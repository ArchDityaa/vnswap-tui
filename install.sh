#!/usr/bin/env sh
# Instal vnswap: dependensi + launcher perintah `vnswap`.
# Termux:  sh install.sh     (atau: bash install.sh)
# Linux:   sh install.sh     (pakai ~/.local/bin bila bukan Termux)
set -eu

REPO_URL="https://github.com/ArchDityaa/vnswap-tui"

if command -v pkg >/dev/null 2>&1; then
  # --- Termux (Android) ---
  pkg install -y python ffmpeg git
  REPO_DIR="${HOME}/vnswap-tui"
  BIN_DIR="${PREFIX}/bin"
else
  # --- Linux umum ---
  REPO_DIR="${HOME}/vnswap-tui"
  BIN_DIR="${HOME}/.local/bin"
fi

if [ -d "${REPO_DIR}/.git" ]; then
  git -C "${REPO_DIR}" pull --ff-only
else
  git clone "${REPO_URL}" "${REPO_DIR}"
fi

if [ -f "${REPO_DIR}/requirements.txt" ]; then
  pip install -r "${REPO_DIR}/requirements.txt" || pip install textual
else
  pip install textual
fi

if command -v termux-setup-storage >/dev/null 2>&1; then
  termux-setup-storage
fi

mkdir -p "${BIN_DIR}"
cat > "${BIN_DIR}/vnswap" <<'EOF'
#!/usr/bin/env sh
exec python "$HOME/vnswap-tui/vnswap.py" "$@"
EOF
chmod +x "${BIN_DIR}/vnswap"

echo "[OK] selesai. Perintah baru:"
echo "  vnswap           buka TUI"
echo "  vnswap web       jalankan server web"
echo "  vnswap update    update ke versi terbaru dari GitHub"
echo "Tutup lalu buka lagi terminal bila perintah belum dikenal."
