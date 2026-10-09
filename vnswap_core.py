"""Logika konversi murni untuk vnswap — mencerminkan aplikasi web 1:1.

Mereplikasi, dalam Python tanpa dependensi:
- lib/ffmpeg.ts  — resep Opus WhatsApp + rantai fallback, pemindaian vendor
- lib/waveform.ts — kurva visualisasi 20 batang/detik (mean-abs, sqrt, round)
- lib/package.ts  — validasi template, aturan nama dasar, resampling

Modul ini TIDAK mengimpor apa pun di luar stdlib sehingga bisa diuji unit
di mana saja, termasuk mesin tanpa textual/rich/ffmpeg terpasang.
"""

from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Versi rilis — satu-satunya sumber kebenaran (dicerminkan di pyproject.toml).
VERSION = "1.7.1"

# --------------------------------------------------------------------------
# Konstanta — harus sama persis dengan aplikasi web
# --------------------------------------------------------------------------

# lib/waveform.ts: VISUALIZATION_BARS_PER_SECOND
VIS_BARS_PER_SECOND = 20
# lib/package.ts: MAX_TEMPLATE_BYTES
MAX_TEMPLATE_BYTES = 36000
# Ekstensi input yang didukung — mencerminkan SUPPORTED_EXTENSIONS milik Dropzone
SUPPORTED_EXTENSIONS = frozenset(
    {
        "mp3", "m4a", "aac", "wav", "ogg", "oga", "opus", "flac",
        "webm", "mp4", "m4v", "mov", "mkv", "3gp", "weba",
    }
)

# Folder voice-note WhatsApp bawaan di perangkat pengguna
DEFAULT_SHARED_DIR = Path(
    "/storage/emulated/999/Android/media/com.whatsapp/WhatsApp"
    "/accounts/1006/.Shared"
)

# Nomor akun/pengguna berbeda-beda tiap perangkat, jadi selain bawaan yang persis kami
# glob setiap varian saudara (bukan hanya `999` / `1006`).
_SHARED_GLOB_PATTERNS = (
    "storage/emulated/*/Android/media/com.whatsapp/WhatsApp/accounts/*/.Shared",
    "sdcard/Android/media/com.whatsapp/WhatsApp/accounts/*/.Shared",
)


def find_shared_candidates() -> list[Path]:
    """Direktori `.Shared` yang ada di seluruh root media WhatsApp yang dikenal.

    Mencakup `$VNSWAP_SHARED`, bawaan yang persis, dan setiap varian
    nomor akun/pengguna. Duplikat symlink (mis. `/sdcard`) digabungkan.
    """
    ordered: list[Path] = []

    def add(p: Path) -> None:
        try:
            key = p.resolve()
        except OSError:
            return
        if p.is_dir() and all(q.resolve() != key for q in ordered):
            ordered.append(p)

    env = os.environ.get("VNSWAP_SHARED", "").strip()
    if env:
        add(Path(env))
    add(DEFAULT_SHARED_DIR)
    for pattern in _SHARED_GLOB_PATTERNS:
        try:
            matches = sorted(Path("/").glob(pattern))
        except OSError:
            continue
        for match in matches:
            add(match)
    return ordered


def count_shared_targets(shared_dir: Path) -> int:
    """Jumlah berkas `*Visualization.data` langsung di bawah direktori `.Shared`."""
    if not shared_dir.is_dir():
        return 0
    try:
        return sum(1 for p in shared_dir.iterdir()
                   if p.is_file() and p.name.endswith("Visualization.data"))
    except OSError:
        return 0


def rank_shared_candidates() -> list[tuple[Path, int]]:
    """Kandidat diurutkan berdasarkan jumlah voice-note, terbanyak lebih dulu."""
    ranked = [(p, count_shared_targets(p)) for p in find_shared_candidates()]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def auto_shared_dir(explicit: Path | None = None) -> Path:
    """Pilih direktori `.Shared` terbaik: yang eksplisit bila ada, kalau tidak
    kandidat dengan voice-note terbanyak, kalau tidak bawaan (atau
    path eksplisit yang hilang) agar error tetap menampilkan path yang konkret."""
    if explicit is not None and explicit.is_dir():
        return explicit
    ranked = rank_shared_candidates()
    if ranked:
        return ranked[0][0]
    return explicit if explicit is not None else DEFAULT_SHARED_DIR

