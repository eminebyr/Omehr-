@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

rem DUZELTME: ayni koruma KURULUM.bat'ta oldugu gibi burada da - kullanici
rem bu dosyayi da ZIP/RAR icinden, cikarma yapmadan calistirabilir.
echo %~dp0 | findstr /i "\\Temp\\" >nul
if not errorlevel 1 (
    echo %~dp0 | findstr /i /C:"rartemp" /C:"7zO" /C:"WinRAR" /C:"Temp1_" >nul
    if not errorlevel 1 (
        echo HATA: Bu dosya bir GECICI klasorden calistiriliyor.
        echo Once ZIP/RAR dosyasini SAG TIKLAYIP "Buraya Cikart" secin,
        echo sonra bu dosyayi cikan GERCEK klasorden calistirin.
        pause
        exit /b 1
    )
)

set "OMEHR_SEND_EMAIL=1"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "APP_VERSION=19.21.28"
set "VENV_DIR=%LOCALAPPDATA%\OMEHR_RUNTIME\venv"
set "BASEPY=%VENV_DIR%\Scripts\python.exe"

if not exist "logs" mkdir "logs"

echo ================================================================
echo  BASDAS V19.21.28 - Gunluk Baslatma
echo ================================================================
echo.

echo [1/5] Kurulum ortami kontrol ediliyor...
if not exist "%BASEPY%" (
    echo HATA: Sanal ortam bulunamadi.
    echo Once bu klasordeki KURULUM.bat dosyasini bir kez calistirin.
    pause
    exit /b 1
)
"%BASEPY%" -c "import sys; assert sys.version_info[:2] in ((3,11),(3,12))" >nul 2>nul
if errorlevel 1 (
    echo HATA: Sanal ortam bozuk veya desteklenmeyen Python kullaniyor.
    echo KURULUM.bat dosyasini yeniden calistirin.
    pause
    exit /b 1
)
"%BASEPY%" -c "import streamlit,pandas,openpyxl,reportlab,plotly,fastapi,uvicorn" >nul 2>nul
if errorlevel 1 (
    echo HATA: Kritik kutuphaneler eksik. KURULUM.bat dosyasini yeniden calistirin.
    pause
    exit /b 1
)

echo [2/5] Kullanici ve sistem sagligi kontrol ediliyor...
"%BASEPY%" "%cd%\INITIAL_PASSWORD_IMPORT.py"
if errorlevel 1 (
    echo HATA: Kullanici guvenlik aktarimi basarisiz oldu.
    pause
    exit /b 1
)
"%BASEPY%" "%cd%\system_health_check.py"
if errorlevel 1 (
    echo HATA: Saglik kontrolu kritik bir sorun buldu.
    pause
    exit /b 1
)

echo [3/5] Ana motor calistiriliyor...
"%BASEPY%" "%cd%\main.py"
if errorlevel 1 (
    echo HATA: Ana motor basarisiz oldu. logs klasorunu kontrol edin.
    pause
    exit /b 1
)

echo [4/5] Eski web sureci kapatiliyor ve yeni panel baslatiliyor...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8501" ^| findstr "LISTENING"') do (
    echo   8501 portundaki eski surec kapatiliyor: PID %%P
    taskkill /PID %%P /F >nul 2>nul
)
timeout /t 2 /nobreak >nul
start "BASDAS Worker" /MIN cmd /c ""%BASEPY%" "%cd%\worker.py" >> "%cd%\logs\CURRENT_Worker_Console.log" 2>&1"
start "BASDAS Monitoring" /MIN cmd /c ""%BASEPY%" -m uvicorn monitoring_server:app --host 127.0.0.1 --port 9108 >> "%cd%\logs\CURRENT_Monitoring_Console.log" 2>&1"
start "BASDAS Alerts" /MIN cmd /c ""%BASEPY%" "%cd%\alert_watcher.py" >> "%cd%\logs\CURRENT_Alerts_Console.log" 2>&1"
start "BASDAS Web" /MIN cmd /c "cd /d "%cd%" && "%BASEPY%" -m streamlit run "%cd%\web\app.py" --server.port 8501 --server.headless true >> "%cd%\logs\CURRENT_Web_Console.log" 2>&1"

echo [5/5] Web paneli bekleniyor...
set "DENEME=0"
:BEKLE
"%BASEPY%" -c "import socket; s=socket.socket(); s.settimeout(.5); r=s.connect_ex(('127.0.0.1',8501)); s.close(); raise SystemExit(0 if r==0 else 1)" >nul 2>nul
if not errorlevel 1 goto BASARILI
set /a DENEME+=1
if !DENEME! GEQ 90 goto ZAMANASIMI
timeout /t 1 /nobreak >nul
goto BEKLE

:BASARILI
echo.
echo BASARILI: http://localhost:8501
start "" "http://localhost:8501/?v=19.21.28"
exit /b 0

:ZAMANASIMI
echo.
echo HATA: Web paneli 90 saniye icinde acilamadi.
echo logs\CURRENT_Web_Console.log dosyasini kontrol edin.
pause
exit /b 1
