@echo off
REM ============================================================
REM  Polban Auto Absen - Launcher Windows (SEKALI jalan, untuk tes)
REM  Klik 2x file ini untuk scan+absen satu kali lalu berhenti.
REM
REM  Isi file ini SENGAJA dibuat kembar dengan auto_absen.bat --
REM  satu-satunya beda ada di baris "set ARGS" dan judul jendela.
REM  Semua pemeriksaan sebelum jalan ada di persiapan.bat.
REM ============================================================
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "PYDIR=%~dp0python"
set "ARGS=--engine http --once"
set "JUDUL=Polban Auto Absen (sekali)"

REM Python portable + dependensi + .env (auto-unduh / auto-buat yang kurang).
call "%~dp0persiapan.bat" || (pause & exit /b 1)

REM UTF-8 + VT supaya border & warna live dashboard (tui.py) tampil benar,
REM termasuk di cmd.exe klasik. Code page lama dikembalikan setelah selesai.
for /f "tokens=2 delims=:." %%c in ('chcp') do set "OLDCP=%%c"
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

title %JUDUL%
REM Mode --once memakai dashboard yang sama, hanya TANPA alternate screen --
REM jadi dashboard tetap terlihat setelah proses selesai.
"%PYDIR%\python.exe" -u "%~dp0auto_absen.py" %ARGS% %*

if defined OLDCP chcp %OLDCP% >nul
echo.
echo Selesai / berhenti.
pause