_OPUS_TAGS_MAGIC = b"OpusTags"
_MAX_VENDOR_LENGTH = 256  # lib/ffmpeg.ts: MAX_VENDOR_LENGTH

# --------------------------------------------------------------------------
# Deteksi target
# --------------------------------------------------------------------------

@dataclass
class VoiceNoteTarget:
    """Pasangan `*Visualization.data` + `<base>.opus` yang terdeteksi."""

    data_path: Path
    opus_path: Path | None
    length: int
    approx_duration_sec: float
    mtime: float = 0.0

    @property
    def base_name(self) -> str:
        return template_base_name(self.data_path.name, "voicenote")

    @property
    def short_name(self) -> str:
        return shorten_middle(self.data_path.name, 28)


def shorten_middle(name: str, width: int = 28) -> str:
    """Pemotongan tengah `abcdef...xyz` untuk nama sidecar 50+ karakter."""
    if len(name) <= width or width < 8:
        return name
    keep = width - 1  # 1 untuk elipsis
    head = (keep + 1) // 2
    tail = keep - head
    return f"{name[:head]}…{name[-tail:]}"


def template_base_name(file_name: str, fallback: str) -> str:
    """`abc123Visualization.data` -> `abc123`; bila tidak, buang ekstensi."""
    trimmed = file_name.strip()
    match = re.match(r"^(.*)Visualization\.data$", trimmed, re.IGNORECASE)
    if match and match.group(1):
        return match.group(1)
    without_ext = re.sub(r"\.[^.]+$", "", trimmed).strip()
    return without_ext or fallback


def parse_target_visualization_data(
    raw: bytes, file_name: str
) -> tuple[int, float]:
    """Validasi byte sidecar; kembalikan (length, approx_duration_sec)."""
    if len(raw) == 0:
        raise ValueError("Berkas Visualization.data itu kosong.")
    if len(raw) > MAX_TEMPLATE_BYTES:
        raise ValueError(
            f"Berkas itu {len(raw)} byte — jauh lebih besar daripada "
            f"sidecar voice-note mana pun (maks {MAX_TEMPLATE_BYTES})."
        )
    for i, byte in enumerate(raw):
        if byte > 100:
            raise ValueError(
                "Berkas itu tidak tampak seperti sidecar Visualization.data "
                f"(byte {i} = {byte}, seharusnya 0-100)."
            )
    return len(raw), len(raw) / VIS_BARS_PER_SECOND


def detect_targets(shared_dir: Path) -> list[VoiceNoteTarget]:
    """Pindai `.Shared/` (rekursif) untuk berkas `*Visualization.data`."""
    if not shared_dir.is_dir():
        return []
    found: list[VoiceNoteTarget] = []
    for data_path in sorted(shared_dir.rglob("*Visualization.data")):
        try:
            raw = data_path.read_bytes()
            length, duration = parse_target_visualization_data(
                raw, data_path.name
            )
        except (OSError, ValueError):
            continue
        base = template_base_name(data_path.name, "")
        opus = data_path.with_name(f"{base}.opus") if base else None
        if opus is not None and not opus.is_file():
            opus = None
        try:
            mtime = data_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        found.append(
            VoiceNoteTarget(
                data_path=data_path,
                opus_path=opus,
                length=length,
                approx_duration_sec=duration,
                mtime=mtime,
            )
        )
    found.sort(key=lambda t: t.mtime, reverse=True)
    return found


# --------------------------------------------------------------------------
# Penemuan sumber
# --------------------------------------------------------------------------

def is_supported_source(path: Path) -> bool:
    """Pemeriksaan ekstensi yang mencerminkan aturan fallback milik Dropzone."""
    return path.suffix.lower().lstrip(".") in SUPPORTED_EXTENSIONS


def discover_sources(dirs: list[Path], limit: int = 30) -> list[Path]:
    """Berkas audio/video terbaru yang didukung di seluruh folder media."""
    files: list[Path] = []
    for folder in dirs:
        if not folder.is_dir():
            continue
        try:
            entries = [e for e in folder.iterdir() if e.is_file()]
        except OSError:
            continue
        for entry in entries:
            try:
                size = entry.stat().st_size
            except OSError:
                continue
            if size > 0 and is_supported_source(entry):
                files.append(entry)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]

