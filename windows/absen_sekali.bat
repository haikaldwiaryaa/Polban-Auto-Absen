@echo off
REM ============================================================
REM  Polban Auto Absen - Jalankan SEKALI lalu tutup (untuk tes)
REM ============================================================
setlocal
cd /d "%~dp0"
set "PYDIR=%~dp0python"
if not exist "%PYDIR%\python.exe" ( call "%~dp0install.bat" || (pause & exit /b 1) )
title Polban Auto Absen (sekali)
"%PYDIR%\python.exe" -u "%~dp0auto_absen.py" --engine http --once
echo.
pause
