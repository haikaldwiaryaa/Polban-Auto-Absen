# Polban Auto Absen — Termux (Android)

Jalankan auto-absen di HP Android **tanpa browser**, hemat baterai, bisa background 24/7 — dengan **live dashboard** yang sama seperti versi Linux (identitas, tabel jadwal, countdown, log aktivitas).

## Prasyarat

- **Termux** — install dari **F-Droid** (bukan Play Store, versi di sana sudah usang).
- (Opsional) **Termux:Boot** dari F-Droid — untuk auto-jalan saat HP nyala.
- (Opsional) **Termux:API** — untuk `termux-wake-lock` (cegah CPU tidur).

## Instalasi (lengkap, dari nol)

1. **Salin file ke HP.** Kamu butuh `auto_absen.py`, `tui.py`, `.env.example`, `termux-install.sh`, `termux-run.sh`. Cara termudah:

   ```bash
   # Dari komputer/VPS yang punya filenya, kirim ke HP via scp/ssh,
   # atau clone repo git, atau salin manual lewat file manager/USB.
   ```

   Di Termux, buat folder kerja:

   ```bash
   mkdir -p ~/polban-auto-absen && cd ~/polban-auto-absen
   # letakkan auto_absen.py, tui.py, .env.example, termux-install.sh, termux-run.sh di sini
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

   Harus muncul banner, baris `[OK] [LOGIN] Authenticated`, lalu hasil scan tombol.
   Mode `--once` otomatis plain text supaya log tetap terbaca setelah selesai.

5. **Mode loop 24/7** (auto-restart bila error):

   ```bash
   bash termux-run.sh
   ```

   Berhenti: `Ctrl+C`. Layar penuh terasa sempit di HP? Jalankan dengan
   `bash termux-run.sh --no-alt-screen` (dashboard tanpa alternate screen)
   atau `bash termux-run.sh --plain` (log mengalir biasa).

6. **(Opsional) Autostart saat HP nyala** — installer sudah membuat `~/.termux/boot/start-auto-absen.sh`. Cukup install **Termux:Boot**, lalu buka sekali. Selesai — setiap HP nyala, auto-absen jalan sendiri di background.

## Cara kerja

Engine **HTTP** (`requests`), bukan browser:

- Login via `POST /laman/login`, verifikasi dengan GET `/ajar/absen`.
- Alert "Kuesioner Layanan" **tidak pernah muncul** (itu JavaScript browser).
- Parse tabel `#jadwal`, klik HANYA tombol **biru** lewat `POST /ajar/absen/absensi_awal`,
  retry sampai terverifikasi (maks `POLBAN_MAX_RETRY`), polling tiap `POLBAN_INTERVAL` detik (default 60).

## Tampilan

Output ditangani `tui.py` (`rich`): banner, panel **Identitas**, tabel **Jadwal Hari Ini**
(status per matkul: SUDAH ABSEN / SIAP ABSEN / BELUM BUKA / BELUM WAKTUNYA, plus dosen pengampu),
countdown scan berikutnya, dan **Log Aktivitas** 15 baris terakhir.

Otomatis jatuh ke plain text bila `rich` tidak terpasang, output dialihkan ke file
(autostart/`absen.log`), atau dijalankan dengan `--once` / `--plain`.

| Argumen | Keterangan |
|---|---|
| `--once` | sekali jalan lalu exit; dashboard tetap di layar (plain kalau output ke file) |
| `--plain` | paksa plain text |
| `--no-alt-screen` | dashboard tanpa alternate screen (layar HP sempit) |
| `--dump [FILE]` | simpan HTML halaman absen (diagnostik) |

## Log

Log tampil di terminal. Kalau autostart/background, log ditulis ke `~/polban-auto-absen/absen.log`:

```bash
tail -f ~/polban-auto-absen/absen.log
```

## Troubleshooting

| Masalah                                               | Solusi                                                                                                                                                                  |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `command not found: python`                           | `pkg install -y python`                                                                                                                                                 |
| `installing pip is forbidden / will break python-pip` | Jangan `pip install --upgrade pip`. Kalau sudah terlanjur: `pkg install -y --reinstall python-pip`, lalu `python -m pip install --user requests beautifulsoup4 rich`         |
| `No module named requests`                            | `python -m pip install --user requests beautifulsoup4 rich`                                                                                                             |
| dashboard tidak muncul (log polos)                    | `rich` belum terpasang: `python -m pip install --user rich`                                                                                                             |
| tampilan dashboard pecah di layar sempit              | jalankan `bash termux-run.sh --no-alt-screen` atau `--plain`                                                                                                            |
| `ERROR: POLBAN_USERNAME...`                           | `.env` belum ada/kosong → ulangi langkah 3                                                                                                                              |
| `[ERROR] .env tidak ditemukan`                        | Letakkan `.env` di **folder yang sama** dengan `termux-run.sh` (bukan di `~/polban-auto-absen`). Atau jalankan eksplisit: `POLBAN_ENV=/path/ke/.env bash termux-run.sh` |
| `Login GAGAL`                                         | NIM/password salah di `.env`                                                                                                                                            |
| Berhenti sendiri saat HP tidur                        | install Termux:API lalu jalankan `termux-wake-lock`, atau pakai `termux-run.sh` (sudah panggil wake-lock)                                                               |
| `Tidak ada tombol biru`                               | di luar jam absen / dosen belum buka — normal, dicoba lagi di poll berikutnya                                                                                           |
