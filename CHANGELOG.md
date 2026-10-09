# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.2.0] — Professional pack

### Added

- `LICENSE` (MIT).
- `pyproject.toml` + `requirements.txt` with a pinned `textual>=8,<9` range.
- `--version` flag on `vnswap.py` and `vnswap-web`.
- `CHANGELOG.md`, `CONTRIBUTING.md`, bug-report and feature-request issue templates.
- `pytest` suite for `vnswap_core` (`tests/test_core.py`) and GitHub Actions CI on Python 3.10–3.13.
- Token auth for the web server: auto-generated token when binding a
  non-loopback `--host` (e.g. `0.0.0.0`), `--token` to set your own,
  `--no-auth` to opt out explicitly. All `/api/*` endpoints enforce it.
- `version` and `auth` fields in `GET /api/health`.

## [1.1.0] — Web interface

### Added

- Interactive web UI (`python vnswap.py --web`): same 4-step wizard as the TUI
  (Target → Source → Confirm → Process) with live progress, waveform canvas
  preview, drag-drop upload, and one-click rollback.
- `vnswap_web.py`: stdlib-only HTTP server + JSON API; background jobs reuse
  `vnswap_core` so encode/sidecar/swap behavior matches the TUI exactly.

## [1.0.0] — Initial release

### Added

- Fullscreen Textual TUI wizard (Target → Source → Confirm → Process).
- `--cli` text-mode fallback when Textual is not installed.
- WhatsApp Opus encode recipe (mono 32k voip + fallbacks, stereo 64k beta),
  20 bars/second visualization sidecar, atomic swap with `.bak-timestamp`
  backup plus automatic and one-click rollback.
- Preview (dry-run) mode.
