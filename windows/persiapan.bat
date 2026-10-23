@echo off
REM ============================================================
REM  Polban Auto Absen - Persiapan sebelum jalan
REM
REM  SATU file ini dipanggil oleh SEMUA launcher (auto_absen.bat dan
REM  absen_sekali.bat) supaya keduanya tidak pernah beda perilaku.
REM  Kalau ada syarat baru, cukup diubah di sini sekali.
REM
REM  Isi pemeriksaan:
REM    1. Python portable ada                -> kalau tidak, jalankan install.bat
REM    2. requests / beautifulsoup4 / rich   -> unduh yang kurang (sekali saja)
REM    3. .env ada dan POLBAN_USERNAME terisi -> peringatkan kalau belum
REM
REM  Exit code: 0 = siap jalan, 1 = batal (pesan sudah dicetak).
REM ============================================================
setlocal EnableExtensions DisableDelayedExpansion
set "PYDIR=%~dp0python"
set "PYEXE=%PYDIR%\python.exe"

REM ---------- 1. Python portable ----------
if not exist "%PYEXE%" (
  echo [Setup] Python portable belum ada -- menjalankan install.bat...
  call "%~dp0install.bat" || exit /b 1
)
if not exist "%PYEXE%" (
  echo [Setup] GAGAL: Python portable tidak ditemukan di "%PYDIR%".
  exit /b 1
)

REM ---------- 2. Dependensi ----------
REM Satu kali cek untuk semua. bs4 = paket beautifulsoup4.
"%PYEXE%" -c "import requests, bs4, rich" >nul 2>&1
if errorlevel 1 (
  echo [Setup] Dependensi belum lengkap -- mengunduh sekali saja ^(butuh internet^)...

  REM pip bisa belum aktif di instalasi lama: aktifkan lewat install.bat.
  "%PYEXE%" -m pip --version >nul 2>&1
  if errorlevel 1 (
    echo [Setup] pip belum aktif -- menjalankan install.bat...
    call "%~dp0install.bat" || exit /b 1
  )

  "%PYEXE%" -m pip install --quiet --no-warn-script-location requests beautifulsoup4 rich

  "%PYEXE%" -c "import requests, bs4, rich" >nul 2>&1
  if errorlevel 1 (
    echo.
    echo [Setup] GAGAL memasang dependensi.
    echo         Pastikan terhubung internet, lalu jalankan lagi.
    echo         Atau pasang manual:
    echo           "%PYEXE%" -m pip install requests beautifulsoup4 rich
    exit /b 1
  )
  echo [Setup] Dependensi lengkap.
)

REM ---------- 3. Config .env ----------
REM DisableDelayedExpansion dipakai supaya tanda '!' di password tetap aman.
if not exist "%~dp0.env" (
  if exist "%~dp0.env.example" (
    copy "%~dp0.env.example" "%~dp0.env" >nul
    echo [Setup] .env dibuat dari template -- EDIT dulu: isi NIM ^& password.
  ) else (
    echo [Setup] GAGAL: .env dan .env.example sama-sama tidak ada.
    exit /b 1
  )
)
findstr /R /C:"^POLBAN_USERNAME=." "%~dp0.env" >nul 2>&1
if errorlevel 1 (
  echo.
  echo [Setup] POLBAN_USERNAME di .env sepertinya masih kosong.
  echo         Buka .env lalu isi POLBAN_USERNAME dan POLBAN_PASSWORD.
  echo.
  choice /C YN /M "Tetap lanjut"
  if errorlevel 2 exit /b 1
)

exit /b 0
