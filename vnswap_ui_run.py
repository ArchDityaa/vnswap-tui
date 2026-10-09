"""Layar proses untuk vnswap: encode -> sidecar -> swap dengan progres.

Tanpa emoji. Tahap memakai [x] selesai, [>] aktif, [ ] antre, [!] gagal.
Level log: [info], [ok], [warn], [error].
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

try:
    from textual.containers import Horizontal
    from textual.screen import Screen
    from textual.widgets import Button, Footer, Header, Label, Log, ProgressBar, Static
    from textual.app import ComposeResult
    TEXTUAL_OK = True
except ImportError:
    TEXTUAL_OK = False
    Horizontal = Screen = Button = Footer = Header = Label = Log = ProgressBar = Static = object  # type: ignore
    ComposeResult = object  # type: ignore

import vnswap_core as core

try:
    from vnswap_ui_nav import CREDIT_TEXT
except ImportError:
    CREDIT_TEXT = "dikembangkan oleh hakiraadityaa"


STAGE_LABELS = [
    "Encode opus",
    "Visual 20 bar per detik",
    "Backup .bak",
    "Tukar atomik",
]


def _stage_text(states: list[str]) -> str:
    marks = {"done": "[x]", "active": "[>]", "todo": "[ ]", "fail": "[!]"}
    lines = ["Tahap:"]
    for label, st in zip(STAGE_LABELS, states):
        lines.append(f"  {marks.get(st, '[ ]')} {label}")
    return "\n".join(lines)


class RunScreen(Screen):
    """(4) encode -> sidecar -> backup -> swap dengan progres langsung."""

    BINDINGS = [
        ("escape", "back", "Kembali"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        try:
            from vnswap_ui_nav import render_stepper
            yield Label(render_stepper(4), id="stepper")
        except ImportError:
            pass
        yield Label("LANGKAH PROSES - KONVERSI DAN PENUKARAN", id="pill")
        yield Label("Proses - encode, visualisasi, lalu tukar", id="title")
        yield Label("Backup .bak dibuat otomatis sebelum tulis.", id="subtitle")
        yield Static(_stage_text(["todo", "todo", "todo", "todo"]), id="stages")
        with Horizontal():
            yield ProgressBar(total=100, show_eta=False, id="bar")
            yield Static("0%", id="percent")
        yield Log(id="log", highlight=True)
        yield Static("", id="result-card")
        with Horizontal():
            yield Button("Rollback", id="rollback", disabled=True)
            yield Button("Selesai", id="done", disabled=True)
        yield Label(CREDIT_TEXT, id="credit")
        yield Footer()

    def on_mount(self) -> None:
        self._stages: list[str] = ["todo", "todo", "todo", "todo"]
        self.query_one("#result-card", Static).display = False
        self.run_worker(self._run(), exclusive=True)

    def _paint_stages(self) -> None:
        try:
            self.query_one("#stages", Static).update(_stage_text(self._stages))
        except Exception:
            pass

    def _set_stage(self, idx: int, value: str) -> None:
        if 0 <= idx < len(self._stages):
            self._stages[idx] = value
            self._paint_stages()

    async def _run(self) -> None:
        from __main__ import get_app_state

        state = get_app_state()
        log = self.query_one("#log", Log)
        bar = self.query_one("#bar", ProgressBar)
        try:
            percent = self.query_one("#percent", Static)
        except Exception:
            percent = None

        def step(pct: int, msg: str, level: str = "info") -> None:
            try:
                bar.update(progress=pct)
            except Exception:
                pass
            if percent is not None:
                try:
                    percent.update(f"{max(0, min(100, pct))}%")
                except Exception:
                    pass
            log.write_line(f"[{level}] {msg}")

        self._paint_stages()

        assert state.target is not None and state.source is not None
        ffmpeg = core.find_ffmpeg()
        if not ffmpeg:
            self._set_stage(0, "fail")
            step(0, "ffmpeg tidak ditemukan - pkg install ffmpeg dulu.", "error")
            self._show_result(
                "[XX] ffmpeg tidak ditemukan.\n"
                "Pasang dengan: pkg install ffmpeg\n"
                "Lalu ulangi dari layar Target.",
                error=True,
            )
            self._finish(False)
            return
        plan = core.build_encode_plan(state.channels)
        last_result: core.SwapResult | None = None
        try:
            with tempfile.TemporaryDirectory(prefix="vnswap-") as tmpdir:
                out = Path(tmpdir) / "converted.ogg"
                converted: bytes | None = None
                self._set_stage(0, "active")
                for idx, argv in enumerate(plan.args_list):
                    if state.cancelled:
                        step(0, "dibatalkan.", "warn")
                        self._set_stage(0, "fail")
                        self._finish(False)
                        return
                    cmd = [
                        str(state.source) if a == "{in}"
                        else str(out) if a == "{out}" else a
                        for a in [ffmpeg, "-hide_banner", "-y", *argv]
                    ]
                    tag = "utama" if idx == 0 else f"fallback {idx}"
                    step(5 + idx * 10, f"encode {tag} berjalan...", "info")
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await proc.communicate()
                    if proc.returncode == 0 and out.exists():
                        converted = out.read_bytes()
                        self._set_stage(0, "done")
                        step(40, f"encode {tag} ok ({len(converted)} bytes).", "ok")
                        break
                    step(5 + idx * 10, "encode gagal, coba berikutnya...", "warn")
                if not converted:
                    self._set_stage(0, "fail")
                    step(0, "semua percobaan encode gagal.", "error")
                    self._show_result(
                        "[XX] Semua percobaan encode gagal.\n"
                        "Cek file sumber masih bisa dibuka dan ffmpeg valid.",
                        error=True,
                    )
                    self._finish(False)
                    return
                vendor = core.read_opus_vendor(converted)
                step(45, f'vendor tag: "{vendor or "tak terbaca"}".', "info")
                self._set_stage(1, "active")
                step(55, "decode dan hitung visualisasi 20 bar per detik...", "info")
                samples, duration = await asyncio.to_thread(
                    core.decode_pcm_mono, ffmpeg, state.source
                )
                bars = await asyncio.to_thread(
                    core.compute_vis_from_samples,
                    samples, 48000, duration or 1.0,
                )
                sidecar = core.clamp_sidecar(bars, state.target.length)
                self._set_stage(1, "done")
                step(70, f"sidecar {len(sidecar)} bytes "
                         f"(target {state.target.length}).", "ok")
                self._set_stage(2, "active")
                self._set_stage(3, "active")
                last_result = core.atomic_swap(
                    converted, sidecar, state.target,
                    dry_run=not state.apply_mode,
                )
                self._last = last_result
                self._set_stage(2, "done")
                self._set_stage(3, "done")
                if state.apply_mode:
                    step(100, f"TERTUKAR: {last_result.opus_path.name} + "
                              f"{last_result.data_path.name} "
                              "(backup .bak tersimpan).", "ok")
                    lines = [
                        "[OK] TERTUKAR: "
                        f"{last_result.opus_path.name} + {last_result.data_path.name}",
                        f"Backup opus: {last_result.backup_opus or '--'}",
                        f"Backup data: {last_result.backup_data or '--'}",
                        "Buka WhatsApp dan putar VN untuk verifikasi.",
                    ]
                    self._show_result("\n".join(lines), error=False)
                else:
                    step(100, "PREVIEW selesai - tidak ada file diubah.", "info")
                    self._show_result(
                        "[OK] PREVIEW selesai - tidak ada file diubah.\n"
                        "Matikan Preview saja untuk tulis langsung.",
                        error=False,
                    )
                self.query_one("#rollback", Button).disabled = (
                    last_result.backup_opus is None
                )
                self._finish(True)
        except Exception as exc:
            self._set_stage(3, "fail")
            step(0, f"gagal: {exc}", "error")
            if last_result is not None:
                core.restore_backup(last_result)
                step(0, "backup dikembalikan (rollback).", "warn")
            self._show_result(f"[XX] gagal: {exc}", error=True)
            self._finish(False)

    def _show_result(self, text: str, error: bool) -> None:
        try:
            card = self.query_one("#result-card", Static)
            card.update(text)
            card.display = True
            card.set_classes(["card-danger"] if error else ["card-info"])
        except Exception:
            pass

    def _finish(self, _ok: bool) -> None:
        try:
            self.query_one("#done", Button).disabled = False
            self.query_one("#done", Button).focus()
        except Exception:
            pass

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rollback":
            last = getattr(self, "_last", None)
            if last is not None:
                core.restore_backup(last)
                self.query_one("#log", Log).write_line(
                    "[warn] rollback selesai - file asli dikembalikan."
                )
        else:
            if not self.query_one("#done", Button).disabled:
                self.app.pop_screen()
