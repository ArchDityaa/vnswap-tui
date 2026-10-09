# Kebijakan Privasi — vnswap-tui

Terakhir diperbarui: 2026-10-10.

vnswap-tui dirancang **privasi-pertama**: seluruh pemrosesan terjadi di perangkat
Anda sendiri. Tidak ada server kami, tidak ada analitik, tidak ada telemetri,
tidak ada akun, tidak ada iklan.

## Data yang diakses (hanya di perangkat Anda)

| Data | Dipakai untuk | Disimpan di mana |
|------|---------------|------------------|
| Folder `.Shared` WhatsApp (audio `.opus` + sidecar `.data`) | Target swap | Tetap di perangkat; backup `.bak-timestamp` dibuat di folder yang sama sebelum tulis |
| Folder media (Download, Music, dsb.) | Penemuan sumber otomatis | Hanya dibaca, tidak disalin |
| File yang diunggah via web | Sumber swap | Folder `upload/` server, **dihapus otomatis setelah 24 jam** |
| Token auth LAN | Mengamankan `/api/*` di jaringan lokal | Hanya di terminal + `sessionStorage` tab browser Anda (hilang saat tab ditutup) |

## Jaringan

- Default server web hanya mendengar di `127.0.0.1` (perangkat sendiri) — tidak
  ada data yang keluar perangkat.
- Mode LAN (`--host 0.0.0.0`) membuka server ke jaringan lokal Anda, dilindungi
  token otomatis. Opsi `--no-auth` menonaktifkan perlindungan ini — gunakan hanya
  di jaringan yang sepenuhnya Anda percaya.
- Tidak ada koneksi keluar ke internet dari aplikasi, kecuali `vnswap update`
  yang menjalankan `git fetch` ke GitHub (dan itu pun hanya saat Anda
  menjalankannya manual).

## Pihak ketiga & cookie

- Tidak ada SDK, pelacak, atau cookie pihak ketiga. Satu-satunya penyimpanan
  browser adalah token LAN di `sessionStorage` (lihat tabel di atas).
- Service worker (PWA) hanya menyimpan cangkang tampilan (HTML/CSS/JS) agar
  aplikasi bisa dipasang ke layar utama — tidak menyimpan audio, target, atau
  data pribadi Anda.

## Penghapusan data

- Backup `.bak-timestamp` dan file `upload/` sepenuhnya milik Anda — hapus
  kapan saja dari file manager/terminal.
- Menghapus folder repo + folder `upload/` menghilangkan seluruh jejak aplikasi.

## Kontak

Pertanyaan privasi: buka issue di
[ArchDityaa/vnswap-tui](https://github.com/ArchDityaa/vnswap-tui).
Jangan lampirkan file audio pribadi di issue publik.
