@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem =====================================================================
rem PUANTAJ_HATIRLATMA_CALISTIR.bat
rem =====================================================================
rem Sessiz, etkilesimsiz calisir. Windows Gorev Zamanlayicisi tarafindan
rem her sabah saat 09:00'de tetiklenmek uzere tasarlanmistir. Otomatik
rem kaydolmak icin ZAMANLAYICI_KUR.bat dosyasini calistirin (ayni betik
rem hem 09:00 puantaj hatirlatmasini hem 12:00 tam rapor calistirmasini
rem kaydeder).
rem =====================================================================

set "BASEPY="
if exist ".venv\Scripts\python.exe" set "BASEPY=.venv\Scripts\python.exe"
if not defined BASEPY (
  where py >nul 2>nul
  if not errorlevel 1 set "BASEPY=py -3"
)
if not defined BASEPY (
  where python >nul 2>nul
  if not errorlevel 1 set "BASEPY=python"
)
if not defined BASEPY (
  echo HATA: Python bulunamadi. > logs\Puantaj_Hatirlatma_HATA.log
  exit /b 1
)

if not exist "logs" mkdir "logs"
%BASEPY% GUNLUK_PUANTAJ_HATIRLATMA.py
exit /b %errorlevel%
