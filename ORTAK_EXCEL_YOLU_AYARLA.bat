@echo off
chcp 65001 >nul
setlocal
cls
echo ============================================================
echo   BASDAS / OMEHR - 3 PC ORTAK EXCEL AYARI
echo ============================================================
echo.
echo Ornek yol: \\SUNUCU\OMEHR\BASDAS_AI_NORM_TRANSFER_INPUT.xlsx
echo Bu yol 3 bilgisayarda da AYNI olmalidir.
echo.
set /p ORTAK_YOL=Ortak Excel tam yolunu girin: 
if "%ORTAK_YOL%"=="" (
  echo Yol bos birakildi. Islem iptal.
  pause
  exit /b 1
)
if not exist "%ORTAK_YOL%" (
  echo.
  echo UYARI: Dosya bu bilgisayardan bulunamadi:
  echo %ORTAK_YOL%
  echo Once ag klasoru erisimini kontrol edin.
  pause
  exit /b 2
)
setx BASDAS_INPUT_PATH "%ORTAK_YOL%" >nul
if errorlevel 1 (
  echo Ortam ayari kaydedilemedi. Komut Istemi'ni normal kullanici olarak tekrar deneyin.
  pause
  exit /b 3
)
echo.
echo TAMAM: BASDAS_INPUT_PATH kaydedildi.
echo Panel aciksa kapatip yeniden baslatin.
echo Diger PC'lerde de bu dosyayi calistirip AYNI yolu girin.
pause
