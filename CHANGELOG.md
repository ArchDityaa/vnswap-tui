# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.4.1] — 2026-10-09

### Fixed

- Web tidak menampilkan target padahal TUI bisa: tiga akar masalah di
  lapisan HTTP/JS, bukan di deteksi — (1) error API ditelan diam-diam
  oleh frontend, (2) `OSError` saat pemindaian memutus koneksi tanpa
  respons JSON, (3) browser bisa menyajikan `app.js` basi karena file
  statis tanpa header cache.
- `GET /api/health`, `/api/targets`, `/api/shared-candidates` kini
  mengembalikan JSON error (HTTP 500) saat pemindaian gagal, bukan
  koneksi putus.
- File statis (`/`, `/app.js`, `/styles.css`) memakai
  `Cache-Control: no-store` agar update selalu sampai ke browser.
- `loadTargets()` menampilkan pesan `[XX] gagal memuat target: ...`
  langsung di tabel; tombol Rescan ikut memuat ulang kandidat.

### Added

- `GET /api/diagnostics`: platform, cwd, nilai `VNSWAP_SHARED`,
  `shared_dir` terpilih, status ada/tidaknya, semua kandidat +
  jumlah target, `scan_error`, ffmpeg, dan status auth — untuk
  melacak kenapa deteksi gagal di perangkat tertentu. Buka
  `http://127.0.0.1:8000/api/diagnostics` di browser HP.
- Versi aplikasi tampil di footer web (`vX.Y.Z`) agar mudah tahu
  apakah browser memuat kode terbaru.

## [1.4.0] — 2026-10-09

### Fixed

- `.Shared` auto-detection: the hardcoded `999`/`1006` path failed on any
  other device. The server now probes `$VNSWAP_SHARED`, the default, and
  every account/user number variant, then uses the folder with the most
  voice notes. `--shared` (or the UI picker) still overrides; a missing
  explicit path is kept so errors stay visible.

### Added

- `GET /api/shared-candidates`: ranked `.Shared` folders with target
  counts; the web UI shows them in a dropdown next to the manual path
  field, plus `shared_auto` in `/api/health`.
- Catppuccin Mocha web theme (dark only): mauve accent, green primary
  action, tinted status banners, roomier cards, larger mobile tap targets.
  The TUI keeps its Dark Pro theme.
- `tests/test_shared.py`: auto-detection unit tests; candidates endpoint
  covered in `tests/test_web.py`.

## [1.3.0] — 2026-10-09

### Added

- Source waveform preview: `GET /api/preview` decodes the source and returns
  its bars resampled to the target length; the Confirm step draws target and
  source canvases side by side with a bar-count/duration summary.
- In-browser audio preview: `GET /api/audio` serves target `.opus` and source
  files with HTTP Range support; the Confirm step has players for both
  (`<video>` is used automatically for video sources).
- `tests/test_web.py`: live-server tests for health, audio (full/range/404),
  preview validation and computation, and token gating.

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
