# Berkontribusi di vnswap-tui

## Penyiapan (Termux atau mesin Python 3.10+ mana pun)

```bash
pkg install python ffmpeg git -y   # khusus Termux
pip install -r requirements.txt
pip install pytest                 # for tests
termux-setup-storage               # khusus Termux
```

## Menjalankan

```bash
python vnswap.py           # fullscreen TUI
python vnswap.py --cli     # text mode, no Textual needed
python vnswap.py --web     # web UI at http://127.0.0.1:8000/
python vnswap.py --version # print version
```

## Tes

```bash
pytest -q
```

`vnswap_core.py` hanya-stdlib by design, jadi suite berjalan di mana saja —
tanpa perlu Textual, tanpa perlu ffmpeg (jalur yang bergantung pada ffmpeg
dilewati saat binary tidak ada). Logika baru di `vnswap_core` wajib disertai tes.

## Aturan Kode

- `vnswap_core.py` dan `vnswap_web.py`: **hanya stdlib**. Tanpa import pihak ketiga.
- String UI: Bahasa Indonesia, marker status ASCII saja (`[OK]`, `[--]`, `[!!]`,
  `[XX]`), tanpa emoji — aplikasi menargetkan terminal Termux.
- Tema hanya-gelap; perubahan web wajib memakai ulang token Dark Pro di
  `web/styles.css` (nilai yang sama seperti `vnswap_ui_nav.py`).
- Backend web wajib menjaga perilaku identik dengan TUI dengan memakai ulang
  `vnswap_core` — jangan pernah mengimplementasikan ulang logika encode/sidecar/swap.
- Perbarui `CHANGELOG.md` di bawah `[Unreleased]` untuk setiap perubahan yang terlihat pengguna.

## Rilis

Maintainer menandai rilis dari `main`:

```bash
git tag -a vX.Y.Z -m "vnswap-tui vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file CHANGELOG.md
```

Naikkan `VERSION` di `vnswap_core.py` dan `version` di `pyproject.toml` bersamaan.
