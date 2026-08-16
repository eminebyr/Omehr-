@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem =====================================================================
rem ADMIN_6_PANEL_AC.bat
rem =====================================================================
rem Sistem calisiyorken ayni web uygulamasini alti ayri tarayici
rem penceresinde acar. Rol ve ekran testlerinde kullanilabilir. Uretimde
rem gereksiz yere cok pencere acmak kaynak tuketimini artirabilir.
rem =====================================================================

set "URL=http://localhost:8501"
if exist ".venv\Scripts\python.exe" (
    set "BASEPY=.venv\Scripts\python.exe"
) else (
    set "BASEPY=python"
)

"%BASEPY%" -c "import socket; s=socket.socket(); s.settimeout(.5); r=s.connect_ex(('127.0.0.1',8501)); s.close(); raise SystemExit(0 if r==0 else 1)" >nul 2>nul
if errorlevel 1 (
    echo HATA: Web sistemi calismiyor.
    echo Once BASDAS_CURRENT_BASLAT.bat dosyasini calistirin.
    pause
    exit /b 1
)

for /L %%i in (1,1,6) do (
    start "" "%URL%"
)
echo BASARILI: 6 admin paneli acildi.