# --------------------------------------------------------------------------
# Resep FFmpeg — mencerminkan buildCommandArgs milik lib/ffmpeg.ts secara persis
# --------------------------------------------------------------------------

@dataclass
class EncodePlan:
    args_list: list[list[str]]  # primary, then fallbacks in order
    channels: int
    bitrate: str
    application: str
    label: str


def build_encode_plan(channels: int = 1) -> EncodePlan:
    """Rantai argv yang identik dengan buildCommandArgs milik aplikasi web."""
    if channels == 2:
        return EncodePlan(
            args_list=[
                ["-i", "{in}", "-vn", "-map_metadata", "-1", "-ac", "2",
                 "-ar", "48000", "-c:a", "libopus", "-b:a", "64k",
                 "-vbr", "on", "-application", "audio",
                 "-metadata", "vendor=WhatsApp", "-f", "ogg", "{out}"],
                ["-i", "{in}", "-vn", "-map_metadata", "-1", "-ac", "2",
                 "-ar", "48000", "-c:a", "libopus", "-b:a", "64k",
                 "-application", "audio", "-metadata", "vendor=WhatsApp",
                 "-f", "ogg", "{out}"],
                ["-i", "{in}", "-ac", "2", "-ar", "48000", "-c:a",
                 "libopus", "-b:a", "64k", "{out}"],
                ["-i", "{in}", "-vn", "-ac", "2", "-ar", "48000",
                 "-c:a", "libopus", "-b:a", "64k", "-f", "ogg", "{out}"],
            ],
            channels=2, bitrate="64k", application="audio",
            label="stereo (beta)",
        )
    return EncodePlan(
        args_list=[
            ["-i", "{in}", "-vn", "-map_metadata", "-1", "-ac", "1",
             "-ar", "48000", "-c:a", "libopus", "-b:a", "32k",
             "-vbr", "on", "-application", "voip",
             "-metadata", "vendor=WhatsApp", "-f", "ogg", "{out}"],
            ["-i", "{in}", "-vn", "-ac", "1", "-ar", "48000", "-c:a",
             "libopus", "-b:a", "32k", "-f", "ogg", "{out}"],
        ],
        channels=1, bitrate="32k", application="voip", label="mono",
    )


def read_opus_vendor(raw: bytes) -> str | None:
    """Pindai string vendor OpusTags — mencerminkan readOpusVendor."""
    magic = _OPUS_TAGS_MAGIC
    for offset in range(len(raw) - 12):
        if raw[offset:offset + 8] != magic:
            continue
        size = (raw[offset + 8] | (raw[offset + 9] << 8)
                | (raw[offset + 10] << 16) | (raw[offset + 11] << 24))
        if size < 0 or size > _MAX_VENDOR_LENGTH:
            break
        if offset + 12 + size > len(raw):
            break
        try:
            return raw[offset + 12:offset + 12 + size].decode("utf-8")
        except UnicodeDecodeError:
            break
    return None

# --------------------------------------------------------------------------
# Kurva visualisasi — mencerminkan computeVisualizationData milik lib/waveform.ts
# --------------------------------------------------------------------------

def compute_vis_from_samples(
    samples: list[float], sample_rate: int, duration_sec: float
) -> list[int]:
    """Rata-rata-abs per jendela ~50ms, dinormalisasi ke yang terkeras, kurva sqrt, 0-100."""
    bars = max(1, round(duration_sec * VIS_BARS_PER_SECOND))
    if not samples:
        return [0] * bars
    total = len(samples)
    averages = [0.0] * bars
    samples_per_bar = total / bars
    for bar in range(bars):
        start = int(bar * samples_per_bar)
        end = total if bar == bars - 1 else int((bar + 1) * samples_per_bar)
        if end <= start:
            averages[bar] = 0.0
            continue
        window = samples[start:end]
        averages[bar] = sum(abs(v) for v in window) / len(window)
    loudest = max(averages) if averages else 0.0
    if loudest < 1e-6:
        loudest = 1e-6
    out: list[int] = []
    for avg in averages:
        ratio = max(0.0, min(1.0, avg / loudest))
        out.append(max(0, min(100, round(100 * (ratio ** 0.5)))))
    return out


