@echo off
REM ============================================================
REM  Polban Auto Absen - Installer Windows (sekali saja)
REM  Mengunduh Python embedded + dependensi, tanpa install sistem.
REM  Jalankan: klik 2x install.bat
REM ============================================================
setlocal
cd /d "%~dp0"
set "PYDIR=%~dp0python"
set "PYZIP=%~dp0python-embed.zip"
set "PYVER=3.11.9"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip"

echo [1/5] Cek Python embedded...
if exist "%PYDIR%\python.exe" goto havepy

echo       Mengunduh Python %PYVER% embedded...
powershell -NoProfile -Command "Invoke-WebRequest -Uri '%PYURL%' -OutFile '%PYZIP%'" || goto dl_fail
echo       Mengekstrak...
powershell -NoProfile -Command "Expand-Archive -Force '%PYZIP%' '%PYDIR%'" || goto dl_fail
del "%PYZIP%" >nul 2>&1

:havepy
echo [2/5] Aktifkan pip di embedded Python...
REM Hapus komentar "import site" di file ._pth agar pip bisa jalan
for %%f in ("%PYDIR%\python*._pth") do (
  powershell -NoProfile -Command "(Get-Content '%%f') -replace '#import site','import site' | Set-Content '%%f'"
)

echo [3/5] Unduh get-pip...
if not exist "%PYDIR%\Scripts\pip.exe" (
  powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PYDIR%\get-pip.py'" || goto dl_fail
  "%PYDIR%\python.exe" "%PYDIR%\get-pip.py" --no-warn-script-location || goto dl_fail
)

echo [4/5] Install dependensi (requests, beautifulsoup4)...
"%PYDIR%\python.exe" -m pip install --quiet --no-warn-script-location requests beautifulsoup4 || goto dl_fail

echo [5/5] Siapkan config...
if not exist "%~dp0.env" (
  if exist "%~dp0.env.example" (copy "%~dp0.env.example" "%~dp0.env" >nul) else (
    (echo POLBAN_USERNAME=& echo POLBAN_PASSWORD=& echo POLBAN_TARGET_URL=https://akademik.polban.ac.id/ajar/absen& echo POLBAN_INTERVAL=60& echo POLBAN_ENGINE=http) > "%~dp0.env"
  )
  echo       .env dibuat. EDIT dulu: isi NIM ^& password.
)

echo.
echo ============================================================
echo  SELESAI. Langkah selanjutnya:
echo   1. Edit .env (klik kanan -^> Edit / buka Notepad), isi:
echo        POLBAN_USERNAME=NIM_kamu
echo        POLBAN_PASSWORD=password_kamu
echo   2. Klik 2x  auto_absen.bat   untuk menjalankan.
echo ============================================================
pause
exit /b 0

:dl_fail
echo.
echo [ERROR] Gagal mengunduh/menginstall. Cek koneksi internet lalu coba lagi.
pause
exit /b 1
