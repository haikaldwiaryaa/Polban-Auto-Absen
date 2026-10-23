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

# Sama seperti persiapan.bat di Windows: pastikan NIM-nya memang sudah diisi,
# bukan cuma file .env-nya yang ada.
if ! grep -qE '^POLBAN_USERNAME=.+' "$POLBAN_ENV"; then
  echo "[PERINGATAN] POLBAN_USERNAME di $POLBAN_ENV sepertinya masih kosong."
  echo "             Isi dulu POLBAN_USERNAME dan POLBAN_PASSWORD:  nano \"$POLBAN_ENV\""
  printf "             Tetap lanjut? [y/N] "
  read -r lanjut
  case "$lanjut" in
    [yY]*) ;;
    *) exit 1 ;;
  esac
fi

# Pastikan dependensi lengkap. Dijalankan tiap kali supaya update repo yang
# membawa dependensi baru (mis. `rich` untuk dashboard) tidak bikin gagal --
# kalau semua sudah ada, cek ini selesai seketika tanpa akses internet.
# CATATAN: JANGAN pernah 'pip install --upgrade pip' di Termux (merusak python-pip).
if ! python -c 'import requests, bs4, rich' >/dev/null 2>&1; then
  echo "[Setup] Dependensi belum lengkap -- memasang sekali saja (butuh internet)..."
  python -m pip install --user --quiet requests beautifulsoup4 rich
  if ! python -c 'import requests, bs4, rich' >/dev/null 2>&1; then
    echo "[Setup] GAGAL memasang dependensi. Jalankan: bash termux-install.sh"
    exit 1
  fi
  echo "[Setup] Dependensi lengkap."
fi

# Cegah CPU tidur (butuh Termux:API; abaikan kalau tidak ada)
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

# Banner & status digambar oleh live dashboard (tui.py), jadi di sini cukup
# info folder/config saja. Argumen tambahan diteruskan ke engine, misal:
#   bash termux-run.sh --plain          (tanpa dashboard, log mengalir biasa)
#   bash termux-run.sh --no-alt-screen  (dashboard tanpa alternate screen)
echo " Folder : $SCRIPT_DIR"
echo " Config : $POLBAN_ENV"
while true; do
  python "$SCRIPT_DIR/auto_absen.py" --engine http "$@"
  echo "[$(date '+%F %T')] berhenti, restart 10 detik..."
  sleep 10
done
