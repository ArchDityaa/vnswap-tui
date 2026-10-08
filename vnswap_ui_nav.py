"""Textual fullscreen UI for vnswap — theme + target/source screens.

Dark Pro theme, dark-only. No emoji in code or UI text.
Status markers use ASCII tags: [OK], [--], [!!], [XX].
"""

from __future__ import annotations

import time
from pathlib import Path

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import Screen
    from textual.widgets import (
        Button, Checkbox, DataTable, Footer, Header, Input, Label, Static,
    )
    TEXTUAL_OK = True
except ImportError:
    TEXTUAL_OK = False
    App = object  # type: ignore
    ComposeResult = object  # type: ignore
    Binding = object  # type: ignore
    Horizontal = object  # type: ignore
    Vertical = object  # type: ignore
    Screen = object  # type: ignore
    Button = Checkbox = DataTable = Footer = Header = Input = Label = Static = object  # type: ignore

import vnswap_core as core

# ---------------------------------------------------------------------------
# Dark Pro theme — dark-only.
# Single primary accent (emerald). INFO only for neutral info,
# WARN only for recoverable warnings, DANGER only for destructive/errors.
# ---------------------------------------------------------------------------

BG = "#0B0E14"        # app background
PANEL = "#101623"     # header / footer layer
SURFACE = "#131A29"   # card / panel
SURFACE2 = "#1B2436"  # table header / input
BORDER = "#2A3446"    # hairline
BORDER_HI = "#3A4A63"  # focus ring / cursor outline
TEXT = "#E8ECF4"      # primary text
MUTED = "#939DB4"     # secondary text / hint
ACCENT = "#34D399"    # emerald — primary action only
INFO = "#22D3EE"      # cyan — neutral info only
WARN = "#FBBF24"      # recoverable warnings only
DANGER = "#F87171"    # destructive + fatal errors only

CREDIT_TEXT = "developed by hakiraadityaa"

