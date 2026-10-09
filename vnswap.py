"""vnswap — penukar voice-note termux.

Panduan layar penuh + fallback --cli + server web + update mandiri.
Cara pakai di termux (sesudah install.sh, dari mana saja):
  vnswap          buka TUI
  vnswap web      jalankan server web
  vnswap update   update ke versi terbaru dari GitHub
Tanpa launcher, dari folder repo:
  python vnswap.py [tui|cli|web|update] [opsi...]
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vnswap_core as core


# ---------------------------------------------------------------------------
# Pembantu warna CLI — ANSI manual, nonaktif otomatis bila bukan TTY.
# Tanpa emoji. Level: [OK], [info], [!!], [XX].
# ---------------------------------------------------------------------------

_ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "green": "\033[32m",
    "cyan": "\033[36m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "muted": "\033[90m",
}


def _use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def cprint(msg: str, color: str = "", bold: bool = False) -> None:
    if _use_color() and color in _ANSI:
        prefix = _ANSI["bold"] if bold else ""
        print(f"{prefix}{_ANSI[color]}{msg}{_ANSI['reset']}")
    else:
        print(msg)


def _fmt_size(n: int) -> str:
    try:
        v = float(n)
    except (TypeError, ValueError):
        return "--"
    if v < 1024:
        return f"{int(v)} B"
    if v < 1024 * 1024:
        return f"{v / 1024:.1f} KB"
    return f"{v / (1024 * 1024):.1f} MB"


def _fmt_dur(s: float) -> str:
    try:
        v = max(0.0, float(s))
    except (TypeError, ValueError):
        return "--:--"
    m = int(v // 60)
    sec = int(round(v % 60))
    if sec == 60:
        m += 1
        sec = 0
    return f"{m}:{sec:02d}"


def _try_rich_table(title: str, columns: list[str], rows: list[list[str]]) -> bool:
    """Tampilkan dengan rich bila terpasang. Kembali True bila dipakai."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        return False
    try:
        console = Console()
        table = Table(title=title, show_header=True, header_style="bold")
        for col in columns:
            table.add_column(col)
        for row in rows:
            table.add_row(*row)
        console.print(table)
        return True
    except Exception:
        return False


@dataclass
class AppState:
    shared_dir: Path = core.DEFAULT_SHARED_DIR
    media_dirs: list[Path] = field(default_factory=list)
    channels: int = 1
    apply_mode: bool = True  # default langsung tulis + backup .bak
    cancelled: bool = False
    target: core.VoiceNoteTarget | None = None
    source: Path | None = None
    targets: list[core.VoiceNoteTarget] = field(default_factory=list)
    sources: list[Path] = field(default_factory=list)


STATE = AppState()


def get_app_state() -> AppState:
    return STATE


def default_media_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / "storage" / "downloads",
        home / "storage" / "movies",
        home / "storage" / "music",
        home / "storage" / "dcim",
        Path("/sdcard/Download"),
        Path("/sdcard/Movies"),
        Path("/sdcard/Music"),
    ]


def run_cli(state: AppState) -> int:
    """Fallback teks saat textual tidak terpasang."""
    cprint("penukar voicenote (mode teks)", "cyan", bold=True)
    print("dikembangkan oleh hakiraadityaa")
    print(f"shared: {state.shared_dir}")
    targets = core.detect_targets(state.shared_dir)
    if not targets:
        cprint("[XX] tidak ada target Visualization.data ditemukan.", "red", bold=True)
        print("1. Buka WhatsApp, putar satu voice note")
        print("2. Jalankan lagi dengan --shared yang benar")
        return 1
    rows = []
    for i, t in enumerate(targets[:10]):
        mark = "[*]" if i == 0 else "[ ]"
        status = "[OK] opus" if t.opus_path else "[--] tanpa opus"
        rows.append([mark, str(i), t.short_name, _fmt_dur(t.approx_duration_sec),
                     _fmt_size(t.length), status])
    if not _try_rich_table("TARGET", ["", "No", "Nama", "Durasi", "Ukuran", "Status"], rows):
        cprint("TARGET:", "cyan", bold=True)
        for r in rows:
            print(f"{r[0]} [{r[1]}] {r[2]} | {r[3]} | {r[4]} | {r[5]}")
    try:
        choice = input("pilih target [0]: ").strip() or "0"
        state.target = targets[int(choice)]
    except (ValueError, IndexError):
        cprint("[XX] pilihan tidak valid.", "red")
        return 1
    sources = core.discover_sources(state.media_dirs)
    srows = []
    for i, s in enumerate(sources[:15]):
        try:
            sz = s.stat().st_size
        except OSError:
            sz = 0
        srows.append([str(i), s.name, _fmt_size(sz)])
    if srows:
        if not _try_rich_table("SUMBER", ["No", "Nama", "Ukuran"], srows):
            cprint("SUMBER:", "cyan", bold=True)
            for r in srows:
                print(f"[{r[0]}] {r[1]} | {r[2]}")
    else:
        cprint("[!!] tidak ada sumber otomatis, ketik path manual.", "yellow")
    src = input("path sumber (angka/path): ").strip()
    if src.isdigit() and sources:
        state.source = sources[int(src) % len(sources)]
    else:
        state.source = Path(src)
    if not state.source.is_file():
        cprint("[XX] file sumber tidak ada.", "red")
        return 1
    if not core.is_supported_source(state.source):
        cprint("[!!] ekstensi tidak dikenal, lanjut dengan risiko gagal encode.", "yellow")
    else:
        cprint(f"[OK] sumber: {state.source.name}", "green")
    typed = input("[Enter] TUKAR, [k] batal: ").strip().upper()
    if typed.startswith("K"):
        print("dibatalkan.")
        return 0
    return run_pipeline(state)


