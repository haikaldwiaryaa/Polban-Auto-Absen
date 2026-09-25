# Polban Auto Absen

Auto-login + auto-klik tombol absen **biru** di `akademik.polban.ac.id/ajar/absen`, dengan log sukses/gagal yang jelas. Berjalan **lokal dengan IP asli** — bukan VPS.

---
**© 2026 Haikal. All rights reserved.** Lihat [LICENSE](LICENSE).


## Struktur (setiap folder MANDIRI / self-contained)

Setiap subfolder berisi **semua file yang dibutuhkan** — tidak bergantung ke folder lain. Salin satu folder, langsung jalan.

```
polban-auto-absen/
├── extension/          # Chrome MV3 (klik "Mulai Absen" -> otomatis)
│   ├── manifest.json  background.js  content.js
│   ├── popup.html  popup.js  options.html  options.js
│
├── windows/            # Windows .bat (double-click, tanpa browser)
│   ├── auto_absen.py        # engine (mandiri)
│   ├── install.bat          # install Python portable (sekali)
│   ├── auto_absen.bat       # jalankan (loop)
│   ├── absen_sekali.bat     # tes sekali
│   ├── .env.example  README.md
│
├── termux/             # Android Termux (background 24/7)
│   ├── auto_absen.py        # engine (mandiri)
│   ├── termux-install.sh    # installer
│   ├── termux-run.sh        # launcher (loop + auto-restart)
│   ├── .env.example  README.md
│
└── README.md  CONTRIBUTING.md  LICENSE  .gitignore
```

> **Catatan:** `windows/auto_absen.py` dan `termux/auto_absen.py` adalah **salinan engine yang sama**. Kalau mengubah logika engine, ubah **keduanya** agar tetap sinkron (atau jadikan satu sumber lalu salin saat rilis).

## Fitur
- ✅ **Auto-login** — isi NIM + password, submit.
- ✅ **Bypass popup "Kuesioner Layanan"** — tidak perlu klik OK.
- ✅ **Auto ke `/ajar/absen`** — setelah login langsung ke halaman absen.
- ✅ **Klik HANYA tombol BIRU** — warna lain tidak diklik (tidak merespon).
- ✅ **Retry sampai hijau** — klik biru → tunggu hijau → kalau belum, tekan ulang (maks `maxRetry`, default 5).
- ✅ **Log skip detail per matkul** — hijau=sudah absen · orange=dosen belum buka · merah=di luar jadwal.
- ✅ **Log sukses/gagal** per tahap + nama matkul + sebab gagal.
- ✅ **Event-driven**, **anti-duplikat per-hari**, **kredensial tersimpan permanen**.
- ✅ **Extension hanya jalan saat dipicu** — flow berjalan hanya setelah menekan **▶ Mulai Absen**.

---

## 🖥️ Extension (Chrome, Windows)

1. `chrome://extensions` → **Developer mode** ON → **Load unpacked** → pilih folder `extension/`.
2. Klik ikon → **⚙️ Pengaturan** → isi NIM & password → **Simpan**.
3. Klik ikon → **▶ Mulai Absen** → popup tertutup → tab akademik terbuka → semua otomatis → log panel muncul.

## 🖥️ Windows `.bat`

```bat
cd windows
install.bat          :: sekali (unduh Python portable)
:: edit .env -> isi POLBAN_USERNAME & POLBAN_PASSWORD
auto_absen.bat       :: jalankan (loop)
absen_sekali.bat     :: tes sekali
```

## 📱 Termux (Android)

Lihat **`termux/README.md`** — panduan lengkap dari nol.

```bash
cd termux
bash termux-install.sh
cp .env.example .env && nano .env
python auto_absen.py --engine http --once   # tes
bash termux-run.sh                          # loop 24/7
```

---

## Cara membaca log

### Extension (panel di pojok kanan bawah situs)
| Log | Arti |
|---|---|
| `✅LOGIN Berhasil` | login sukses |
| `❌LOGIN Gagal` | NIM/password salah |
| `⚠️DIALOG alert/confirm di-bypass` | popup dibungkam otomatis |
| `ℹ️NAV Dari /Mhs → /ajar/absen` | pindah ke halaman absen |
| `ℹ️SCAN #1: N tombol — biru:x hijau:y ...` | hasil scan warna |
| `✅SCAN Sudah absen (hijau), skip` | matkul sudah absen |
| `⚠️SCAN Skip tombol orange: ... dosen belum membuka sesi` | alasan skip |
| `⚠️SCAN Skip tombol merah: ... di luar jadwal/waktu absensi` | alasan skip |
| `ℹ️KLIK Klik (biru) + retry sampai hijau: NamaMatkul` | mulai klik |
| `⚠️VERIFIKASI Percobaan 1/5: masih biru, tekan lagi...` | belum hijau, diulang |
| `✅VERIFIKASI SUCCESS — tombol jadi HIJAU (percobaan N)` | **absen berhasil** |
| `❌VERIFIKASI GAGAL — tidak jadi hijau setelah N percobaan` | **absen gagal** |

### Engine (Windows `.bat` / Termux) — kode status terstruktur
| Log | Arti |
|---|---|
| `ℹ️ [SCAN] 2 biru siap-klik \| hijau:1 orange:1 merah:1` | ringkasan scan per warna |
| `⏭️ [SKIP] (orange) belum bisa diklik — dosen belum membuka sesi — Matkul` | skip + alasan |
| `⏭️ [SKIP] (green) sudah absen (dihitung berhasil) — Matkul` | sudah absen |
| `ℹ️ [ABSEN] target: NamaMatkul` | mulai proses absen |
| `⚠️ [RETRY] percobaan 1/5 masih biru, tekan lagi` | belum berhasil, diulang |
| `✅ [ABSEN] BERHASIL (percobaan N): NamaMatkul` | **absen berhasil** |
| `❌ [ABSEN] GAGAL setelah N percobaan: NamaMatkul. Kemungkinan...` | **absen gagal** + sebab |
| `⚠️ [SESSION] Sesi habis — re-login...` | sesi berakhir, auto re-login |
| `❌ [ERROR] request gagal...` | error jaringan/request |

### Mode diagnostik `--dump` (engine)
Kalau tombol biru tidak terdeteksi, dump HTML halaman absen untuk dianalisis:
```bash
python auto_absen.py --engine http --dump        # simpan ke absen-dump.html
```
File berisi HTML mentah (jangan di-commit — sudah di-`.gitignore`). Kirim strukturnya untuk penyesuaian selector.

## Keamanan
- Kredensial disimpan **lokal** (`chrome.storage` untuk extension; `.env` untuk engine). Tidak dikirim ke server selain `akademik.polban.ac.id`.
- `.env`, `.clicked.json`, `windows/python/` sudah di-`.gitignore` — **jangan commit kredensial**.