APP_CSS = f"""
Screen {{
    background: {BG};
    color: {TEXT};
}}
Header {{
    background: {PANEL};
    color: {TEXT};
    text-style: bold;
}}
Footer {{
    background: {PANEL};
    color: {MUTED};
}}
#stepper {{
    color: {MUTED};
    padding: 0 2;
    margin: 1 2 0 2;
}}
#pill {{
    color: {BG};
    background: {ACCENT};
    text-style: bold;
    padding: 0 2;
    margin: 0 2 0 2;
    width: auto;
}}
#title {{
    color: {TEXT};
    text-style: bold;
    padding: 0 2;
    margin: 0 2;
}}
#subtitle {{
    color: {MUTED};
    padding: 0 2;
    margin: 0 2 1 2;
}}
#hint {{
    color: {MUTED};
    padding: 0 2;
    margin: 1 2 0 2;
}}
#credit {{
    color: {MUTED};
    padding: 0 2;
    margin: 0 2 1 2;
}}
.key {{
    background: {SURFACE2};
    color: {TEXT};
    border: solid {BORDER};
    padding: 0 1;
    margin: 0 1 0 0;
}}
.card {{
    background: {SURFACE};
    border: solid {BORDER};
    color: {TEXT};
    padding: 1 2;
    margin: 1 2;
}}
.card-info {{
    background: {SURFACE};
    border-left: tall {INFO};
    border-top: solid {BORDER};
    border-right: solid {BORDER};
    border-bottom: solid {BORDER};
    color: {TEXT};
    padding: 1 2;
    margin: 1 2;
}}
.card-warn {{
    background: {SURFACE};
    border-left: tall {WARN};
    border-top: solid {BORDER};
    border-right: solid {BORDER};
    border-bottom: solid {BORDER};
    color: {TEXT};
    padding: 1 2;
    margin: 1 2;
}}
.card-danger {{
    background: {SURFACE};
    border-left: tall {DANGER};
    border-top: solid {BORDER};
    border-right: solid {BORDER};
    border-bottom: solid {BORDER};
    color: {TEXT};
    padding: 1 2;
    margin: 1 2;
}}
#mode-preview {{
    color: {INFO};
    text-style: bold;
}}
#mode-write {{
    color: {DANGER};
    text-style: bold;
}}
DataTable {{
    background: {SURFACE};
    color: {TEXT};
    border: solid {BORDER};
    margin: 1 2;
    height: 1fr;
}}
DataTable > .datatable--header {{
    background: {SURFACE2};
    color: {TEXT};
    text-style: bold;
}}
DataTable > .datatable--cursor {{
    background: {SURFACE2};
    color: {TEXT};
    text-style: bold;
}}
DataTable > .datatable--hover {{
    background: {BORDER};
}}
Input {{
    background: {SURFACE2};
    color: {TEXT};
    border: solid {BORDER};
    margin: 1 2;
    padding: 0 1;
}}
Input:focus {{
    border: solid {ACCENT};
}}
Checkbox {{
    margin: 0 2;
    color: {MUTED};
}}
Checkbox:focus {{
    text-style: bold;
    color: {TEXT};
}}
Button {{
    margin: 1 1 1 2;
    min-width: 28;
    height: 3;
}}
Button:focus {{
    text-style: bold;
    border: solid {BORDER_HI};
}}
#go {{
    background: {ACCENT};
    color: {BG};
    text-style: bold;
    min-width: 32;
    border: tall {ACCENT};
}}
#go:hover {{
    background: #5EEAD4;
}}
#next {{
    background: {ACCENT};
    color: {BG};
    text-style: bold;
    min-width: 32;
    border: tall {ACCENT};
}}
#back, #rescan {{
    background: {SURFACE2};
    color: {TEXT};
    border: solid {BORDER};
}}
#rollback {{
    background: {WARN};
    color: {BG};
    text-style: bold;
}}
#rollback:disabled {{
    background: {SURFACE2};
    color: {MUTED};
}}
#done {{
    background: {SURFACE2};
    color: {TEXT};
}}
#done:disabled {{
    background: {SURFACE};
    color: {MUTED};
}}
ProgressBar {{
    margin: 1 2 0 2;
    height: 1;
}}
ProgressBar > .bar--bar {{
    background: {ACCENT};
}}
ProgressBar > .bar--track {{
    background: {SURFACE2};
}}
#percent {{
    color: {TEXT};
    text-style: bold;
    margin: 1 2 0 0;
    width: 8;
}}
#stages {{
    background: {SURFACE};
    border: solid {BORDER};
    color: {TEXT};
    padding: 1 2;
    margin: 1 2 0 2;
}}
#result-card {{
    background: {SURFACE};
    border: solid {BORDER};
    color: {TEXT};
    padding: 1 2;
    margin: 1 2;
}}
Log {{
    background: {SURFACE};
    color: {TEXT};
    border: solid {BORDER};
    margin: 1 2;
    height: 1fr;
    padding: 1 1;
}}
#empty {{
    color: {MUTED};
    padding: 2 2;
    margin: 1 2;
    background: {SURFACE};
    border: solid {BORDER};
}}
#summary-ok {{
    color: {ACCENT};
    text-style: bold;
}}
#target-card, #source-card {{
    background: {SURFACE};
    border: solid {BORDER};
    color: {TEXT};
    padding: 1 2;
    margin: 1 1 1 2;
    height: auto;
}}
"""


# ---------------------------------------------------------------------------
# Pure format helpers — no core logic changes.
# ---------------------------------------------------------------------------

def render_stepper(active: int) -> str:
    """Persistent 4-step indicator. active is 1..4."""
    steps = ["1 TARGET", "2 SUMBER", "3 CEK", "4 PROSES"]
    parts: list[str] = []
    for i, name in enumerate(steps, start=1):
        if i < active:
            parts.append(f"[x] {name}")
        elif i == active:
            parts.append(f"[*] {name}")
        else:
            parts.append(f"[ ] {name}")
    return " -- ".join(parts)


