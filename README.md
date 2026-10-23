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
├── windows/            # Windows .bat (double-click, live TUI dashboard)
│   ├── auto_absen.py        # engine (mandiri)
│   ├── tui.py               # modul TUI (rich live dashboard)
│   ├── persiapan.bat        # cek Python + dependensi + .env (dipanggil kedua launcher)
│   ├── install.bat          # install Python portable (sekali)
│   ├── auto_absen.bat       # jalankan (loop, dashboard)
│   ├── absen_sekali.bat     # tes sekali (dashboard tetap di layar)
│   ├── .env.example  README.md
│
├── linux/              # Linux (live TUI dashboard)
│   ├── auto_absen.py        # engine + TUI integration (dirawat terpisah)
│   ├── tui.py               # modul TUI (rich live dashboard)
│   ├── install.sh           # installer
│   ├── run.sh               # launcher
│   ├── .env.example  README.md
│
├── termux/             # Android Termux (24/7, live TUI dashboard)
│   ├── auto_absen.py        # engine (mandiri)
│   ├── tui.py               # modul TUI (rich live dashboard)
│   ├── termux-install.sh    # installer
│   ├── termux-run.sh        # launcher (loop + auto-restart)
│   ├── .env.example  README.md
│
└── README.md  CONTRIBUTING.md  LICENSE  .gitignore
```

> **Catatan:** `windows/` dan `termux/` memakai **file identik** (`auto_absen.py` + `tui.py`) — label platform di banner dideteksi otomatis saat runtime, jadi perbaikan cukup disalin apa adanya antar keduanya (`diff windows/auto_absen.py termux/auto_absen.py` harus kosong). `linux/` memegang salinannya sendiri dan **dirawat terpisah**.

## Fitur

- ✅ **Auto-login** — isi NIM + password, submit.
- ✅ **Bypass popup "Kuesioner Layanan"** — tidak perlu klik OK.
- ✅ **Auto ke `/ajar/absen`** — setelah login langsung ke halaman absen.
- ✅ **Klik HANYA tombol BIRU** — warna lain tidak diklik (tidak merespon).
- ✅ **Retry sampai hijau** — klik biru → tunggu hijau → kalau belum, tekan ulang (maks `maxRetry`, default 5).
- ✅ **Alasan per matkul** — hijau=sudah absen · orange=dosen belum buka · merah=di luar jadwal. Di `windows/`, `termux/`, dan extension ditampilkan di tabel jadwal (tidak lagi membanjiri log); di `linux/` masih berupa baris log.
- ✅ **Log sukses/gagal** per tahap + nama matkul + sebab gagal.
- ✅ **Event-driven**, **anti-duplikat per-hari**, **kredensial tersimpan permanen**.
- ✅ **Extension hanya jalan saat dipicu** — flow berjalan hanya setelah menekan **▶ Mulai Absen**.
- ✅ **Dependensi menyusul sendiri** — `auto_absen.bat` dan `absen_sekali.bat` sama-sama memanggil `persiapan.bat` (Python portable + paket + `.env`), dan `termux-run.sh` melakukan pemeriksaan yang setara. Setelah `git pull` yang menambah dependensi, cukup jalankan seperti biasa. Untuk `linux/`, jalankan `bash install.sh` sekali setelah pull.
- ✅ **Tampilan menyesuaikan ukuran jendela** (`windows/`, `termux/`, extension) — dashboard dibangun ulang tiap frame, jadi tabel jadwal berubah bentuk sendiri saat terminal di-maximize/di-restore: kolom Jam lalu Dosen melipat ke bawah nama matkul, dan jumlah baris log menyesuaikan tinggi jendela. Di Windows, buffer console ikut dilebarkan otomatis saat jendela di-maximize supaya tidak menyisakan area kosong di kanan. Panel extension melar/menyusut mengikuti lebar browser.
- ✅ **Dashboard seragam di semua platform** — identitas mahasiswa, tabel jadwal hari ini dengan status per matkul, countdown scan berikutnya, log aktivitas ringkas. Di terminal (Windows/Linux/Termux) lewat `tui.py`, di browser lewat panel `content.js`.

---

## 🖥️ Extension (Chrome, Windows)

1. `chrome://extensions` → **Developer mode** ON → **Load unpacked** → pilih folder `extension/`.
2. Klik ikon → **⚙️ Pengaturan** → isi NIM & password → **Simpan**.
3. Klik ikon → **▶ Mulai Absen** → popup tertutup → tab akademik terbuka → semua otomatis → log panel muncul.

## 🖥️ Windows `.bat`

```bat
cd windows
install.bat          :: sekali (unduh Python portable + rich)
:: edit .env -> isi POLBAN_USERNAME & POLBAN_PASSWORD
auto_absen.bat       :: jalankan (loop, live dashboard)
absen_sekali.bat     :: tes sekali (dashboard tetap di layar)
```

Lihat **`windows/README.md`** — termasuk argumen `--plain` dan `--no-alt-screen`.

## Linux (Live TUI Dashboard)