def resample_bars(source: list[float], target_length: int) -> list[float]:
    """Resample linear — mencerminkan resampleBars milik lib/waveform.ts."""
    if target_length <= 0:
        return []
    if not source:
        return [0.0] * target_length
    if len(source) == target_length:
        return list(source)
    if len(source) == 1:
        return [source[0]] * target_length
    out = [0.0] * target_length
    last = len(source) - 1
    for i in range(target_length):
        pos = (i / (target_length - 1)) * last
        lo = int(pos)
        hi = min(last, lo + 1)
        frac = pos - lo
        out[i] = source[lo] * (1 - frac) + source[hi] * frac
    return out


def clamp_sidecar(bars: list[float], target_length: int) -> bytes:
    """Resample (bila perlu) + jepit ke byte 0-100."""
    sized = bars if len(bars) == target_length else resample_bars(
        bars, target_length
    )
    capped = min(target_length, MAX_TEMPLATE_BYTES)
    return bytes(max(0, min(100, round(v))) for v in sized[:capped])

# --------------------------------------------------------------------------
# Swap — penimpaan atomik dengan backup + rollback
# --------------------------------------------------------------------------

@dataclass
class SwapResult:
    opus_path: Path
    data_path: Path
    backup_opus: Path | None = None
    backup_data: Path | None = None
    vendor: str | None = None


def atomic_swap(
    new_opus: bytes,
    new_data: bytes,
    target: VoiceNoteTarget,
    backup_dir: Path | None = None,
    dry_run: bool = True,
) -> SwapResult:
    """Tulis byte hasil konversi menimpa pasangan target, secara atomik per berkas."""
    import time

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_root = backup_dir or target.data_path.parent
    backup_root.mkdir(parents=True, exist_ok=True)

    result = SwapResult(
        opus_path=target.opus_path or target.data_path.with_name(
            f"{target.base_name}.opus"
        ),
        data_path=target.data_path,
        vendor=read_opus_vendor(new_opus),
    )
    if dry_run:
        return result

    try:
        pairs = [(result.opus_path, new_opus, "backup_opus"),
                 (result.data_path, new_data, "backup_data")]
        for dest, payload, slot in pairs:
            if dest.exists():
                backup = backup_root / f"{dest.name}.bak-{stamp}"
                shutil.copy2(dest, backup)
                if slot == "backup_opus":
                    result.backup_opus = backup
                else:
                    result.backup_data = backup
            tmp = dest.with_name(f"{dest.name}.vnswap-tmp")
            tmp.write_bytes(payload)
            os.replace(tmp, dest)
    except Exception:
        restore_backup(result)
        raise
    return result


def restore_backup(result: SwapResult) -> None:
    """Rollback atomic_swap dari salinan `.bak`-nya (upaya terbaik)."""
    for dest, backup in (
        (result.opus_path, result.backup_opus),
        (result.data_path, result.backup_data),
    ):
        if backup is not None and backup.exists():
            try:
                shutil.copy2(backup, dest)
            except OSError:
                continue


# --------------------------------------------------------------------------
# Helper runner (penemuan ffmpeg, probe durasi, decode pcm)
# --------------------------------------------------------------------------

@dataclass
class RunConfig:
    ffmpeg: str = "ffmpeg"
    channels: int = 1
    apply: bool = False  # False = dry-run, mencerminkan langkah preview web
    cancelled: bool = False  # mencerminkan ConversionSignal { cancelled }


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def probe_duration(ffmpeg: str, source: Path) -> float:
    """Durasi via stderr ffmpeg. Tanpa perlu ffprobe."""
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(source)],
        capture_output=True, text=True, timeout=60,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", proc.stderr)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def decode_pcm_mono(
    ffmpeg: str, source: Path, sample_rate: int = 48000
) -> tuple[list[float], float]:
    """Decode ke PCM mono f32le lewat pipe — setara decodeAudio."""
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error",
         "-i", str(source), "-vn", "-ac", "1", "-ar", str(sample_rate),
         "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"],
        capture_output=True, timeout=600,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="replace")[:300]
        raise RuntimeError(f"Tidak bisa decode {source.name}: {detail}")
    count = len(proc.stdout) // 4
    samples = list(struct.unpack(f"<{count}f", proc.stdout)) if count else []
    duration = len(samples) / sample_rate if sample_rate else 0.0
    return samples, duration
