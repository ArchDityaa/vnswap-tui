"""Pure conversion logic for vnswap — mirrors the web app 1:1.

Replicates, in dependency-free Python:
- lib/ffmpeg.ts  — the WhatsApp Opus recipe + fallback chains, vendor scan
- lib/waveform.ts — 20 bars/s visualization curve (mean-abs, sqrt, round)
- lib/package.ts  — template validation, base-name rule, resampling

This module imports NOTHING outside the stdlib so it can be unit-tested
anywhere, including machines without textual/rich/ffmpeg installed.
"""

from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Constants — must match the web app exactly
# --------------------------------------------------------------------------

# lib/waveform.ts: VISUALIZATION_BARS_PER_SECOND
VIS_BARS_PER_SECOND = 20
# lib/package.ts: MAX_TEMPLATE_BYTES
MAX_TEMPLATE_BYTES = 36000
# Supported input extensions — mirrors Dropzone SUPPORTED_EXTENSIONS
SUPPORTED_EXTENSIONS = frozenset(
    {
        "mp3", "m4a", "aac", "wav", "ogg", "oga", "opus", "flac",
        "webm", "mp4", "m4v", "mov", "mkv", "3gp", "weba",
    }
)

# Default WhatsApp voice-note folder on the user's device
DEFAULT_SHARED_DIR = Path(
    "/storage/emulated/999/Android/media/com.whatsapp/WhatsApp"
    "/accounts/1006/.Shared"
)

_OPUS_TAGS_MAGIC = b"OpusTags"
_MAX_VENDOR_LENGTH = 256  # lib/ffmpeg.ts: MAX_VENDOR_LENGTH

# --------------------------------------------------------------------------
# Target detection
# --------------------------------------------------------------------------

@dataclass
class VoiceNoteTarget:
    """A detected `*Visualization.data` + `<base>.opus` pair."""

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
    """`abcdef...xyz` middle-truncation for 50+ char sidecar names."""
    if len(name) <= width or width < 8:
        return name
    keep = width - 1  # 1 for the ellipsis
    head = (keep + 1) // 2
    tail = keep - head
    return f"{name[:head]}…{name[-tail:]}"


def template_base_name(file_name: str, fallback: str) -> str:
    """`abc123Visualization.data` -> `abc123`; else strip extension."""
    trimmed = file_name.strip()
    match = re.match(r"^(.*)Visualization\.data$", trimmed, re.IGNORECASE)
    if match and match.group(1):
        return match.group(1)
    without_ext = re.sub(r"\.[^.]+$", "", trimmed).strip()
    return without_ext or fallback


def parse_target_visualization_data(
    raw: bytes, file_name: str
) -> tuple[int, float]:
    """Validate sidecar bytes; return (length, approx_duration_sec)."""
    if len(raw) == 0:
        raise ValueError("That Visualization.data file is empty.")
    if len(raw) > MAX_TEMPLATE_BYTES:
        raise ValueError(
            f"That file is {len(raw)} bytes — far larger than any "
            f"voice-note sidecar (max {MAX_TEMPLATE_BYTES})."
        )
    for i, byte in enumerate(raw):
        if byte > 100:
            raise ValueError(
                "That file does not look like a Visualization.data sidecar "
                f"(byte {i} = {byte}, expected 0-100)."
            )
    return len(raw), len(raw) / VIS_BARS_PER_SECOND


def detect_targets(shared_dir: Path) -> list[VoiceNoteTarget]:
    """Scan `.Shared/` (recursive) for `*Visualization.data` files."""
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
# Source discovery
# --------------------------------------------------------------------------

def is_supported_source(path: Path) -> bool:
    """Extension check mirroring Dropzone's fallback rule."""
    return path.suffix.lower().lstrip(".") in SUPPORTED_EXTENSIONS


def discover_sources(dirs: list[Path], limit: int = 30) -> list[Path]:
    """Newest supported audio/video files across media folders."""
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
# FFmpeg recipe — mirrors lib/ffmpeg.ts buildCommandArgs exactly
# --------------------------------------------------------------------------

@dataclass
class EncodePlan:
    args_list: list[list[str]]  # primary, then fallbacks in order
    channels: int
    bitrate: str
    application: str
    label: str


def build_encode_plan(channels: int = 1) -> EncodePlan:
    """Argv chains identical to the web app's buildCommandArgs."""
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
    """Scan for the OpusTags vendor string — mirrors readOpusVendor."""
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
# Visualization curve — mirrors lib/waveform.ts computeVisualizationData
# --------------------------------------------------------------------------

def compute_vis_from_samples(
    samples: list[float], sample_rate: int, duration_sec: float
) -> list[int]:
    """Mean-abs per ~50ms window, loudest-normalised, sqrt curve, 0-100."""
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
    """Linear resample — mirrors lib/waveform.ts resampleBars."""
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
    """Resample (if needed) + clamp to 0-100 bytes."""
    sized = bars if len(bars) == target_length else resample_bars(
        bars, target_length
    )
    capped = min(target_length, MAX_TEMPLATE_BYTES)
    return bytes(max(0, min(100, round(v))) for v in sized[:capped])

# --------------------------------------------------------------------------
# Swap — atomic overwrite with backup + rollback
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
    """Write converted bytes over the target pair, atomically per file."""
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
    """Roll back an atomic_swap from its `.bak` copies (best effort)."""
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
# Runner helpers (ffmpeg discovery, duration probe, pcm decode)
# --------------------------------------------------------------------------

@dataclass
class RunConfig:
    ffmpeg: str = "ffmpeg"
    channels: int = 1
    apply: bool = False  # False = dry-run, mirrors the web preview step
    cancelled: bool = False  # mirrors ConversionSignal { cancelled }


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def probe_duration(ffmpeg: str, source: Path) -> float:
    """Duration via ffmpeg stderr. No ffprobe needed."""
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
    """Decode to f32le mono PCM on a pipe — the decodeAudio equivalent."""
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error",
         "-i", str(source), "-vn", "-ac", "1", "-ar", str(sample_rate),
         "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"],
        capture_output=True, timeout=600,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="replace")[:300]
        raise RuntimeError(f"Could not decode {source.name}: {detail}")
    count = len(proc.stdout) // 4
    samples = list(struct.unpack(f"<{count}f", proc.stdout)) if count else []
    duration = len(samples) / sample_rate if sample_rate else 0.0
    return samples, duration
