# Catatan Perubahan

Semua perubahan penting pada proyek ini didokumentasikan di sini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
penomoran versi mengikuti [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.9.0] — 2026-10-09

### Ditambahkan

- PWA "instal ke layar utama": `manifest.webmanifest` (standalone,
  tema gelap, ikon 192/512 + maskable), ikon `apple-touch-icon`,
  dan `sw.js` yang meng-cache kerangka aplikasi untuk buka offline —
  `/api/*` selalu lewat jaringan. Buka sekali di browser HP lalu
  "Add to Home screen" / "Instal aplikasi".
- `tests/test_pwa.py`: validasi manifest, tautan HTML/registrasi SW,
  jaminan SW tak meng-cache API, dan rute statis PWA di server.

## [1.8.0] — 2026-10-09

### Ditambahkan

- Pemeriksaan kesehatan awal: `vnswap_core.check_health()` memverifikasi
  ffmpeg, folder `.Shared` (ada/baca/tulis), izin penyimpanan Termux,
  target voice-note, folder media, Textual, dan Python — masing-masing
  dengan perintah perbaikan siap salin-tempel.
- Subcommand baru `vnswap health` mencetak laporan lengkap (kode kembali
  1 bila ada yang gagal); CLI dan web mencetak ringkasan masalah saat
  startup; TUI menampilkan banner peringatan di layar Target; web
  menampilkan banner di atas wizard via `checks` baru di `/api/health`.

### Diubah

- Tema web Catppuccin disempurnakan (tetap Mocha, hanya gelap): satu aksen
  mauve untuk aksi primer (`--primary`), tombol primer tak lagi hijau;
  border kartu/table dipertegas (`surface1`), radius 18px ke 14px; teks
  sekunder lebih terang untuk keterbacaan; banner kesehatan jadi daftar
  terstruktur dengan perintah perbaikan dalam `<code>` + tombol Salin;
  pill health tidak lagi terpotong di layar sempit.

## [1.7.1] — 2026-10-09

### Diperbaiki

- Overflow horizontal di HP: path panjang di footer kini wrap
  (`overflow-wrap` + `word-break`) dan body memakai `overflow-x: clip`
  sebagai pengaman tanpa merusak sticky header.

## [1.7.0] — 2026-10-09

### Diubah

- Rombak tampilan web mobile-first (palet Catppuccin Mocha tetap): header
  ramping menempel dengan blur, stepper segmen 4 kolom menempel, daftar
  target/sumber jadi kartu di layar kecil (tabel kembali di layar besar),
  tombol aksi menempel di bawah tiap kartu, input 16px agar tidak zoom
  otomatis, area sentuh min 48px, lipatan folder .Shared yang terbuka
  otomatis bila tidak terdeteksi, waveform tajam (DPR) dengan warna
  mauve/teal dan digambar ulang saat rotasi layar.

## [1.6.0] — 2026-10-09

### Ditambahkan

- Perintah `vnswap`: ketik `vnswap` untuk TUI, `vnswap web` untuk server web,
  `vnswap update` untuk update ke versi terbaru dari GitHub (subcommand
  `tui`/`cli`/`web`/`update`; flag lama `--web`/`--cli` tetap jalan).
- `vnswap update --check`: cek update saja tanpa download (kode kembali 2
  bila ada update). Update batal otomatis bila ada perubahan lokal.
- `install.sh`: instal Termux sekali jalan (dependensi + clone + launcher
  `$PREFIX/bin/vnswap` sehingga `vnswap` bisa diketik dari mana saja).
- `tests/test_update.py`: tes resolusi mode dan update via repo git sementara.

## [1.5.1] — 2026-10-09

### Diperbaiki

- URL web yang tercetak tak bisa dibuka di mode LAN: terminal mencetak
  `http://0.0.0.0:...` (alamat bind, ditolak browser) sehingga web tampak
  "tidak work" padahal server jalan. Kini dicetak URL siap-buka: loopback
  plus tiap IP LAN perangkat (terdeteksi via routing lokal, tanpa kirim
  paket), token tersemat otomatis, plus URL `/api/diagnostics`.
- Port bentrok tak lagi traceback: konflik bind menghasilkan pesan ramah
  `[XX] port ... sudah dipakai ... --port lain` dan exit code 1.
- Panduan Termux baru di Pemecahan Masalah: `termux-wake-lock` agar Android
  tak mematikan server saat pindah ke browser, wajib ketik `http://` lengkap,
  dan cara pakai token di mode LAN.

### Ditambahkan

- `lan_ips()` dan `access_urls()` di `vnswap_web.py` beserta suite
  `tests/test_net.py` (URL loopback/LAN, anti-`0.0.0.0`, konflik port).

## [1.5.0] — 2026-10-09

### Diubah

