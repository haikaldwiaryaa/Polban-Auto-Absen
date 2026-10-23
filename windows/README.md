# Polban Auto Absen — Windows (.bat double-click)

Auto-absen jalan di **terminal Windows** tanpa buka browser, tanpa install Python ke sistem (pakai Python embedded portable), dengan **live dashboard** yang sama seperti versi Linux: identitas mahasiswa, tabel jadwal hari ini, countdown scan berikutnya, dan log aktivitas ringkas.

Folder ini **mandiri** — engine `auto_absen.py` + modul UI `tui.py` ada di sini.

## Tampilan

Dashboard digambar di **alternate screen buffer** (seperti `htop`), jadi layar bersih dan tidak meninggalkan scrollback. Panel diperbarui *in-place*, bukan dicetak ulang tiap siklus, dan **ikut menyesuaikan saat jendela diubah ukurannya**: di bawah 96 kolom kolom Jam melipat ke bawah nama matkul, di bawah 62 kolom kolom Dosen ikut melipat, dan jumlah baris log menyesuaikan tinggi jendela.

```
┌──────────────────────── POLBAN AUTO ABSEN ─────────────────────────┐
│            ___         __           ___    __                      │
│           /   | __  __/ /_____     /   |  / /_  ________  ____     │
│          / ___ / /_/ / /_/ /_/ /  / ___ |/ /_/ (__  )  __/ / / /   │
│                 Polban Auto Absen -- Windows v2.0                  │
│  ┌───────────────────────── Identitas ─────────────────────────┐   │
│  │  Nama       : NAMA KAMU                                     │   │
│  │  NIM        : 25......                                      │   │
│  │  Status     : OK -- Authenticated                           │   │
│  │  Hasil Scan : 16:31:18 (1 siap | 1 sudah | 0 belum buka)    │   │
│  │  Engine     : http  Interval : 60s  Next scan : 00:25       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────── Jadwal Hari Ini ─────────────────────┐   │
│  │  No │ Mata Kuliah     │ Jam        │ Status      │ Dosen     │   │
│  │   1 │ Komputer Grafik │ 08:40 s.d. │ SUDAH ABSEN │ Trisna G. │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌──────────────────── Log Aktivitas (8 terakhir) ─────────────┐   │
│  │  16:31:20  [OK] [LOGIN] Authenticated                       │   │
│  │  16:31:23  [OK] [ABSEN] BERHASIL (percobaan 2): Kompu...    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└──────────── v2.0 windows | siklus #38 | Ctrl+C untuk keluar ───────┘
```

## File

| File               | Tugas                                                 |
| ------------------ | ----------------------------------------------------- |
| `auto_absen.py`    | engine (login → parse tombol → klik + retry)          |
| `tui.py`           | modul UI (live dashboard `rich`) — sama isi dgn termux |
| `persiapan.bat`    | **dipakai permanen** — dipanggil kedua launcher di atas tiap kali jalan: cek Python portable, cek `requests`/`beautifulsoup4`/`rich` (unduh yang kurang), cek `.env` ada & `POLBAN_USERNAME` terisi. Bukan file sementara |
| `install.bat`      | jalankan SEKALI — unduh Python portable + dependensi  |
| `auto_absen.bat`   | jalankan (loop, poll tiap `POLBAN_INTERVAL` detik)    |
| `absen_sekali.bat` | tes SEKALI jalan lalu berhenti (dashboard tetap terlihat) |
| `.env.example`     | template config                                        |

## Cara pakai (dari awal)

