# vnswap-tui

![CI](https://github.com/ArchDityaa/vnswap-tui/actions/workflows/ci.yml/badge.svg)

Tukar voice note WhatsApp langsung dari Termux. Sepenuhnya di perangkat — tanpa situs web, tanpa unggah.

Dibangun dengan Python, Textual (TUI gelap layar penuh), dan ffmpeg.

## Mulai Cepat

Sudah clone, tinggal buka TUI:

```bash
python vnswap.py
```

Termux baru, cukup salin-tempel sekali — memasang dependensi, meng-clone repo, memberi akses penyimpanan, lalu membuka TUI:

```bash
pkg install python ffmpeg git -y && pip install textual && git clone https://github.com/ArchDityaa/vnswap-tui && cd vnswap-tui && termux-setup-storage && python vnswap.py
```

## Mengapa vnswap

WhatsApp menyimpan voice note sebagai file berpasangan (audio `.opus` + sidecar visualisasi `.data`). vnswap mengganti keduanya secara atomik: me-re-encode sumber audio/video apa pun menjadi stream Opus yang kompatibel dan membuat ulang visualisasi 20 bar/detik, sehingga note hasil swap diputar secara native di WhatsApp.

Logika konversi mengikuti implementasi web:

- `src/lib/ffmpeg.ts` → `vnswap_core.py` (rencana encode)
- `src/lib/waveform.ts` → kurva visualisasi 20 bar/detik
- `src/lib/package.ts` → aturan pasangan nama dasar

## Fitur

- Wizard terpandu layar penuh (Target → Sumber → Konfirmasi → Proses)
- Fallback mode teks (`--cli`) saat Textual tidak terpasang
- Swap sekali klik — tanpa perlu mengetik konfirmasi
- Backup otomatis `.bak-timestamp` untuk kedua file sebelum menulis
- Penulisan atomik per file via `os.replace`, dengan rollback otomatis + sekali klik
- Progres langsung: encode, pembuatan sidecar, backup, swap
- Mode pratinjau (dry-run) yang mensimulasikan seluruh alur tanpa menyentuh file
- UI Web (`--web`, hanya-stdlib, tanpa perlu Textual): wizard 4 langkah yang sama di
  browser dengan progres langsung, pratinjau kanvas waveform, unggah seret-letakkan,
  dan rollback sekali klik
- Default cerdas: target terbaru sudah terpilih, jadi tiga kali tekan `Enter` menyelesaikan swap
- Input path manual dengan validasi tipe file
- Aman untuk Termux: marker status ASCII saja (`[OK]`, `[--]`, `[!!]`, `[XX]`), tanpa emoji

## Persyaratan

- Android dengan Termux
- Python 3.10+
- ffmpeg (paket Termux)
- Textual 8.x (paket Python, hanya untuk TUI layar penuh)

## Instalasi

Jalankan sekali di Termux:

```bash
pkg install python ffmpeg -y
pip install textual
termux-setup-storage
```

> `textual` adalah paket Python (PyPI) — pasang dengan `pip`, bukan `pkg`.
> `pkg install textual` akan selalu gagal dengan `Unable to locate package`.

Lalu clone repositori ini:

```bash
gh repo clone ArchDityaa/vnswap-tui
cd vnswap-tui
```

## Penggunaan

```bash
python vnswap.py                         # TUI layar penuh (disarankan)
python vnswap.py --cli                   # mode teks, tanpa perlu Textual
python vnswap.py --web                   # UI web di http://127.0.0.1:8000/
python vnswap.py --web --port 8080       # port kustom (Termux: pakai --host 0.0.0.0 untuk LAN)
python vnswap.py --web --host 0.0.0.0    # mode LAN: token dibuat otomatis, buka URL ?token= yang tercetak
python vnswap.py --web --token RAHASIA   # mode LAN dengan token sendiri
python vnswap.py --dry-run               # hanya pratinjau, file tidak diubah
python vnswap.py --stereo                # stereo beta (default: mono)
python vnswap.py --shared /path/.Shared  # folder shared kustom
python vnswap.py --version               # tampilkan versi
```

| Mode | Konfirmasi | Efek |
|------|--------------|--------|
| Default (TUI / CLI) | `Enter` / `TUKAR SEKARANG` | Menulis langsung, backup `.bak` otomatis |
| Pratinjau (`Preview saja` / `--dry-run`) | Sama, tanpa tulis | Simulasi penuh, file tidak diubah |

Flag lama `--apply` masih diterima tetapi sudah tidak diperlukan — tulis langsung kini menjadi default.

## Alur Kerja

```text
LANGKAH 1/3  TARGET    Pilih Visualization.data terbaru (Enter)
LANGKAH 2/3  SUMBER    Pilih audio/video dari daftar atau ketik path (Enter)
LANGKAH 3/3  CEK       Periksa kartu ringkasan, tekan TUKAR SEKARANG (Enter)
PROSES                Encode → sidecar 20 bar/detik → backup .bak → tukar atomik
```

Pintasan keyboard:

| Tombol | Aksi |
|-----|--------|
| `Enter` | Lanjut / tukar |
| `R` | Pindai ulang target |
| `Esc` | Kembali |
| `Up` / `Down` | Pindahkan pilihan |

Catatan:

- Nama file panjang dipotong di tengah (`abc12...xyz.data`) agar mudah dibaca.
- Setiap langkah default ke item terbaru, jadi navigasi minimal sudah cukup.

## Jaminan Keamanan

1. Kedua file (`.opus` + `.data`) dicadangkan sebagai `.bak-timestamp` sebelum penulisan apa pun.
2. Setiap file ditulis secara atomik dengan `os.replace` — tanpa status setengah tertulis.
3. Saat gagal: pemulihan otomatis plus tombol **Rollback** sekali klik pada layar Proses.

## Struktur Proyek

| File | Isi |
|------|----------|
| `vnswap.py` | Entrypoint, status aplikasi, fallback CLI, pipeline bersama, peluncur `--web` |
| `vnswap_core.py` | Logika murni (hanya stdlib — bisa diuji di mana saja): deteksi, rencana encode, visualisasi, swap atomik |
| `vnswap_ui_nav.py` | Tema Dark Pro + layar Target / Sumber / Konfirmasi |
| `vnswap_ui_run.py` | Layar Proses + worker asyncio (progres, log, hasil) |
| `vnswap_web.py` | Server web (`http.server` hanya-stdlib + JSON API + background jobs, token auth untuk LAN) |
| `web/index.html` | Markup wizard web (Target → Sumber → Konfirmasi → Proses) |
| `web/styles.css` | Tema Catppuccin Mocha untuk web (TUI tetap Dark Pro) |
| `web/app.js` | Klien web (fetch + polling, kanvas waveform, unggah, rollback) |
| `tests/test_core.py` | Suite `pytest` untuk `vnswap_core` (tanpa perlu ffmpeg/Textual) |
| `tests/test_web.py` | Tes live-server: health, preview, audio/Range, token gating |
| `.github/workflows/ci.yml` | CI: byte-compile + pytest pada Python 3.10–3.13 |

## Antarmuka Web

Bagi pengguna yang tidak ingin memakai UI terminal:

```bash
python vnswap.py --web
# buka http://127.0.0.1:8000/ di browser
```

Paritas fitur dengan TUI: deteksi otomatis target + pindai ulang + filter, penemuan
otomatis sumber + filter + unggah seret-letakkan + path server manual, kartu konfirmasi
dengan pratinjau waveform ganda (bar target vs bar sumber terhitung) + pemutar audio
untuk kedua file + toggle pratinjau/tulis + resep mono/stereo + peringatan kelebihan
ukuran, lalu tampilan proses langsung (4 tahap, progress bar, log, kartu hasil,
rollback). Tanpa paket pihak ketiga — `vnswap_web.py` hanya memakai stdlib dan
memakai ulang `vnswap_core` untuk encode/sidecar/swap, sehingga perilakunya sama persis
dengan TUI. Di Termux, ekspos ke LAN dengan `python vnswap.py --web --host 0.0.0.0`.

### Autentikasi token LAN

Loopback (`127.0.0.1`) tidak perlu auth. Binding host non-loopback mengaktifkan
token auth pada semua endpoint `/api/*`: token dibuat otomatis dan dicetak
(buka URL `?token=...` yang tercetak), `--token RAHASIA` mengatur milik Anda
sendiri, dan `--no-auth` menonaktifkannya (hanya untuk jaringan yang Anda percaya).

### Deteksi .Shared otomatis

Path hardcoded lama (`.../emulated/999/.../accounts/1006/.Shared`) hanya
cocok untuk satu perangkat. Server kini memindai `$VNSWAP_SHARED`, default, dan
setiap varian nomor akun/pengguna, lalu memakai folder dengan voice note
terbanyak. Urutan prioritas: `--shared` eksplisit, `VNSWAP_SHARED`, deteksi otomatis.
Dropdown di atas wizard menampilkan setiap kandidat beserta jumlah targetnya —
pilih satu lalu tekan Terapkan, atau ketik path secara manual.

## Sumber yang Didukung

Audio: `mp3 m4a aac wav ogg oga opus flac weba`
Video: `webm mp4 m4v mov mkv 3gp`

Apa pun yang bisa di-decode ffmpeg akan dicoba; ekstensi yang tidak didukung memberi peringatan tetapi tetap mencoba rantai encode (utama + fallback).

## Pemecahan Masalah

| Gejala | Perbaikan |
|---------|-----|
| `ffmpeg tidak ditemukan` | `pkg install ffmpeg -y` |
| `textual belum terinstall` | `pip install textual`, atau gunakan `--cli` |
| Tidak ada target ditemukan | Putar satu voice note di WhatsApp dulu, lalu `R` (Pindai Ulang) di TUI atau tombol Pindai Ulang di web |
| Web kosong padahal TUI ada isi | Buka `http://127.0.0.1:8000/api/diagnostics` di browser HP, lihat `shared_dir`, `shared_exists`, `candidates`, dan `scan_error` — di situlah penyebabnya tercatat. Lalu hard-refresh (`Ctrl+Shift+R`) agar `app.js` terbaru terpakai, dan cek footer: harus tertulis versi terbaru |
| Browser "situs tidak dapat dijangkau" padahal server jalan | Jangan buka `http://0.0.0.0:...` — itu alamat bind, bukan alamat tujuan. Terminal kini mencetak URL siap-buka (loopback + tiap IP LAN). Di HP lain pakai URL IP LAN, di HP yang sama pakai `http://127.0.0.1:8000/` |
| Chrome malah Googling alamatnya | Ketik lengkap dengan `http://` di depan, mis. `http://127.0.0.1:8000/` — tanpa skema, Chrome menganggapnya kata kunci pencarian |
| Halaman mati setelah pindah aplikasi | Android mematikan Termux saat dibuka browser. Kunci bangun dulu: `termux-wake-lock` (paket `termux-api`), atau pakai layar-belah agar Termux tetap foreground. Matikan optimasi baterai untuk Termux bila perlu |
| `[XX] port ... sudah dipakai` | Server lama masih jalan. Hentikan dulu (buka terminal lama, `Ctrl+C`), atau jalankan dengan `--port` lain, mis. `--port 8080` |
| API web 401 "butuh token" | Mode LAN butuh token: buka URL lengkap dari terminal (token sudah tersemat sebagai `?token=...`), jangan ketik manual tanpa token |
| Encode selalu gagal | Pastikan file sumber bisa dibuka; coba `--dry-run` untuk isolasi |

## Roadmap

Langkah berikutnya yang direncanakan — dikelompokkan berdasarkan tujuan. Kontribusi dipersilakan untuk item mana pun.

### Lebih canggih

- [ ] Antrean batch: tukar beberapa pasangan target/sumber dalam sekali jalan (job queue web sudah ada — tampilkan di UI, TUI, dan CLI)
- [ ] Kontrol potong: atur awal/akhir atau durasi maksimum sebelum encode (`ffmpeg -ss/-t`), dengan ukuran sidecar yang menyesuaikan durasi
- [x] Pratinjau waveform sumber: hitung bar pengganti *sebelum* swap (endpoint baru `/api/preview`) dan gambar target-vs-sumber berdampingan pada langkah Konfirmasi
- [ ] Pemeriksaan durasi, bukan hanya ukuran: beri peringatan saat audio sumber jauh lebih panjang daripada VN target, bukan hanya saat file besar
- [ ] Progres langsung via Server-Sent Events sebagai pengganti polling di klien web
- [ ] Manajer backup: daftar, pulihkan, dan rapikan file `.bak-timestamp` yang menumpuk dari `.Shared`
- [ ] Riwayat swap (log JSONL) dengan batalkan-dari-riwayat

### Lebih ramah pengguna

- [ ] Toggle bahasa Indonesia/Inggris (UI saat ini hanya Bahasa Indonesia) untuk TUI, CLI, dan web
- [x] Pratinjau audio di browser: putar sumber yang diunggah dan `.opus` target saat ini sebelum konfirmasi
- [ ] Pemeriksaan kesehatan awal: verifikasi ffmpeg, direktori shared, dan izin penyimpanan di awal dengan perintah perbaikan siap salin-tempel
- [ ] Alur keyboard penuh di UI web (pilihan tombol panah, `Enter` untuk lanjut, `R` untuk pindai ulang), sama seperti TUI
- [ ] Shortcut widget Termux untuk meluncurkan TUI atau server web sekali ketuk

### Lebih profesional

- [x] File `LICENSE` (MIT) — dulu placeholder, kini sudah tersedia
- [x] `requirements.txt` / `pyproject.toml` dengan rentang `textual` yang dipin, plus flag `--version` dan `CHANGELOG.md`
- [x] Suite `pytest` untuk `vnswap_core` (hanya-stdlib by design, jadi berjalan di mana saja) dengan CI GitHub Actions setiap push
- [x] Token auth untuk mode LAN `--host 0.0.0.0` di server web (dibuat otomatis kecuali `--token`/`--no-auth`)
- [x] Panduan kontribusi dan template issue; rilis bertag (`v1.0.0`, `v1.1.0`, `v1.2.0`)

## Lisensi

MIT — lihat [LICENSE](LICENSE).

---

Dikembangkan oleh hakiraadityaa.