- Seluruh repo diterjemahkan ke Bahasa Indonesia: string UI TUI/CLI/web
  (LANGKAH, Pindai Ulang, Durasi, Ukuran, Unggah, "dikembangkan oleh
  hakiraadityaa"), pesan error `vnswap_core`, komentar dan docstring kode,
  README, CHANGELOG, CONTRIBUTING, dan template issue. Identifier kode,
  endpoint API, key JSON, dan marker status tidak berubah.

## [1.4.1] — 2026-10-09

### Diperbaiki

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
  langsung di tabel; tombol Pindai Ulang ikut memuat ulang kandidat.

### Ditambahkan

- `GET /api/diagnostics`: platform, cwd, nilai `VNSWAP_SHARED`,
  `shared_dir` terpilih, status ada/tidaknya, semua kandidat +
  jumlah target, `scan_error`, ffmpeg, dan status auth — untuk
  melacak kenapa deteksi gagal di perangkat tertentu. Buka
  `http://127.0.0.1:8000/api/diagnostics` di browser HP.
- Versi aplikasi tampil di footer web (`vX.Y.Z`) agar mudah tahu
  apakah browser memuat kode terbaru.

## [1.4.0] — 2026-10-09

### Diperbaiki

- Deteksi otomatis `.Shared`: path hardcoded `999`/`1006` gagal di perangkat
  lain. Server kini memindai `$VNSWAP_SHARED`, default, dan
  setiap varian nomor akun/pengguna, lalu memakai folder dengan voice
  note terbanyak. `--shared` (atau pemilih di UI) tetap mengesampingkan;
  path eksplisit yang hilang tetap disimpan agar error tetap terlihat.

### Ditambahkan

- `GET /api/shared-candidates`: folder `.Shared` berperingkat beserta jumlah
  target; UI web menampilkannya dalam dropdown di samping kolom path manual,
  serta `shared_auto` di `/api/health`.
- Tema web Catppuccin Mocha (hanya gelap): aksen mauve, aksi primer hijau,
  banner status berwarna, kartu lebih lega, target ketuk mobile lebih besar.
  TUI tetap memakai tema Dark Pro.
- `tests/test_shared.py`: unit tes deteksi otomatis; endpoint kandidat
  tercakup di `tests/test_web.py`.

## [1.3.0] — 2026-10-09

### Ditambahkan

- Pratinjau waveform sumber: `GET /api/preview` men-decode sumber dan mengembalikan
  bar-nya yang di-resample ke panjang target; langkah Konfirmasi menggambar kanvas
  target dan sumber berdampingan beserta ringkasan jumlah bar/durasi.
- Pratinjau audio di browser: `GET /api/audio` menyajikan `.opus` target dan file
  sumber dengan dukungan HTTP Range; langkah Konfirmasi memiliki pemutar untuk keduanya
  (`<video>` dipakai otomatis untuk sumber video).
- `tests/test_web.py`: tes live-server untuk health, audio (penuh/range/404),
  validasi dan komputasi preview, serta token gating.

## [1.2.0] — Paket profesional

### Ditambahkan

- `LICENSE` (MIT).
- `pyproject.toml` + `requirements.txt` dengan rentang `textual>=8,<9` yang dipin.
- Flag `--version` pada `vnswap.py` dan `vnswap-web`.
- `CHANGELOG.md`, `CONTRIBUTING.md`, template laporan-bug dan permintaan-fitur.
- Suite `pytest` untuk `vnswap_core` (`tests/test_core.py`) dan CI GitHub Actions pada Python 3.10–3.13.
- Token auth untuk server web: token dibuat otomatis saat binding
  `--host` non-loopback (mis. `0.0.0.0`), `--token` untuk mengatur milik sendiri,
  `--no-auth` untuk keluar secara eksplisit. Semua endpoint `/api/*` menegakkannya.
- Kolom `version` dan `auth` di `GET /api/health`.

## [1.1.0] — Antarmuka web

### Ditambahkan

- UI web interaktif (`python vnswap.py --web`): wizard 4 langkah yang sama seperti TUI
  (Target → Sumber → Konfirmasi → Proses) dengan progres langsung, pratinjau kanvas
  waveform, unggah seret-letakkan, dan rollback sekali klik.
- `vnswap_web.py`: server HTTP hanya-stdlib + JSON API; job latar memakai ulang
  `vnswap_core` sehingga perilaku encode/sidecar/swap sama persis dengan TUI.

## [1.0.0] — Rilis awal

### Ditambahkan

- Wizard TUI Textual layar penuh (Target → Sumber → Konfirmasi → Proses).
- Fallback mode teks `--cli` saat Textual tidak terpasang.
- Resep encode Opus WhatsApp (mono 32k voip + fallback, stereo 64k beta),
  sidecar visualisasi 20 bar/detik, swap atomik dengan backup `.bak-timestamp`
  serta rollback otomatis dan sekali klik.
- Mode pratinjau (dry-run).
