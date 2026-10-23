# Polban Auto Absen — Chrome Extension (MV3)

Auto-absen dengan tombol **▶ Mulai Absen**. Flow berjalan **hanya** setelah tombol ditekan — membuka situs akademik langsung tanpa lewat extension **tidak** menjalankan apa-apa.

Panel di halaman absen kini berupa **dashboard** dengan susunan yang sama seperti TUI versi Linux:

| Bagian | Isi |
|---|---|
| Header | status dot + hitungan `OK / GAGAL / SKIP` + tombol scan, bersihkan log, minimize |
| **Identitas** | Nama, NIM, Jurusan, Tanggal, Status login, Hasil scan, countdown `Next scan` |
| **Jadwal Hari Ini** | tabel matkul + jam + badge status (SUDAH ABSEN / SIAP ABSEN / BELUM BUKA / BELUM WAKTUNYA) + nama dosen pengampu |
| **Log Aktivitas** | `HH:MM:SS [OK] [STAGE] pesan` — format identik dengan engine Python. Rincian per matkul tidak ditulis di sini karena sudah ada di tabel |

Panel ikut ukuran jendela (`min(430px, 100vw - 28px)`), dan di layar sempit (< 760px) panel melebar penuh dengan kolom Dosen melipat ke bawah nama matkul.

Popup dan halaman Options memakai tema gelap yang sama.

## File (mandiri — tidak butuh folder lain)
| File | Tugas |
|---|---|
| `manifest.json` | deklarasi MV3, permission, popup, background, content script |
| `background.js` | service worker: trigger gate + force-nav ke `/ajar/absen` (bypass popup) |
| `content.js` | logic di halaman: login, navigasi, scan & klik tombol biru, dashboard panel |
| `popup.html` / `popup.js` | tombol "Mulai Absen" + status NIM |
| `options.html` / `options.js` | form pengaturan (NIM, password, delay, retry, dll) |

## Instalasi
1. `chrome://extensions` → **Developer mode** ON → **Load unpacked** → pilih folder ini.
2. Klik ikon extension → **⚙️ Pengaturan** → isi NIM & password → **Simpan** (tersimpan permanen di `chrome.storage.sync`).
3. Klik ikon → **▶ Mulai Absen** → popup tertutup → tab akademik terbuka → semua otomatis.

## Cara kerja
1. `popup.js` → kirim `PAA_START` ke `background.js`.
2. `background.js` membuka/mengaktifkan tab akademik dan menandainya **armed**.
3. `content.js` menanyakan `PAA_SHOULD_RUN` — hanya jalan kalau tab armed.
4. Login → `background.js` force-nav ke `/ajar/absen` (kebal popup alert) → `content.js` scan & klik tombol biru → **retry sampai hijau**. Tiap scan tabel jadwal di panel di-update in-place; log hanya bertambah saat scan pertama, ada tombol biru, atau status berubah.
5. `content.js` kirim `PAA_DONE` → trigger dilepas.

## Pengaturan (Options)
NIM, password, URL absen, toggle auto-login/nav/click, delay klik, interval polling, max passes, **max retry klik** & **jeda retry**.
