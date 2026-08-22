@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

rem =====================================================================
rem DUZELTME: kullanicilar bu dosyayi WinRAR/7-Zip icinden CIKARMADAN,
rem dogrudan cift tiklayarak calistirdiginda, arsiv programi YALNIZ bu
rem TEK dosyayi gecici bir klasore (ornegin
rem C:\Users\...\AppData\Local\Temp\Rar$DIxxxxx.xxxxx.rartemp) aciyor -
rem requirements.txt gibi DIGER TUM dosyalar hic cikarilmiyor. Sonuc:
rem pip "Could not open requirements file" gibi anlasilmaz bir hatayla
rem duruyordu. Artik bu durum ERKEN tespit edilip ACIK bir Turkce
rem yonlendirme gosteriliyor.
echo %~dp0 | findstr /i "\\Temp\\" >nul
if not errorlevel 1 (
    echo %~dp0 | findstr /i /C:"rartemp" /C:"7zO" /C:"WinRAR" /C:"Temp1_" >nul
    if not errorlevel 1 (
        echo ================================================================
        echo  HATA: Bu dosya bir GECICI klasorden calistiriliyor.
        echo ================================================================
        echo.
        echo  Bu ZIP/RAR dosyasini CIKARMADAN, dogrudan icinden cift
        echo  tiklayarak actiniz - bu yuzden requirements.txt gibi diger
        echo  gerekli dosyalar bulunamiyor.
        echo.
        echo  DOGRU YONTEM:
        echo   1^) Bu ZIP/RAR dosyasina SAG TIKLAYIN
        echo   2^) "Buraya Cikart" veya "Extract All" secin
        echo   3^) Cikan GERCEK klasore girin ^(orn. C:\BASDAS^)
        echo   4^) KURULUM.bat'i O KLASORDEN calistirin
        echo.
        pause
        exit /b 1
    )
)
if not exist "%~dp0requirements.txt" (
    echo ================================================================
    echo  HATA: requirements.txt bulunamadi.
    echo ================================================================
    echo.
    echo  KURULUM.bat'in yaninda requirements.txt dosyasi yok. Paketin
    echo  TAMAMININ ayni klasorde oldugundan emin olun ^(ZIP'i TAM olarak
    echo  cikardiginizdan emin olun, yalniz bu dosyayi tasimayin^).
    echo.
    pause
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "APP_VERSION=19.21.28"
set "VENV_DIR=%LOCALAPPDATA%\OMEHR_RUNTIME\venv"
set "VENVPY=%VENV_DIR%\Scripts\python.exe"

rem =====================================================================
rem BASDAS V19.21.28 - MASAUSTU UYUMLU ILK KURULUM
rem Uygulama klasoru Masaustunde kalabilir. Uzun yol sorununu onlemek icin
rem sanal ortam kisa bir sistem klasorunde tutulur.
rem =====================================================================

echo ================================================================
echo  BASDAS V19.21.28 - Masaustu Uyumlu Ilk Kurulum
echo ================================================================
echo.
echo  Uygulama konumu: %cd%
echo  Sanal ortam:      %VENV_DIR%
echo.

if not exist "%LOCALAPPDATA%\OMEHR_RUNTIME" mkdir "%LOCALAPPDATA%\OMEHR_RUNTIME"

 echo [1/8] Uyumlu Python surumu kontrol ediliyor...
set "BASEPY="
where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 --version >nul 2>nul
    if not errorlevel 1 set "BASEPY=py -3.12"
)
if not defined BASEPY if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "BASEPY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined BASEPY if exist "%ProgramFiles%\Python312\python.exe" set "BASEPY=%ProgramFiles%\Python312\python.exe"
if not defined BASEPY (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3.11 --version >nul 2>nul
        if not errorlevel 1 set "BASEPY=py -3.11"
    )
)
if not defined BASEPY if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "BASEPY=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined BASEPY if exist "%ProgramFiles%\Python311\python.exe" set "BASEPY=%ProgramFiles%\Python311\python.exe"