Lihat **`linux/README.md`** — panduan lengkap.

```bash
cd linux
bash install.sh
cp .env.example .env && nano .env
python3 auto_absen.py --engine http --once   # tes
bash run.sh                                  # loop (live dashboard)
```

## Termux (Android)

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

### Extension (panel dashboard di pojok kanan bawah situs)

| Log                                                          | Arti                     |
| ------------------------------------------------------------ | ------------------------ |
| `[OK] [LOGIN] Berhasil`                                           | login sukses             |
| `[!!] [LOGIN] Gagal`                                              | NIM/password salah       |
| `[??] [DIALOG] alert/confirm di-bypass`                           | popup dibungkam otomatis |
| `[--] [NAV] Dari /Mhs ke /ajar/absen`                              | pindah ke halaman absen  |
| `[--] [SCAN] #1: N tombol -- biru:x hijau:y ...`                   | hasil scan warna         |
| `[--] [KLIK] Klik (biru) + retry sampai hijau: NamaMatkul`        | mulai klik               |
| `[??] [VERIFIKASI] Percobaan 1/5: masih biru, tekan lagi...`      | belum hijau, diulang     |
| `[OK] [VERIFIKASI] SUCCESS -- tombol jadi HIJAU (percobaan N)`     | **absen berhasil**       |
| `[!!] [VERIFIKASI] GAGAL -- tidak jadi hijau setelah N percobaan`  | **absen gagal**          |

### Engine (Windows / Termux / Linux) — panel Log Aktivitas

Format baris: `HH:MM:SS  [TAG] [KODE] pesan`. Tag: `[OK]` sukses · `[!!]` gagal · `[??]` peringatan · `[--]` info · `[>>]` skip.

| Log                                                                  | Arti                         |
| -------------------------------------------------------------------- | ---------------------------- |
| `[OK] [LOGIN] Authenticated`                                         | login sukses                 |
| `[!!] [LOGIN] GAGAL -- dilempar ke ...`                              | NIM/password salah           |
| `[--] [SCAN] Scan awal: 1 siap \| 1 sudah \| 0 belum buka ...`       | ringkasan scan per warna     |
| `[--] [ABSEN] target: NamaMatkul (jam)`                              | mulai proses absen           |
| `[??] [RETRY] percobaan 1/5 masih biru, tekan lagi`                  | belum berhasil, diulang      |
| `[OK] [ABSEN] BERHASIL (percobaan N): NamaMatkul`                    | **absen berhasil**           |
| `[!!] [ABSEN] GAGAL setelah N percobaan: NamaMatkul. Kemungkinan...` | **absen gagal** + sebab      |
| `[??] [SESSION] Sesi habis -- re-login...`                           | sesi berakhir, auto re-login |
| `[!!] [ERROR] request gagal...`                                      | error jaringan/request       |

Di `windows/` dan `termux/`, rincian per mata kuliah **sengaja tidak ditulis ke log** —
semuanya sudah ada di tabel **Jadwal Hari Ini** lengkap dengan alasannya, jadi log hanya
memuat kejadian penting. (Di mode plain text yang tidak punya tabel, daftar jadwal dicetak
sekali tiap kali ada status yang berubah.) Versi `linux/` masih menulis baris
`[>>] [SKIP] (warna) alasan -- Matkul` untuk tiap baris non-biru.

Status tiap mata kuliah dibaca dari tabel **Jadwal Hari Ini**, bukan dari log.
Hanya ada **empat** status, mengikuti warna tombol di halaman akademik:

| Status | Warna tombol | Arti |
|---|---|---|
| `SUDAH ABSEN` | hijau | absensi sudah tercatat |
| `SIAP ABSEN` | biru | bisa diabsen sekarang — akan diklik otomatis |
| `BELUM BUKA` | kuning | dosen belum membuka sesi absen |
| `BELUM WAKTUNYA` | merah | di luar jam absensi |

Kolom terakhir tabel berisi **nama dosen pengampu** (kode di depannya dibuang),
bukan alasan status — alasannya sudah terbaca dari badge statusnya sendiri.

Begitu sebuah baris berhasil diabsenkan, statusnya **langsung berubah jadi
`SUDAH ABSEN`** — tidak ada status "BERHASIL" terpisah. Kalau percobaannya gagal,
barisnya tetap `SIAP ABSEN` dan diulang (sebab gagalnya muncul di Log Aktivitas),
sampai semua yang biru berubah hijau. Pada mode loop, pengulangan berikutnya
menunggu interval berikutnya.

### Mode diagnostik `--dump` (engine)

Kalau tombol biru tidak terdeteksi, dump HTML halaman absen untuk dianalisis:

```bash
python auto_absen.py --engine http --dump        # simpan ke absen-dump.html
```

File berisi HTML mentah (jangan di-commit — sudah di-`.gitignore`). Kirim strukturnya untuk penyesuaian selector.

## Keamanan

- Kredensial disimpan **lokal** (`chrome.storage` untuk extension; `.env` untuk engine). Tidak dikirim ke server selain `akademik.polban.ac.id`.
