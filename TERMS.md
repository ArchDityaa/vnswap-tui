# Ketentuan Penggunaan — vnswap-tui

Terakhir diperbarui: 2026-10-10.

## 1. Layanan "apa adanya"

vnswap-tui adalah perangkat lunak sumber terbuka berlisensi MIT, disediakan
**"sebagaimana adanya" tanpa jaminan apa pun**. Pengembang tidak bertanggung
jawab atas kehilangan data, kerusakan file, atau akibat lain dari penggunaan
aplikasi ini. Selalu simpan backup penting secara terpisah.

## 2. Tanggung jawab pengguna

- **Cadangkan dulu.** Aplikasi membuat backup `.bak-timestamp` otomatis, tetapi
  Anda tetap disarankan memverifikasi hasil swap di WhatsApp sebelum menghapus
  backup.
- **Mode tulis vs pratinjau.** Default menulis langsung ke file WhatsApp.
  Gunakan mode pratinjau (dry-run) bila ragu.
- **Risiko modifikasi data aplikasi.** Mengubah file data WhatsApp dapat
  melanggar ketentuan layanan WhatsApp dan/atau menyebabkan voice note tidak
  terbaca setelah update WhatsApp. Gunakan atas risiko sendiri.

## 3. Penggunaan yang dilarang

- Hanya tukar voice note **milik Anda sendiri** dan gunakan audio sumber yang
  **Anda miliki atau berhak pakai** (karya sendiri, berlisensi, atau bebas).
- **Dilarang** memakai vnswap untuk menipu, menyamar, memalsukan identitas,
  menipu verifikasi suara, atau melanggar hukum yang berlaku.
- **Dilarang** memakai server web (`--host 0.0.0.0 --no-auth` atau token yang
  dibagikan) untuk memberi orang lain akses ke file di perangkat Anda tanpa
  sepengetahuan mereka.

## 4. Keamanan perangkat Anda

- Jangan jalankan `--no-auth` di jaringan publik/bersama.
- Jangan bagikan URL `?token=...` ke orang yang tidak Anda percaya — token
  memberi akses baca ke file dalam folder yang diizinkan.
- Perbarui aplikasi (`vnswap update`) untuk mendapatkan perbaikan keamanan.

## 5. Perubahan ketentuan

Ketentuan ini dapat diperbarui mengikuti versi aplikasi. Perubahan material
dicatat di [CHANGELOG.md](CHANGELOG.md). Penggunaan berkelanjutan setelah
perubahan berarti Anda menerima ketentuan terbaru.

## 6. Kontak

Pelanggaran/pertanyaan: buka issue di
[ArchDityaa/vnswap-tui](https://github.com/ArchDityaa/vnswap-tui).
