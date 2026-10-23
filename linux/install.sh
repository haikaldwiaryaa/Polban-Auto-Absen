#!/usr/bin/env bash
# ============================================================
#  Polban Auto Absen - Installer Linux
#  Jalankan:  bash install.sh
#  Engine: HTTP (requests) - tanpa browser.
#
#  Bekerja di folder tempat script ini berada.
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo " Polban Auto Absen -- Linux Installer"
echo "============================================================"
echo ""

# [1/3] Cek Python >= 3.9
echo "==> [1/3] Cek Python"
if ! command -v python3 &>/dev/null; then
    echo "    python3 tidak ditemukan."
    echo "    Install dulu:"
    echo "      Ubuntu/Debian : sudo apt install python3 python3-pip"
    echo "      Fedora        : sudo dnf install python3 python3-pip"
    echo "      Arch          : sudo pacman -S python python-pip"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]); then
    echo "    Python $PY_VERSION terdeteksi, butuh >= 3.9"
    exit 1
fi
echo "    Python $PY_VERSION -- OK"

# [2/3] Siapkan virtual environment & install dependensi
echo ""
echo "==> [2/3] Siapkan virtual environment (.venv)"
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    python3 -m venv "$SCRIPT_DIR/.venv"
    echo "    Virtual environment dibuat di $SCRIPT_DIR/.venv"
else
    echo "    Virtual environment (.venv) sudah ada."
fi

echo "    Menginstall dependensi (rich, requests, beautifulsoup4)..."
"$SCRIPT_DIR/.venv/bin/pip" install --upgrade pip 2>/dev/null || true
"$SCRIPT_DIR/.venv/bin/pip" install rich requests beautifulsoup4
echo "    Dependensi terinstall."

# [3/3] Siapkan .env
echo ""
echo "==> [3/3] Siapkan config"
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

echo ""
echo "============================================================"
echo " SELESAI. Folder kerja: $SCRIPT_DIR"
echo ""
echo " Langkah selanjutnya:"
echo "   1. Edit .env (isi NIM & password):"
echo "        nano $SCRIPT_DIR/.env"
echo ""
echo "   2. Tes sekali:"
echo "        python3 $SCRIPT_DIR/auto_absen.py --engine http --once"
echo ""
echo "   3. Mode loop (live dashboard):"
echo "        bash $SCRIPT_DIR/run.sh"
echo ""
echo "   4. (Opsional) Install Playwright untuk engine pw:"
echo "        $SCRIPT_DIR/.venv/bin/pip install playwright"
echo "        $SCRIPT_DIR/.venv/bin/playwright install chromium"
echo "============================================================"
