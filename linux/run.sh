#!/usr/bin/env bash
# ============================================================
#  Polban Auto Absen - Launcher Linux (loop + auto-restart)
#  Jalankan:  bash run.sh
#  Berhenti:  tekan Ctrl+C
#
#  .env dicari di folder YANG SAMA dengan script ini (atau
#  override lewat env var POLBAN_ENV=/path/ke/.env).
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || { echo "Tidak bisa masuk $SCRIPT_DIR"; exit 1; }

# Izinkan override eksplisit lewat POLBAN_ENV; default: .env di folder script.
export POLBAN_ENV="${POLBAN_ENV:-$SCRIPT_DIR/.env}"

# Cek file engine
if [ ! -f "$SCRIPT_DIR/auto_absen.py" ]; then
    echo "[ERROR] auto_absen.py tidak ada di $SCRIPT_DIR"
    exit 1
fi

# Cek .env
if [ ! -f "$POLBAN_ENV" ]; then
    echo "[ERROR] .env tidak ditemukan di: $POLBAN_ENV"
    echo "        Buat dulu:  cp .env.example .env   lalu  nano .env  (isi NIM & password)"
    echo "        Atau taruh di path lain dan jalankan:  POLBAN_ENV=/path/.env bash run.sh"
    exit 1
fi

# Tentukan Python binary: utamakan .venv jika ada
if [ -f "$SCRIPT_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
else
    PYTHON_BIN="python3"
fi

# Forward semua argumen ke auto_absen.py
exec "$PYTHON_BIN" "$SCRIPT_DIR/auto_absen.py" "$@"
