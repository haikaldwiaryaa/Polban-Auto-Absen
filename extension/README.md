# Polban Auto Absen — Chrome Extension (MV3)

Auto-absen dengan tombol **▶ Mulai Absen**. Flow berjalan **hanya** setelah tombol ditekan — membuka situs akademik langsung tanpa lewat extension **tidak** menjalankan apa-apa.

## File (mandiri — tidak butuh folder lain)
| File | Tugas |
|---|---|
| `manifest.json` | deklarasi MV3, permission, popup, background, content script |
| `background.js` | service worker: trigger gate + force-nav ke `/ajar/absen` (bypass popup) |
| `content.js` | logic di halaman: login, navigasi, scan & klik tombol biru, log panel |
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
4. Login → `background.js` force-nav ke `/ajar/absen` (kebal popup alert) → `content.js` scan & klik tombol biru → **retry sampai hijau**.
5. `content.js` kirim `PAA_DONE` → trigger dilepas.

## Pengaturan (Options)
NIM, password, URL absen, toggle auto-login/nav/click, delay klik, interval polling, max passes, **max retry klik** & **jeda retry**.
