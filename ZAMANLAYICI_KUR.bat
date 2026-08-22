@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem =====================================================================
rem ZAMANLAYICI_KUR.bat
rem =====================================================================
rem OMEHR_Puantaj_Hatirlatma (her gun 09:00) ve OMEHR_Gunluk_Rapor
rem (her gun 12:00) Windows Gorev Zamanlayicisi gorevlerini kurar.
rem Yonetici olarak calistirilmasi gerekir (schtasks bunu ister).
rem Gorevleri silmek icin:
rem   schtasks /delete /tn "OMEHR_Puantaj_Hatirlatma" /f
rem   schtasks /delete /tn "OMEHR_Gunluk_Rapor" /f
rem =====================================================================

net session >nul 2>nul
if errorlevel 1 (
    echo HATA: Bu betik Yonetici olarak calistirilmalidir.
    echo Dosyaya sag tiklayip "Yonetici olarak calistir" secin.
    pause
    exit /b 1
)

set "KOK=%~dp0"
if "%KOK:~-1%"=="\" set "KOK=%KOK:~0,-1%"

echo Gorev 1/2: OMEHR_Puantaj_Hatirlatma (her gun 09:00)...
schtasks /create /tn "OMEHR_Puantaj_Hatirlatma" ^
    /tr "\"%KOK%\PUANTAJ_HATIRLATMA_CALISTIR.bat\"" ^
    /sc daily /st 09:00 /f
if errorlevel 1 (
    echo   HATA: Gorev olusturulamadi.
) else (
    echo   OK.
)

echo Gorev 2/2: OMEHR_Gunluk_Rapor (her gun 12:00)...
schtasks /create /tn "OMEHR_Gunluk_Rapor" ^
    /tr "\"%KOK%\GUNLUK_OTOMATIK_CALISTIR.bat\"" ^
    /sc daily /st 12:00 /f
if errorlevel 1 (
    echo   HATA: Gorev olusturulamadi.
) else (
    echo   OK.
)

echo.
echo Gorevleri Windows Gorev Zamanlayicisi'nda ("Son Calisma Sonucu" alani)
echo izleyebilirsiniz. Kaldirmak icin:
echo   schtasks /delete /tn "OMEHR_Puantaj_Hatirlatma" /f
echo   schtasks /delete /tn "OMEHR_Gunluk_Rapor" /f
pause
exit /b 0
