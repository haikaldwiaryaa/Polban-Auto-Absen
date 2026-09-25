#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  Polban Auto Absen - Installer Termux (Android)
#  Jalankan:  bash termux-install.sh
#  Engine: HTTP (requests) - tanpa browser, hemat baterai.
#
#  Bekerja di folder tempat script ini berada (bukan hardcode ~/).
# ============================================================
set -e

# Folder tempat script ini berada
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> [1/4] Update paket & install python"
pkg update -y
pkg install -y python cronie nano

echo "==> [2/4] Install dependensi python"
# JANGAN 'pip install --upgrade pip' — di Termux itu merusak paket python-pip
# ("installing pip is forbidden, this will break the python-pip package").
# Kalau pip SUDAH terlanjur rusak karena upgrade sebelumnya, perbaiki dulu:
if ! python -m pip --version >/dev/null 2>&1; then
  echo "    pip rusak — memperbaiki paket python-pip..."
  pkg install -y --reinstall python-pip || pkg install -y python-pip
fi
python -m pip install --user requests beautifulsoup4

echo "==> [3/4] Siapkan config di folder script: $SCRIPT_DIR"
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  if [ -f "$SCRIPT_DIR/.env.example" ]; then
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo "    .env dibuat dari template -> EDIT: isi NIM & password."
  else
    cat > "$SCRIPT_DIR/.env" <<'EOF'
POLBAN_USERNAME=
POLBAN_PASSWORD=
POLBAN_TARGET_URL=https://akademik.polban.ac.id/ajar/absen
POLBAN_INTERVAL=60
POLBAN_ENGINE=http
EOF
    echo "    .env kosong dibuat -> EDIT: isi NIM & password."
  fi
else
  echo "    .env sudah ada, dilewati."
fi

# Autostart saat HP nyala (butuh Termux:Boot dari F-Droid)
echo "==> [4/4] Siapkan autostart"
BOOT_DIR="$HOME/.termux/boot"
mkdir -p "$BOOT_DIR"
cat > "$BOOT_DIR/start-auto-absen.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
export POLBAN_ENV="$SCRIPT_DIR/.env"
cd "$SCRIPT_DIR" && python "$SCRIPT_DIR/auto_absen.py" --engine http >> "$SCRIPT_DIR/absen.log" 2>&1 &
EOF
chmod +x "$BOOT_DIR/start-auto-absen.sh"
echo "    Autostart dibuat di $BOOT_DIR/start-auto-absen.sh"

cat <<EOF

============================================================
 SELESAI. Folder kerja: $SCRIPT_DIR
 Langkah selanjutnya:
   1. Edit .env (isi NIM & password):   nano "$SCRIPT_DIR/.env"
   2. Tes sekali:   python "$SCRIPT_DIR/auto_absen.py" --engine http --once
   3. Mode loop 24/7:   bash "$SCRIPT_DIR/termux-run.sh"
   4. (Opsional) install Termux:Boot (F-Droid) agar auto-jalan saat HP nyala
============================================================
EOF
