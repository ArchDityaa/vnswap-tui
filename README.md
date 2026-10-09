# vnswap-tui

Swap WhatsApp voice notes directly from Termux. Fully on-device — no website, no upload.

Built with Python, Textual (dark fullscreen TUI), and ffmpeg.

## Quick Start

Already cloned, just open the TUI:

```bash
python vnswap.py
```

Fresh Termux, copy-paste once — installs dependencies, clones the repo, grants storage access, then opens the TUI:

```bash
pkg install python ffmpeg git -y && pip install textual && git clone https://github.com/ArchDityaa/vnswap-tui && cd vnswap-tui && termux-setup-storage && python vnswap.py
```

## Why vnswap

WhatsApp stores voice notes as paired files (`.opus` audio + `.data` visualization sidecar). vnswap replaces both atomically: it re-encodes any audio/video source into a compatible Opus stream and regenerates the 20 bars/second visualization, so the swapped note plays natively in WhatsApp.

Conversion logic mirrors the web implementation:

- `src/lib/ffmpeg.ts` → `vnswap_core.py` (encode plan)
- `src/lib/waveform.ts` → 20 bars/second visualization curve
- `src/lib/package.ts` → base-name pairing rules

## Features

- Fullscreen guided wizard (Target → Source → Confirm → Process)
- Text-mode fallback (`--cli`) when Textual is not installed
- One-click swap — no typed confirmation required
- Automatic `.bak-timestamp` backup of both files before writing
- Atomic write per file via `os.replace`, with automatic + one-click rollback
- Live progress: encode, sidecar generation, backup, swap
- Preview (dry-run) mode that simulates the full pipeline without touching files
- Web UI (`--web`, stdlib-only, no Textual needed): same 4-step wizard in the
  browser with live progress, waveform canvas preview, drag-drop upload,
  and one-click rollback
- Smart defaults: newest target pre-selected, so three `Enter` presses complete a swap
- Manual path input with file-type validation
- Termux-safe: ASCII-only status markers (`[OK]`, `[--]`, `[!!]`, `[XX]`), no emoji

## Requirements

- Android with Termux
- Python 3.10+
- ffmpeg (Termux package)
- Textual 8.x (Python package, for fullscreen TUI only)

## Installation

Run once in Termux:

```bash
pkg install python ffmpeg -y
pip install textual
termux-setup-storage
```

> `textual` is a Python (PyPI) package — install with `pip`, not `pkg`.
> `pkg install textual` will always fail with `Unable to locate package`.

Then clone this repository:

```bash
gh repo clone ArchDityaa/vnswap-tui
cd vnswap-tui
```

## Usage

```bash
python vnswap.py                         # fullscreen TUI (recommended)
python vnswap.py --cli                   # text mode, no Textual required
python vnswap.py --web                   # web UI at http://127.0.0.1:8000/
python vnswap.py --web --port 8080       # custom port (Termux: use --host 0.0.0.0 for LAN)
python vnswap.py --dry-run               # preview only, files untouched
python vnswap.py --stereo                # stereo beta (default: mono)
python vnswap.py --shared /path/.Shared  # custom shared folder
```

| Mode | Confirmation | Effect |
|------|--------------|--------|
| Default (TUI / CLI) | `Enter` / `TUKAR SEKARANG` | Writes immediately, `.bak` backup automatic |
| Preview (`Preview saja` / `--dry-run`) | Same, no write | Full simulation, files untouched |

The legacy `--apply` flag is still accepted but no longer needed — direct write is now the default.

## Workflow

```text
STEP 1/3  TARGET    Select the newest Visualization.data (Enter)
STEP 2/3  SOURCE    Pick audio/video from the list or type a path (Enter)
STEP 3/3  CONFIRM   Review the summary cards, press TUKAR SEKARANG (Enter)
PROCESS             Encode → 20 bars/s sidecar → .bak backup → atomic swap
```

Keyboard shortcuts:

| Key | Action |
|-----|--------|
| `Enter` | Continue / swap |
| `R` | Rescan targets |
| `Esc` | Back |
| `Up` / `Down` | Move selection |

Notes:

- Long filenames are middle-truncated (`abc12...xyz.data`) for readability.
- Each step defaults to the newest item, so minimal navigation is required.

## Safety guarantees

1. Both files (`.opus` + `.data`) are backed up as `.bak-timestamp` before any write.
2. Each file is written atomically with `os.replace` — no half-written state.
3. On failure: automatic restore plus a one-click **Rollback** button on the Process screen.

## Project structure

| File | Contents |
|------|----------|
| `vnswap.py` | Entrypoint, app state, CLI fallback, shared pipeline, `--web` launcher |
| `vnswap_core.py` | Pure logic (stdlib only — testable anywhere): detection, encode plan, visualization, atomic swap |
| `vnswap_ui_nav.py` | Dark Pro theme + Target / Source / Confirm screens |
| `vnswap_ui_run.py` | Process screen + asyncio worker (progress, log, result) |
| `vnswap_web.py` | Web server (stdlib-only `http.server` + JSON API + background jobs) |
| `web/index.html` | Web wizard markup (Target → Source → Confirm → Process) |
| `web/styles.css` | Dark Pro theme for the web (same tokens as the TUI) |
| `web/app.js` | Web client (fetch + polling, waveform canvas, upload, rollback) |

## Web interface

For users who prefer not to use the terminal UI:

```bash
python vnswap.py --web
# open http://127.0.0.1:8000/ in the browser
```

Feature parity with the TUI: target auto-detect + rescan + filter, source
auto-discover + filter + drag-drop upload + manual server path, confirm cards
with waveform preview + preview/write toggle + mono/stereo recipe + oversize
warning, then live process view (4 stages, progress bar, log, result card,
rollback). No third-party packages — `vnswap_web.py` uses only the stdlib and
reuses `vnswap_core` for encode/sidecar/swap, so behavior matches the TUI
exactly. On Termux, expose to the LAN with `python vnswap.py --web --host 0.0.0.0`.

## Supported sources

Audio: `mp3 m4a aac wav ogg oga opus flac weba`
Video: `webm mp4 m4v mov mkv 3gp`

Anything ffmpeg can decode is attempted; unsupported extensions warn but still try the encode chain (main + fallbacks).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ffmpeg tidak ditemukan` | `pkg install ffmpeg -y` |
| `textual belum terinstall` | `pip install textual`, or use `--cli` |
| No targets found | Play one voice note in WhatsApp first, then `R` (Rescan) |
| Encode always fails | Verify the source file opens; try `--dry-run` to isolate |

## License

Private project — all rights reserved unless a `LICENSE` file is added.

---

Developed by hakiraadityaa.
