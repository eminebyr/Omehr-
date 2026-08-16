@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem =====================================================================
rem GUNLUK_OTOMATIK_CALISTIR.bat
rem =====================================================================
rem Bu betik BASDAS_CURRENT_BASLAT.bat'tan farklidir: interaktif degildir,
rem "Bir tusa basin" gibi bekleme icermez, hicbir pencere acik kalmaz.
rem Windows Gorev Zamanlayicisi (Task Scheduler) tarafindan gunluk/haftalik
rem tetiklenmek uzere tasarlanmistir. Otomatik kaydolmak icin
rem ZAMANLAYICI_KUR.bat dosyasini BIR KEZ calistirin.
rem
rem Ne yapar: formulleri yeniden hesaplar, AI/istatistik motorunu calistirir,
rem tum PDF/Excel raporlarini uretir ve (BASDAS_SEND_EMAIL=1 ise) Outlook
rem uzerinden gercek e-postalari gonderir. Cikti logs\Otomatik_Calistirma_*.log
rem dosyasina yazilir; masaustunde hicbir pencere kalmaz.
rem =====================================================================

set "BASDAS_SEND_EMAIL=1"
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
  echo HATA: Python bulunamadi. > logs\Otomatik_Calistirma_HATA.log
  exit /b 1
)

if not exist "logs" mkdir "logs"
for /f "tokens=1-4 delims=/. " %%a in ("%date%") do set "GUN=%%c-%%b-%%a"
set "LOGDOSYA=logs\Otomatik_Calistirma_%GUN%.log"

echo [%date% %time%] Otomatik calistirma basladi >> "%LOGDOSYA%"
%BASEPY% main.py >> "%LOGDOSYA%" 2>&1
if errorlevel 1 (
  echo [%date% %time%] HATA: main.py basarisiz oldu, cikis kodu: %errorlevel% >> "%LOGDOSYA%"
  exit /b 1
)
echo [%date% %time%] Otomatik calistirma basariyla tamamlandi >> "%LOGDOSYA%"
exit /b 0