def run_pipeline(state: AppState) -> int:
    """Alur blokir bersama untuk --cli (TUI memakai worker)."""
    import tempfile

    assert state.target is not None and state.source is not None
    ffmpeg = core.find_ffmpeg()
    if not ffmpeg:
        cprint("[XX] ffmpeg tidak ditemukan - pkg install ffmpeg dulu.", "red", bold=True)
        return 1
    plan = core.build_encode_plan(state.channels)
    channels = "mono" if state.channels == 1 else "stereo beta"
    cprint(f"[info] resep: opus {plan.bitrate} {plan.application} {channels}", "cyan")
    cprint(f"[info] target: {state.target.short_name} "
           f"({_fmt_dur(state.target.approx_duration_sec)}, "
           f"{_fmt_size(state.target.length)})", "cyan")
    if not state.apply_mode:
        cprint("[info] mode: PREVIEW - tidak ubah file", "cyan", bold=True)
    else:
        cprint("[!!] mode: TULIS LANGSUNG + backup .bak otomatis", "yellow", bold=True)
    with tempfile.TemporaryDirectory(prefix="vnswap-") as tmpdir:
        out = Path(tmpdir) / "converted.ogg"
        converted: bytes | None = None
        for idx, argv in enumerate(plan.args_list):
            cmd = [
                str(state.source) if a == "{in}"
                else str(out) if a == "{out}" else a
                for a in [ffmpeg, "-hide_banner", "-y", *argv]
            ]
            print(f"[info] encode {'utama' if idx == 0 else f'fallback {idx}'}...")
            import subprocess

            proc = subprocess.run(cmd, capture_output=True)
            if proc.returncode == 0 and out.exists():
                converted = out.read_bytes()
                cprint(f"[OK] encode ok ({len(converted)} bytes).", "green")
                break
            cprint("[!!] encode gagal, coba berikutnya...", "yellow")
        if not converted:
            cprint("[XX] semua percobaan encode gagal.", "red", bold=True)
            return 1
        print(f'[info] vendor: "{core.read_opus_vendor(converted) or "tak terbaca"}".')
        samples, duration = core.decode_pcm_mono(ffmpeg, state.source)
        bars = core.compute_vis_from_samples(samples, 48000, duration or 1.0)
        sidecar = core.clamp_sidecar(bars, state.target.length)
        cprint(f"[OK] sidecar {len(sidecar)} bytes (target {state.target.length}).", "green")
        result = core.atomic_swap(
            converted, sidecar, state.target,
            dry_run=not state.apply_mode,
        )
        if state.apply_mode:
            cprint(f"[OK] tertukar: {result.opus_path} + {result.data_path}", "green", bold=True)
            print(f"backup opus: {result.backup_opus or '--'}")
            print(f"backup data: {result.backup_data or '--'}")
            print("Buka WhatsApp dan putar VN untuk verifikasi.")
        else:
            cprint("[OK] preview selesai - tidak ada file diubah.", "green", bold=True)
        print("dikembangkan oleh hakiraadityaa")
    return 0


