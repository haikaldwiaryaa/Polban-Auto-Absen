# Contributing

Terima kasih ingin berkontribusi. Proyek ini sederhana — menjaga agar tetap mudah dipahami adalah prioritas.

## Prinsip
1. **Clean code** — nama variabel/fungsi deskriptif, fungsi kecil satu tugas, komentar untuk "kenapa" bukan "apa".
2. **Tanpa dependensi berat** — engine HTTP hanya `requests` + `beautifulsoup4`; browser hanya API standar.
3. **Jangan hardcode kredensial** — selalu lewat `.env` / storage browser.

## Struktur
- `userscript/` — Tampermonkey (satu file mandiri).
- `extension/` — Chrome MV3 (background, content, popup, options).
- `windows/` — launcher `.bat` (memakai `vps/auto_absen.py`).
- `vps/` — engine Python `auto_absen.py` (dipakai Windows, Termux, VPS).

## Sebelum commit
- Pastikan `.env`, `.clicked.json`, `windows/python/` tidak ikut (sudah di `.gitignore`).
- Uji sintaks: `node --check` untuk `.js`, `python -m py_compile` untuk `.py`.
- Uji login + deteksi tombol di situs asli bila memungkinkan.

## Melaporkan bug
Sertakan: versi (userscript/extension/windows), log dari panel/terminal, dan struktur tombol absen (dari menu Diagnostik) bila relevan.
