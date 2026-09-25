# Polban Auto Absen — Windows (.bat double-click)

Auto-absen jalan di **terminal Windows** tanpa buka browser, tanpa install Python ke sistem (pakai Python embedded portable). Folder ini **mandiri** — engine `auto_absen.py` ada di sini.

## File
| File | Tugas |
|---|---|
| `auto_absen.py` | engine (login → parse tombol → klik + retry) |
| `install.bat` | jalankan SEKALI — unduh Python portable + dependensi |
| `auto_absen.bat` | jalankan (loop, poll tiap `POLBAN_INTERVAL` detik) |
| `absen_sekali.bat` | tes SEKALI jalan lalu berhenti |
| `.env.example` | template config |

## Cara pakai (dari awal)
1. **Install sekali** — klik 2x `install.bat` (butuh internet; unduh Python portable ke `windows\python\`).
2. **Isi kredensial** — buka `.env` (dibuat oleh installer dari `.env.example`), isi:
   ```
   POLBAN_USERNAME=25.....
   POLBAN_PASSWORD=password_kamu
   ```
3. **Tes** — klik 2x `absen_sekali.bat` (harus muncul `Login OK` lalu hasil scan).
4. **Jalankan** — klik 2x `auto_absen.bat`. Berhenti: tutup jendela / `Ctrl+C`.
5. **Desktop shortcut** — klik kanan `auto_absen.bat` → Send to → Desktop.

## Cara kerja
Engine **HTTP** (`requests`), bukan browser: login via `POST /laman/login` (diverifikasi GET `/ajar/absen`), parse tombol, klik yang **biru**, **retry sampai tombol hilang dari daftar biru** (sukses). Alert "Kuesioner Layanan" tidak pernah muncul (itu JavaScript browser).

## Troubleshooting
| Masalah | Solusi |
|---|---|
| installer gagal unduh | cek internet, jalankan `install.bat` lagi |
| `Login GAGAL` | NIM/password di `.env` salah |
| window langsung tertutup | jalankan lewat `cmd` manual untuk lihat error |
| `Tidak ada tombol biru` | di luar jam absen / dosen belum buka — dicoba lagi di poll berikutnya |

## Keamanan
`.env` berisi password teks biasa di folder ini — jangan bagikan foldernya. Untuk lebih aman, pakai **extension** (kredensial di `chrome.storage`, terenkripsi profil).