if not defined BASEPY (
    echo   Python 3.12 veya 3.11 bulunamadi.
    where winget >nul 2>nul
    if errorlevel 1 (
        echo   HATA: winget bulunamadi. Python 3.12 x64 kurup tekrar deneyin.
        pause
        exit /b 1
    )
    echo   Python 3.12 winget ile kuruluyor...
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo   HATA: Python 3.12 kurulumu basarisiz oldu.
        pause
        exit /b 1
    )
    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "BASEPY=%LocalAppData%\Programs\Python\Python312\python.exe"
    ) else (
        echo   Python kuruldu. Bu pencereyi kapatip KURULUM.bat dosyasini tekrar calistirin.
        pause
        exit /b 1
    )
)

%BASEPY% -c "import sys; assert sys.version_info[:2] in ((3,11),(3,12)), sys.version" >nul 2>nul
if errorlevel 1 (
    echo   HATA: Yalnizca Python 3.11 veya 3.12 destekleniyor.
    pause
    exit /b 1
)

echo [2/8] Kisa sistem yolunda sanal ortam hazirlaniyor...
if exist "%VENVPY%" (
    "%VENVPY%" -c "import sys; assert sys.version_info[:2] in ((3,11),(3,12))" >nul 2>nul
    if errorlevel 1 rmdir /s /q "%VENV_DIR%"
) else if exist "%VENV_DIR%" (
    rmdir /s /q "%VENV_DIR%"
)
if not exist "%VENVPY%" (
    %BASEPY% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo   HATA: Sanal ortam olusturulamadi.
        pause
        exit /b 1
    )
)

echo [3/8] Kutuphaneler kuruluyor ^(yalnizca ilk kurulum^) ...
"%VENVPY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo   HATA: pip guncellenemedi.
    pause
    exit /b 1
)
"%VENVPY%" -m pip install -r "%cd%\requirements.txt"
if errorlevel 1 (
    echo   HATA: Kutuphane kurulumu basarisiz oldu.
    pause
    exit /b 1
)
"%VENVPY%" -c "import streamlit,pandas,openpyxl,reportlab,plotly,fastapi,uvicorn; print('Kritik kutuphaneler hazir.')"
if errorlevel 1 (
    echo   HATA: Kritik kutuphanelerden biri yuklenemedi.
    pause
    exit /b 1
)

echo [4/8] Python hesap motoru kontrol ediliyor...
"%VENVPY%" -c "from services.formula_bagimsiz_hesapla import statiklestir; print('Python hesap motoru hazir. LibreOffice zorunlu degildir.')"
if errorlevel 1 (
    echo   HATA: Python hesap motoru yuklenemedi.
    pause
    exit /b 1
)

echo [5/8] Ilk kullanicilar guvenlik veritabanina aktariliyor...
"%VENVPY%" "%cd%\INITIAL_PASSWORD_IMPORT.py"
if errorlevel 1 (
    echo   HATA: Ilk kullanici aktarimi basarisiz oldu.
    pause
    exit /b 1
)

echo [6/8] Masaustu kisayolu olusturuluyor...
set "KISAYOL=%USERPROFILE%\Desktop\BASDAS Norm Kadro Sistemi.bat"
> "%KISAYOL%" echo @echo off
>> "%KISAYOL%" echo cd /d "%cd%"
>> "%KISAYOL%" echo call "%cd%\OMEHR_CURRENT_BASLAT.bat"
echo   Kisayol olusturuldu: %KISAYOL%

echo [7/8] Zamanlanmis gorevler ^(istege bagli^) ...
set /p ZAMANLA="  Gunluk gorevleri kurmak ister misiniz? (E/H): "
if /i "%ZAMANLA%"=="E" (
    if exist "ZAMANLAYICI_KUR.bat" call ZAMANLAYICI_KUR.bat
)

echo [8/8] Saglik kontrolu yapiliyor...
"%VENVPY%" "%cd%\system_health_check.py"
if errorlevel 1 (
    echo   HATA: Saglik kontrolu kritik bir sorun buldu.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo  KURULUM TAMAMLANDI.
echo  Program Masaustundeki mevcut klasorunde kalabilir.
echo  Gunluk kullanim: OMEHR_CURRENT_BASLAT.bat
echo ================================================================
pause
exit /b 0
