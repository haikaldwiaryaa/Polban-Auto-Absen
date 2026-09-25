#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  Polban Auto Absen - Launcher Termux (loop + auto-restart)
#  Jalankan:  bash termux-run.sh
#  Berhenti:  tekan Ctrl+C
#
#  .env dicari di folder YANG SAMA dengan script ini (atau
#  override lewat env var POLBAN_ENV=/path/ke/.env).
# ============================================================

# Folder tempat script ini berada (bukan hardcode ~/) — supaya .env
# yang diletakkan "1 folder dengan termux-run.sh" selalu ketemu.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || { echo "Tidak bisa masuk $SCRIPT_DIR"; exit 1; }

# Izinkan override eksplisit lewat POLBAN_ENV; default: .env di folder script.
export POLBAN_ENV="${POLBAN_ENV:-$SCRIPT_DIR/.env}"

# Cek file engine
if [ ! -f "$SCRIPT_DIR/auto_absen.py" ]; then
  echo "[ERROR] auto_absen.py tidak ada di $SCRIPT_DIR"
  echo "        Salin auto_absen.py ke folder yang sama dengan termux-run.sh."
  exit 1
fi

# Cek .env
if [ ! -f "$POLBAN_ENV" ]; then
  echo "[ERROR] .env tidak ditemukan di: $POLBAN_ENV"
  echo "        Buat dulu:  cp .env.example .env   lalu  nano .env  (isi NIM & password)"
  echo "        Atau taruh di path lain dan jalankan:  POLBAN_ENV=/path/.env bash termux-run.sh"
  exit 1
fi

# Cegah CPU tidur (butuh Termux:API; abaikan kalau tidak ada)
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

echo "============================================================"
echo " Polban Auto Absen (Termux, engine HTTP) - Ctrl+C untuk berhenti"
echo " Folder : $SCRIPT_DIR"
echo " Config : $POLBAN_ENV"
echo "============================================================"
while true; do
  echo "[$(date '+%F %T')] mulai auto_absen.py"
  python "$SCRIPT_DIR/auto_absen.py" --engine http
  echo "[$(date '+%F %T')] berhenti, restart 10 detik..."
  sleep 10
done
