@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title BASDAS CURRENT - Gunluk Sube Maili

if not exist ".venv\Scripts\python.exe" (
  echo HATA: Once BASDAS_CURRENT_BASLAT.bat dosyasini bir kez calistirin.
  pause
  exit /b 1
)

if not exist "GUNLUK_SUBE_MAIL_METNI.txt" (
  echo HATA: GUNLUK_SUBE_MAIL_METNI.txt bulunamadi.
  pause
  exit /b 1
)

echo [1/3] Gunluk mail metni aciliyor.
echo Metni duzenleyin, kaydedin ve Not Defteri'ni kapatin.
start /wait notepad.exe "GUNLUK_SUBE_MAIL_METNI.txt"

echo [2/3] Alicilar ve mesajlar kontrol ediliyor...
".venv\Scripts\python.exe" daily_branch_mail.py --dry-run
if errorlevel 1 (
  echo HATA: Onizleme olusturulamadi. Yukaridaki hata mesajini kontrol edin.
  pause
  exit /b 1
)

echo.
echo Onizleme: logs\CURRENT_Gunluk_Sube_Mail_Onizleme.txt
start /wait notepad.exe "logs\CURRENT_Gunluk_Sube_Mail_Onizleme.txt"
echo.
set /p "ONAY=Listedeki subelere bu e-postayi gondermek icin EVET yazin: "
if /I not "%ONAY%"=="EVET" (
  echo IPTAL: Hicbir e-posta gonderilmedi.
  pause
  exit /b 0
)

echo [3/3] E-postalar gonderiliyor...
".venv\Scripts\python.exe" daily_branch_mail.py
if errorlevel 1 (
  echo HATA: Bazi veya tum e-postalar gonderilemedi.
  echo Ayrinti: logs\CURRENT_Gunluk_Sube_Mail_Log.json
  pause
  exit /b 1
)

echo BASARILI: Gunluk sube e-postalari gonderildi.
echo Kayit: logs\CURRENT_Gunluk_Sube_Mail_Log.json
pause
exit /b 0