1. **Install sekali** — klik 2x `install.bat` (butuh internet; unduh Python portable ke `windows\python\` + `requests`, `beautifulsoup4`, `rich`).
2. **Isi kredensial** — buka `.env` (dibuat oleh installer dari `.env.example`), isi:
   ```
   POLBAN_USERNAME=25.....
   POLBAN_PASSWORD=password_kamu
   ```
3. **Tes** — klik 2x `absen_sekali.bat`. Dashboard yang sama muncul, bedanya tidak memakai alternate screen jadi hasilnya **tetap di layar** setelah selesai.
4. **Jalankan** — klik 2x `auto_absen.bat` → live dashboard. Berhenti: `Ctrl+C`.
5. **Desktop shortcut** — klik kanan `auto_absen.bat` → Send to → Desktop.

## Argumen CLI

Bisa ditambahkan di belakang nama `.bat` (diteruskan ke engine), atau dipanggil langsung lewat `python\python.exe auto_absen.py ...`.

| Argumen           | Keterangan                                                             |
| ----------------- | ---------------------------------------------------------------------- |
| `--engine http`   | engine HTTP ringan, tanpa browser (default)                            |
| `--engine pw`     | engine Playwright (perlu `pip install playwright` + `playwright install chromium`) |
| `--once`          | sekali jalan lalu exit. Dashboard tetap digambar, tanpa alternate screen |
| `--plain`         | paksa plain text (log mengalir biasa, tanpa dashboard)                 |
| `--no-alt-screen` | dashboard digambar di layar biasa — pakai bila terminal lama tampil kacau |
| `--dump [FILE]`   | simpan HTML halaman absen lalu exit (diagnostik)                       |

## Dependensi otomatis

Kedua launcher memanggil **`persiapan.bat`** yang sama persis sebelum jalan, jadi
`auto_absen.bat` dan `absen_sekali.bat` tidak akan pernah beda perilaku. Isinya:
Python portable ada, `requests`/`beautifulsoup4`/`rich` bisa di-import, `.env` ada
dan `POLBAN_USERNAME` terisi.

Kalau semua lengkap, cek ini selesai seketika tanpa internet; kalau ada yang kurang
(misalnya setelah `git pull` yang membawa dependensi baru), paketnya diunduh sendiri
lalu program lanjut jalan. Jadi **tidak perlu** menjalankan ulang `install.bat` tiap
kali repo di-update.

Selain `ARGS` (`--once`) dan judul jendela, isi kedua `.bat` itu memang dibuat kembar —
`diff auto_absen.bat absen_sekali.bat` hanya menampilkan dua baris itu plus komentar.

## Cara kerja

Engine **HTTP** (`requests`), bukan browser: login via `POST /laman/login` (diverifikasi GET `/ajar/absen`), parse tabel `#jadwal`, klik tombol yang **biru** lewat `POST /ajar/absen/absensi_awal`, lalu **retry sampai absen terverifikasi** (maks `POLBAN_MAX_RETRY`). Alert "Kuesioner Layanan" tidak pernah muncul (itu JavaScript browser).

Semua status masuk ke dashboard `tui.py`; kalau `rich` tidak terpasang atau output dialihkan ke file, otomatis jatuh ke mode plain text.

## Troubleshooting

| Masalah                          | Solusi                                                                 |
| -------------------------------- | ---------------------------------------------------------------------- |
| installer gagal unduh            | cek internet, jalankan `install.bat` lagi                              |
| `Login GAGAL`                    | NIM/password di `.env` salah                                           |
| window langsung tertutup         | jalankan lewat `cmd` manual untuk lihat error                          |
| border/warna berantakan          | jalankan dengan `--no-alt-screen`, atau pakai Windows Terminal         |
| ada area kosong di kanan layar   | buffer console terkunci (biasanya 120 kolom). Dashboard mengukur berapa kolom yang muat di jendela lalu melebarkan buffernya sendiri; kalau tetap kosong, klik kanan judul jendela → Properties → Layout → besarkan *Screen buffer size → Width* |
| kotak dashboard jadi `?` / kotak | pastikan dijalankan lewat `.bat` (sudah `chcp 65001`), bukan klik `.py` |
| tidak ada dashboard sama sekali  | `rich` belum terpasang — launcher melengkapinya otomatis lewat `persiapan.bat` (butuh internet sekali) |
| `modul UI dashboard tidak bisa dimuat` | `tui.py` harus berada **satu folder** dengan `auto_absen.py`           |
| `Tidak ada tombol biru`          | di luar jam absen / dosen belum buka — dicoba lagi di poll berikutnya  |