def rel_time(mtime: float) -> str:
    """Relative time label, Termux-safe ASCII."""
    try:
        delta = time.time() - float(mtime)
    except (TypeError, ValueError):
        return "--"
    if delta < 0:
        return "baru saja"
    if delta < 60:
        return "baru saja"
    if delta < 3600:
        mins = int(delta // 60)
        return f"{mins} mnt lalu"
    if delta < 86400:
        hours = int(delta // 3600)
        return f"{hours} jam lalu"
    days = int(delta // 86400)
    if days == 1:
        return "1 hari lalu"
    if days < 30:
        return f"{days} hari lalu"
    return time.strftime("%Y-%m-%d", time.localtime(mtime))


def fmt_size(num_bytes: int) -> str:
    """Consistent size label with one decimal."""
    try:
        n = float(num_bytes)
    except (TypeError, ValueError):
        return "--"
    if n < 0:
        return "--"
    if n < 1024:
        return f"{int(n)} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def fmt_dur(seconds: float) -> str:
    """Duration as m:ss, no tilde prefix."""
    try:
        s = max(0.0, float(seconds))
    except (TypeError, ValueError):
        return "--:--"
    mins = int(s // 60)
    secs = int(round(s % 60))
    if secs == 60:
        mins += 1
        secs = 0
    return f"{mins}:{secs:02d}"


def media_tag(path: Path | str) -> str:
    """Short type label from extension: 'MP3 A' or 'MP4 V'."""
    suffix = Path(str(path)).suffix.lower().lstrip(".")
    audio = {"mp3", "m4a", "aac", "wav", "ogg", "oga", "opus", "flac", "weba"}
    video = {"webm", "mp4", "m4v", "mov", "mkv", "3gp"}
    if suffix in audio:
        return f"{suffix.upper()} A"
    if suffix in video:
        return f"{suffix.upper()} V"
    if suffix:
        return f"{suffix.upper()} ?"
    return "--"


def wave_preview(bars: list[float] | bytes | None, width: int = 40) -> str:
    """ASCII waveform from 0-100 bars. Termux-safe chars only."""
    glyphs = " .-=+#"
    if not bars:
        return "memuat pola..."
    try:
        vals = [max(0, min(100, int(v))) for v in bars]
    except (TypeError, ValueError):
        return "memuat pola..."
    if len(vals) > width:
        # downsample evenly
        step = len(vals) / width
        vals = [vals[int(i * step)] for i in range(width)]
    out: list[str] = []
    for v in vals:
        idx = min(len(glyphs) - 1, v * len(glyphs) // 101)
        out.append(glyphs[idx])
    return "".join(out)


def status_dot(ok: bool, ok_text: str = "[OK]", bad_text: str = "[--]") -> str:
    return ok_text if ok else bad_text


class TargetScreen(Screen):
    """(1) pick the newest voice-note pair in .Shared/."""

    BINDINGS = [
        ("enter", "next", "Lanjut"),
        ("r", "rescan", "Rescan"),
        ("escape", "quit", "Keluar"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(render_stepper(1), id="stepper")
        yield Label("STEP 1 DARI 3 - TARGET", id="pill")
        yield Label("Target - voice note yang akan diganti", id="title")
        yield Label(
            "Paling baru sudah dipilih. Up/Down pindah, Enter lanjut.",
            id="subtitle",
        )
        yield DataTable(id="targets", zebra_stripes=True, cursor_type="row")
        yield Static("", id="empty", classes="card")
        yield Label("[Enter] Lanjut   [R] Rescan   [Up/Down] Pilih   [Esc] Keluar", id="hint")
        with Horizontal():
            yield Button("Rescan", id="rescan")
            yield Button("Lanjut >", id="next", variant="success")
        yield Label(CREDIT_TEXT, id="credit")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#targets", DataTable)
        table.add_columns("No", "Nama", "Dur", "Lama", "Size", "Status")
        self._load()
        try:
            self.query_one("#next", Button).focus()
        except Exception:
            pass

    def _load(self) -> None:
        from __main__ import get_app_state

        state = get_app_state()
        table = self.query_one("#targets", DataTable)
        empty = self.query_one("#empty", Static)
        table.clear()
        state.targets = core.detect_targets(state.shared_dir)
        if not state.targets:
            empty.update(
                "Belum ada target di folder .Shared\n"
                "1. Buka WhatsApp, putar satu voice note\n"
                "2. Kembali ke sini, tekan [R] Rescan\n"
                f"Path: {state.shared_dir}"
            )
            empty.display = True
            table.display = False
            self.query_one("#subtitle", Label).update(
                "Belum ada Visualization.data — putar VN dulu, lalu Rescan."
            )
            return
        empty.display = False
        table.display = True
        for i, t in enumerate(state.targets[:20], start=1):
            table.add_row(
                str(i),
                t.short_name,
                fmt_dur(t.approx_duration_sec),
                rel_time(t.mtime),
                fmt_size(t.length),
                "[OK] opus" if t.opus_path else "[--] tanpa opus",
            )
        if state.targets:
            state.target = state.targets[0]

    def _go_next(self) -> None:
        from __main__ import get_app_state

        state = get_app_state()
        if not state.targets:
            return
        table = self.query_one("#targets", DataTable)
        row = table.cursor_row if table.cursor_row is not None else 0
        state.target = state.targets[min(row, len(state.targets) - 1)]
        self.app.push_screen(SourceScreen())

    def action_next(self) -> None:
        self._go_next()

    def action_rescan(self) -> None:
        self._load()

    def action_quit(self) -> None:
        self.app.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next":
            self._go_next()
        else:
            self._load()


class SourceScreen(Screen):
    """(2) pick the replacement audio/video."""

    BINDINGS = [
        ("enter", "next", "Lanjut"),
        ("escape", "back", "Kembali"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(render_stepper(2), id="stepper")
        yield Label("STEP 2 DARI 3 - SUMBER", id="pill")
        yield Label("Sumber - audio atau video pengganti", id="title")
        yield Static("", id="context", classes="card")
        yield Input(placeholder="Filter: ketik untuk saring daftar...", id="filter")
        yield DataTable(id="sources", zebra_stripes=True, cursor_type="row")
        yield Input(placeholder="...atau ketik path manual di sini", id="manual")
        yield Static("", id="manual-status")
        yield Label("[Enter] Lanjut   [Esc] Kembali", id="hint")
        with Horizontal():
            yield Button("< Kembali", id="back")
            yield Button("Lanjut >", id="next", variant="success")
        yield Label(CREDIT_TEXT, id="credit")
        yield Footer()

    def on_mount(self) -> None:
        from __main__ import get_app_state

        state = get_app_state()
        table = self.query_one("#sources", DataTable)
        table.add_columns("No", "Nama", "Tipe", "Size")
        target_name = state.target.short_name if state.target else "--"
        target_dur = fmt_dur(state.target.approx_duration_sec) if state.target else "--:--"
        self.query_one("#context", Static).update(
            f"Target: {target_name} ({target_dur})"
        )
        state.sources = core.discover_sources(state.media_dirs)
        self._all_sources: list[Path] = list(state.sources)
        self._fill_table(self._all_sources)
        if state.sources:
            state.source = state.sources[0]
        try:
            self.query_one("#filter", Input).focus()
        except Exception:
            pass

    def _fill_table(self, paths: list[Path]) -> None:
        table = self.query_one("#sources", DataTable)
        table.clear()
        if not paths:
            table.add_row("--", "Ketik path manual di bawah", "--", "--")
            return
        for i, path in enumerate(paths[:30], start=1):
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            label = path.name if len(path.name) <= 34 else (
                path.name[:15] + "..." + path.name[-15:]
            )
            table.add_row(str(i), label, media_tag(path), fmt_size(size))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter":
            needle = event.value.strip().lower()
            all_paths = getattr(self, "_all_sources", [])
            if not needle:
                self._fill_table(all_paths)
            else:
                self._fill_table([p for p in all_paths if needle in p.name.lower()])
        elif event.input.id == "manual":
            self._check_manual(event.value.strip())

    def _check_manual(self, manual: str) -> None:
        status = self.query_one("#manual-status", Static)
        if not manual:
            status.update("")
            return
        p = Path(manual)
        if p.is_file() and core.is_supported_source(p):
            status.update("[OK] file ditemukan dan tipe didukung")
        elif p.is_file():
            status.update("[!!] file ada tapi ekstensi tidak dikenal")
        else:
            status.update("[!!] file belum ditemukan, cek path")

    def _visible_paths(self) -> list[Path]:
        table = self.query_one("#sources", DataTable)
        needle = self.query_one("#filter", Input).value.strip().lower()
        all_paths = getattr(self, "_all_sources", [])
        if not needle:
            return list(all_paths)
        return [p for p in all_paths if needle in p.name.lower()]

    def _go_next(self) -> None:
        from __main__ import get_app_state

        state = get_app_state()
        manual = self.query_one("#manual", Input).value.strip()
        if manual:
            state.source = Path(manual)
        else:
            visible = self._visible_paths()
            pool = visible if visible else state.sources
            if not pool:
                return
            table = self.query_one("#sources", DataTable)
            row = table.cursor_row if table.cursor_row is not None else 0
            state.source = pool[min(row, len(pool) - 1)]
        if state.source is None:
            return
        self.app.push_screen(ConfirmScreen())

    def action_next(self) -> None:
        self._go_next()

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next":
            self._go_next()
        else:
            self.app.pop_screen()


class ConfirmScreen(Screen):
    """(3) summary + 1-klik tukar (tanpa ketik TUKAR)."""

    BINDINGS = [
        ("enter", "go", "Tukar"),
        ("escape", "back", "Kembali"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(render_stepper(3), id="stepper")
        yield Label("STEP 3 DARI 3 - CEK", id="pill")
        yield Label("Ringkasan - cek sekali sebelum tukar", id="title")
        yield Label("Pastikan target dan sumber sudah benar.", id="subtitle")
        with Horizontal():
            yield Static("", id="target-card")
            yield Static("", id="source-card")
        yield Static("", id="mode-banner", classes="card")
        yield Static("", id="warn-card", classes="card-warn")
        yield Checkbox("Preview saja (dry-run, tidak ubah file)", id="preview")
        with Horizontal():
            yield Button("< Kembali", id="back")
            yield Button("TUKAR SEKARANG", id="go", variant="success")
        yield Label(CREDIT_TEXT, id="credit")
        yield Footer()

    def on_mount(self) -> None:
        from __main__ import get_app_state

        state = get_app_state()
        self.query_one("#preview", Checkbox).value = not state.apply_mode
        self._refresh()
        try:
            self.query_one("#go", Button).focus()
        except Exception:
            pass

    def _refresh(self) -> None:
        from __main__ import get_app_state

        state = get_app_state()
        plan = core.build_encode_plan(state.channels)
        preview = self.query_one("#preview", Checkbox).value
        channels = "mono" if state.channels == 1 else "stereo beta"

        if state.target is not None:
            t = state.target
            opus = "[OK] opus pendamping ada" if t.opus_path else "[--] tanpa opus"
            self.query_one("#target-card", Static).update(
                "TARGET\n"
                f"{t.short_name}\n"
                f"{fmt_dur(t.approx_duration_sec)}, {fmt_size(t.length)}\n"
                f"{opus}"
            )
        else:
            self.query_one("#target-card", Static).update("TARGET\n--")

        if state.source is not None:
            s = state.source
            try:
                size = s.stat().st_size if s.is_file() else 0
            except OSError:
                size = 0
            pattern = "pola dihitung saat proses berjalan"
            if state.target is not None:
                try:
                    raw = state.target.data_path.read_bytes()
                    pattern = wave_preview(list(raw))
                except OSError:
                    pattern = "pola target tidak terbaca"
            self.query_one("#source-card", Static).update(
                "SUMBER\n"
                f"{s.name}\n"
                f"{media_tag(s)}, {fmt_size(size)}\n"
                f"Pola target: {pattern}"
            )
        else:
            self.query_one("#source-card", Static).update("SUMBER\n--")

        banner = self.query_one("#mode-banner", Static)
        if preview:
            banner.update(
                f"Mode: PREVIEW - tidak ubah file\n"
                f"Resep: opus {plan.bitrate} {plan.application} {channels}"
            )
            banner.set_classes(["card-info"])
        else:
            banner.update(
                "Mode: TULIS LANGSUNG + backup .bak otomatis\n"
                f"Resep: opus {plan.bitrate} {plan.application} {channels}"
            )
            banner.set_classes(["card-danger"])

        warn = self.query_one("#warn-card", Static)
        warn.display = False
        if state.target is not None and state.source is not None:
            try:
                if state.source.is_file():
                    src_size = state.source.stat().st_size
                    # Rough heuristic: large source vs tiny sidecar target.
                    if src_size > 0 and state.target.length > 0:
                        ratio = src_size / max(1, state.target.length * 1024)
                        if ratio > 20:
                            warn.update(
                                "[!!] Sumber jauh lebih besar dari target. "
                                "Audio akan dipadatkan ke sidecar target."
                            )
                            warn.display = True
            except OSError:
                pass

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        from __main__ import get_app_state

        state = get_app_state()
        state.apply_mode = not event.value
        self._refresh()

    def _go(self) -> None:
        from vnswap_ui_run import RunScreen

        self.app.push_screen(RunScreen())

    def action_go(self) -> None:
        self._go()

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "go":
            self._go()
        else:
            self.app.pop_screen()