def print_health_issues(shared: Path, media_dirs: list[Path]) -> None:
    """Cetak ringkasan masalah kesehatan awal (bila ada) sebelum jalan."""
    try:
        checks = core.check_health(shared, media_dirs)
    except Exception:
        return
    failed = core.health_failed(checks)
    if not failed:
        return
    cprint("[!!] pemeriksaan kesehatan menemukan masalah:", "yellow", bold=True)
    for c in failed:
        print(f"[XX] {c.label}: {c.detail}")
        if c.fix:
            print(f"     Perbaiki: {c.fix}")
    print("Detail penuh: vnswap health")


def run_health(shared: Path, media_dirs: list[Path]) -> int:
    """Subcommand `health`: laporan lengkap + kode kembali 0/1."""
    checks = core.check_health(shared, media_dirs)
    print(core.format_health_report(checks))
    failed = core.health_failed(checks)
    if not failed:
        cprint("[OK] semua pemeriksaan lolos.", "green", bold=True)
        return 0
    cprint(f"[XX] {len(failed)} pemeriksaan gagal (lihat Perbaiki di atas).", "red", bold=True)
    return 1


SUBCOMMANDS = ("tui", "cli", "web", "update", "health")

EPILOG = """subcommand (boleh dihilangkan, default: tui):
  tui             buka TUI layar penuh
  cli             mode teks (tanpa TUI)
  web             jalankan server web (--host/--port/--token/--no-auth)
  update          update ke versi terbaru dari GitHub (--check = cek saja)
  health          cek ffmpeg, folder .Shared, dan izin + perintah perbaikan

contoh:
  vnswap
  vnswap web --host 0.0.0.0 --port 8080
  vnswap update
  vnswap update --check
Flag lama tetap bisa: `vnswap --web`, `vnswap --cli`."""


def split_subcommand(argv: list[str]) -> tuple[str | None, list[str]]:
    """Ambil subcommand opsional di posisi pertama (tui/cli/web/update)."""
    if argv and argv[0] in SUBCOMMANDS:
        return argv[0], argv[1:]
    return None, argv


def resolve_mode(cmd: str | None, args: argparse.Namespace) -> str:
    """Tentukan mode jalan: subcommand menang atas flag lama."""
    if cmd in SUBCOMMANDS:
        return cmd
    if getattr(args, "web", False):
        return "web"
    if getattr(args, "cli", False):
        return "cli"
    return "tui"


def _git(repo: Path, *git_args: str) -> tuple[int, str]:
    import subprocess

    proc = subprocess.run(["git", "-C", str(repo), *git_args],
                          capture_output=True, text=True, timeout=120)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _read_version(repo: Path) -> str | None:
    """Baca VERSION dari vnswap_core.py tanpa import (kode mungkin baru)."""
    import re

    try:
        text = (repo / "vnswap_core.py").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', text, re.M)
    return match.group(1) if match else None


