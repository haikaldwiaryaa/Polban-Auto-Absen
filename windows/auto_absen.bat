@echo off
REM ============================================================
REM  Polban Auto Absen - Launcher Windows
REM  Klik 2x file ini untuk menjalankan auto-absen.
REM  Pertama kali: jalankan install.bat dulu sekali.
REM ============================================================
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "PYDIR=%~dp0python"

REM Kalau Python embedded belum ada, jalankan installer dulu
if not exist "%PYDIR%\python.exe" (
  echo Python belum terinstall. Menjalankan install.bat dulu...
  call "%~dp0install.bat" || (echo Install gagal.& pause & exit /b 1)
)

REM Cek .env sudah diisi (DisableDelayedExpansion agar '!' di password aman)
if not exist "%~dp0.env" (
  echo [PERINGATAN] File .env tidak ada. Jalankan install.bat dulu.
  pause & exit /b 1
)
findstr /R /C:"^POLBAN_USERNAME=." "%~dp0.env" >nul 2>&1
if errorlevel 1 (
  echo.
  echo [PERINGATAN] POLBAN_USERNAME di .env sepertinya masih kosong.
  echo Buka .env lalu isi POLBAN_USERNAME dan POLBAN_PASSWORD, lalu jalankan lagi.
  echo.
  choice /C YN /M "Tetap lanjut"
  if errorlevel 2 exit /b 1
)

title Polban Auto Absen
echo ============================================================
echo  Polban Auto Absen (engine HTTP) - tekan Ctrl+C untuk berhenti
echo ============================================================
"%PYDIR%\python.exe" -u "%~dp0auto_absen.py" --engine http
echo.
echo Selesai / berhenti.
pause
