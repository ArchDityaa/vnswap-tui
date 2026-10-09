# Contributing to vnswap-tui

## Setup (Termux or any Python 3.10+ machine)

```bash
pkg install python ffmpeg git -y   # Termux only
pip install -r requirements.txt
pip install pytest                 # for tests
termux-setup-storage               # Termux only
```

## Running

```bash
python vnswap.py           # fullscreen TUI
python vnswap.py --cli     # text mode, no Textual needed
python vnswap.py --web     # web UI at http://127.0.0.1:8000/
python vnswap.py --version # print version
```

## Tests

```bash
pytest -q
```

`vnswap_core.py` is stdlib-only by design, so the suite runs anywhere —
no Textual, no ffmpeg required (ffmpeg-dependent paths are skipped when the
binary is absent). New logic in `vnswap_core` must come with tests.

## Code rules

- `vnswap_core.py` and `vnswap_web.py`: **stdlib only**. No third-party imports.
- UI strings: Indonesian, ASCII-only status markers (`[OK]`, `[--]`, `[!!]`,
  `[XX]`), no emoji — the app targets Termux terminals.
- Theme is dark-only; web changes must reuse the Dark Pro tokens in
  `web/styles.css` (same values as `vnswap_ui_nav.py`).
- The web backend must keep behavior identical to the TUI by reusing
  `vnswap_core` — never reimplement encode/sidecar/swap logic.
- Update `CHANGELOG.md` under `[Unreleased]` for any user-visible change.

## Releases

Maintainers tag releases from `main`:

```bash
git tag -a vX.Y.Z -m "vnswap-tui vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file CHANGELOG.md
```

Bump `VERSION` in `vnswap_core.py` and `version` in `pyproject.toml` together.