def run_update(check_only: bool = False,
               repo: Path | None = None) -> int:
    """Update ke versi terbaru dari GitHub via git pull.

    Kode kembali: 0 = ok/sudah terbaru, 1 = gagal, 2 = ada update (mode cek).
    """
    import shutil

    repo = repo or Path(__file__).resolve().parent
    if not shutil.which("git"):
        print("[XX] git tidak ditemukan — pkg install git dulu.")
        return 1
    if not (repo / ".git").is_dir():
        print("[XX] folder ini bukan clone git, update otomatis tidak bisa.")
        print("Clone dari GitHub dulu:")
        print("  git clone https://github.com/ArchDityaa/vnswap-tui")
        return 1
    print(f"versi sekarang: {core.VERSION}")
    code, branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch.strip() if code == 0 and branch.strip() != "HEAD" else "main"
    code, upstream = _git(repo, "rev-parse", "--abbrev-ref", "@{u}")
    upstream = upstream.strip() if code == 0 else f"origin/{branch}"
    code, kotor = _git(repo, "status", "--porcelain")
    if code == 0 and kotor:
        print("[XX] ada perubahan lokal, update dibatalkan agar tidak hilang.")
        print("Simpan dulu (git stash) atau buang (git checkout -- .), lalu ulangi.")
        return 1
    code, _ = _git(repo, "fetch", "origin")
    if code != 0:
        print("[XX] fetch dari GitHub gagal — cek koneksi internet.")
        return 1
    code, lokal = _git(repo, "rev-parse", "HEAD")
    code2, jauh = _git(repo, "rev-parse", upstream)
    if code != 0 or code2 != 0:
        print(f"[XX] tidak bisa bandingkan dengan {upstream}.")
        return 1
    if lokal == jauh:
        print(f"[OK] sudah versi terbaru ({upstream}).")
        return 0
    if check_only:
        print(f"[!!] ada update di {upstream} — jalankan `vnswap update`.")
        return 2
    code, out = _git(repo, "merge", "--ff-only", upstream)
    if code != 0:
        print("[XX] merge gagal (riwayat bercabang). Update manual:")
        print(f"  git -C {repo} fetch origin")
        print(f"  git -C {repo} reset --hard {upstream}")
        print(out)
        return 1
    baru = _read_version(repo) or "?"
    print(f"[OK] terupdate ke {baru} ({jauh[:12]}). Jalankan ulang vnswap.")
    return 0


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    cmd, rest = split_subcommand(raw)
    parser = argparse.ArgumentParser(prog="vnswap", epilog=EPILOG,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--shared", default=None,
                        help="folder .Shared (default: deteksi otomatis)")
    parser.add_argument("--dry-run", action="store_true",
                        help="preview saja, tidak ubah file")
    parser.add_argument("--apply", action="store_true",
                        help="(deprecated, kini default) tulis langsung")
    parser.add_argument("--stereo", action="store_true",
                        help="pakai stereo beta (default: mono)")
    parser.add_argument("--cli", action="store_true",
                        help="jalankan mode teks (tanpa TUI)")
    parser.add_argument("--web", action="store_true",
                        help="jalankan antarmuka web interaktif")
    parser.add_argument("--host", default="127.0.0.1",
                        help="host server web (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000,
                        help="port server web (default: 8000)")
    parser.add_argument("--token", default=None,
                        help="token auth server web (default: auto saat host non-lokal)")
    parser.add_argument("--no-auth", action="store_true",
                        help="nonaktifkan token auth server web (hanya untuk jaringan tepercaya)")
    parser.add_argument("--check", action="store_true",
                        help="cek update saja tanpa download (untuk `update`)")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {core.VERSION}")
    args = parser.parse_args(rest)

    STATE.shared_dir = (Path(args.shared) if args.shared
                          else core.auto_shared_dir())
    STATE.media_dirs = default_media_dirs()
    STATE.channels = 2 if args.stereo else 1
    STATE.apply_mode = not args.dry_run

    mode = resolve_mode(cmd, args)

    if mode == "update":
        return run_update(check_only=args.check)

    if mode == "health":
        return run_health(STATE.shared_dir, STATE.media_dirs)

    if mode == "web":
        print_health_issues(STATE.shared_dir, STATE.media_dirs)
        import vnswap_web
        token, generated = vnswap_web.resolve_token(
            args.host, args.token, args.no_auth)
        try:
            srv = vnswap_web.run_server(args.host, args.port,
                                        STATE.shared_dir, default_media_dirs(),
                                        token=token)
        except OSError as exc:
            print(f"[XX] {exc}")
            return 1
        port = srv.server_address[1]
        print(f"vnswap web v{core.VERSION}: buka salah satu URL ini di browser HP:")
        for u in vnswap_web.access_urls(args.host, port, token):
            print(f"  {u}")
        print(f"  http://127.0.0.1:{port}/api/diagnostics"
              "  (halaman diagnosis bila daftar target kosong)")
        if token:
            print("token sudah tersemat di URL di atas.")
            if generated:
                print("[!!] token dibuat otomatis karena host non-lokal.")
        elif not vnswap_web.is_loopback(args.host):
            print("[!!] tanpa token di jaringan lokal — hanya untuk jaringan tepercaya.")
        print(f"shared: {STATE.shared_dir}")
        print("dikembangkan oleh hakiraadityaa (Ctrl+C untuk berhenti)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0

    if mode == "cli":
        print_health_issues(STATE.shared_dir, STATE.media_dirs)
        return run_cli(STATE)

    try:
        from textual.app import App
        from vnswap_ui_nav import TargetScreen, APP_CSS
    except ImportError:
        print("textual belum terinstall — jatuh ke mode teks.")
        print("textual itu paket python, pasang dengan: pip install textual")
        print("(bukan: pkg install textual — itu memang tidak ada.)")
        return run_cli(STATE)

    class VnSwapApp(App):
        TITLE = "penukar voicenote"
        SUB_TITLE = "audio dan video jadi voice note - by hakiraadityaa"
        CSS = APP_CSS

        def on_mount(self) -> None:
            self.push_screen(TargetScreen())

    VnSwapApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
