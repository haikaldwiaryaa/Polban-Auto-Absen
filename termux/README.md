# Polban Auto Absen — Termux (Android)

Jalankan auto-absen di HP Android **tanpa browser**, hemat baterai, bisa background 24/7.

## Prasyarat
- **Termux** — install dari **F-Droid** (bukan Play Store, versi di sana sudah usang).
- (Opsional) **Termux:Boot** dari F-Droid — untuk auto-jalan saat HP nyala.
- (Opsional) **Termux:API** — untuk `termux-wake-lock` (cegah CPU tidur).

## Instalasi (lengkap, dari nol)

1. **Salin file ke HP.** Kamu butuh `auto_absen.py`, `.env.example`, `termux-install.sh`, `termux-run.sh`. Cara termudah:
   ```bash
   # Dari komputer/VPS yang punya filenya, kirim ke HP via scp/ssh,
   # atau clone repo git, atau salin manual lewat file manager/USB.
   ```
   Di Termux, buat folder kerja:
   ```bash
   mkdir -p ~/polban-auto-absen && cd ~/polban-auto-absen
   # letakkan auto_absen.py, .env.example, termux-install.sh, termux-run.sh di sini
   ```

2. **Jalankan installer** (install python + dependensi + autostart):
   ```bash
   bash termux-install.sh
   ```

3. **Isi kredensial:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   Isi (tanpa kutip, simbol `# ! @` spasi aman):
   ```
   POLBAN_USERNAME=NIM_kamu
   POLBAN_PASSWORD=password_kamu
   ```
   Simpan: `Ctrl+O` → Enter → `Ctrl+X`.

4. **Tes sekali** (pastikan login + deteksi tombol jalan):
   ```bash
   python auto_absen.py --engine http --once
   ```
   Harus muncul `Login OK (terautentikasi, ...)` lalu hasil scan tombol.

5. **Mode loop 24/7** (auto-restart bila error):
   ```bash
   bash termux-run.sh
   ```
   Berhenti: `Ctrl+C`.

6. **(Opsional) Autostart saat HP nyala** — installer sudah membuat `~/.termux/boot/start-auto-absen.sh`. Cukup install **Termux:Boot**, lalu buka sekali. Selesai — setiap HP nyala, auto-absen jalan sendiri di background.

## Cara kerja
Engine **HTTP** (`requests`), bukan browser:
- Login via `POST /laman/login`, verifikasi dengan GET `/ajar/absen`.
- Alert "Kuesioner Layanan" **tidak pernah muncul** (itu JavaScript browser).
- Parse tombol absen, klik yang **non-hijau**, polling tiap `POLBAN_INTERVAL` detik (default 60).

## Log
Log tampil di terminal. Kalau autostart/background, log ditulis ke `~/polban-auto-absen/absen.log`:
```bash
tail -f ~/polban-auto-absen/absen.log
```

## Troubleshooting
| Masalah | Solusi |
|---|---|
| `command not found: python` | `pkg install -y python` |
| `installing pip is forbidden / will break python-pip` | Jangan `pip install --upgrade pip`. Kalau sudah terlanjur: `pkg install -y --reinstall python-pip`, lalu `python -m pip install --user requests beautifulsoup4` |
| `No module named requests` | `python -m pip install --user requests beautifulsoup4` |
| `ERROR: POLBAN_USERNAME...` | `.env` belum ada/kosong → ulangi langkah 3 |
| `[ERROR] .env tidak ditemukan` | Letakkan `.env` di **folder yang sama** dengan `termux-run.sh` (bukan di `~/polban-auto-absen`). Atau jalankan eksplisit: `POLBAN_ENV=/path/ke/.env bash termux-run.sh` |
| `Login GAGAL` | NIM/password salah di `.env` |
| Berhenti sendiri saat HP tidur | install Termux:API lalu jalankan `termux-wake-lock`, atau pakai `termux-run.sh` (sudah panggil wake-lock) |
| `Tidak ada tombol biru` | di luar jam absen / dosen belum buka — normal, dicoba lagi di poll berikutnya |
