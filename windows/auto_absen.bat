@echo off
REM ============================================================
REM  Polban Auto Absen - Launcher Windows (mode LOOP)
REM  Klik 2x file ini untuk menjalankan auto-absen terus-menerus.
REM
REM  Isi file ini SENGAJA dibuat kembar dengan absen_sekali.bat --
REM  satu-satunya beda ada di baris "set ARGS" dan judul jendela.
REM  Semua pemeriksaan sebelum jalan ada di persiapan.bat.
REM ============================================================
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "PYDIR=%~dp0python"
set "ARGS=--engine http"
set "JUDUL=Polban Auto Absen"

REM Python portable + dependensi + .env (auto-unduh / auto-buat yang kurang).
call "%~dp0persiapan.bat" || (pause & exit /b 1)

REM UTF-8 + VT supaya border & warna live dashboard (tui.py) tampil benar,
REM termasuk di cmd.exe klasik. Code page lama dikembalikan setelah selesai.
for /f "tokens=2 delims=:." %%c in ('chcp') do set "OLDCP=%%c"
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

title %JUDUL%
REM Banner & status digambar oleh live dashboard, bukan oleh .bat ini.
"%PYDIR%\python.exe" -u "%~dp0auto_absen.py" %ARGS% %*

if defined OLDCP chcp %OLDCP% >nul
echo.
echo Selesai / berhenti.
pause
