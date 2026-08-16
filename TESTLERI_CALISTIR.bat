@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

rem DUZELTME: ayni koruma diger .bat dosyalarinda oldugu gibi burada da.
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

rem DUZELTME (KRITIK): onceden "python" (SISTEM Python'u) kullaniliyordu -
rem KURULUM.bat'in kurdugu SANAL ORTAM (pandas/streamlit/pytest vb. TUM
rem bagimliliklarin oldugu yer) DEGIL. Sistem Python'unda bu kutuphaneler
rem YUKLU DEGILSE testler hemen "ModuleNotFoundError" ile cokerdi.
set "VENV_DIR=%LOCALAPPDATA%\BASDAS_RUNTIME\venv"
set "VENVPY=%VENV_DIR%\Scripts\python.exe"
if not exist "%VENVPY%" (
    echo HATA: Sanal ortam bulunamadi: %VENVPY%
    echo Once KURULUM.bat calistirilmis olmali.
    pause
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
rem DUZELTME: PYTHONPATH ayarlanmiyordu - testlerin cogu "from services.X
rem import Y" seklinde proje-koku-goreceli import kullanir, bu PYTHONPATH
rem olmadan calismaz.
set "PYTHONPATH=%~dp0"

echo BASDAS - test paketi calistiriliyor (bu birkac dakika surebilir)...
echo Sanal ortam: %VENVPY%
echo.

rem DUZELTME: yerel PostgreSQL kurulu/yapilandirilmis DEGILSE (cogu
rem Windows kurulumunda boyle), PostgreSQL gerektiren birkac test
rem BASARISIZ olur - ama bu GERCEK bir kod hatasi degildir, ortam
rem eksikligidir. BASDAS_TEST_POSTGRES_DSN ayarli degilse bu testler
rem otomatik atlanir (ayni mantik main main.py/CI dogrulamasinda
rem kullanildi).
if not defined BASDAS_TEST_POSTGRES_DSN (
    echo NOT: BASDAS_TEST_POSTGRES_DSN ayarli degil - PostgreSQL gerektiren
    echo      birkac test atlanacak ^(bu bir HATA degildir^).
    "%VENVPY%" -m pytest tests/ -v --tb=short -k "not db_backed_input" %*
) else (
    "%VENVPY%" -m pytest tests/ -v --tb=short %*
)

set "TEST_SONUCU=%ERRORLEVEL%"

if %TEST_SONUCU% EQU 0 (
    echo.
    echo SONUC: YESIL - tum testler gecti.
) else (
    echo.
    echo SONUC: KIRMIZI - en az bir test basarisiz oldu, yukariyi kontrol edin.
)
exit /b %TEST_SONUCU%
