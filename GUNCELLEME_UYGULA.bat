@echo off
REM GUNCELLEME_UYGULA.bat - indirilen bir guncelleme paketini uygular.
REM Kullanim: GUNCELLEME_UYGULA.bat <paket_klasoru> <yeni_surum>
cd /d "%~dp0"
if "%~1"=="" (
    echo Kullanim: GUNCELLEME_UYGULA.bat ^<paket_klasoru^> ^<yeni_surum^>
    echo Ornek:    GUNCELLEME_UYGULA.bat C:\indirilenler\omehr_v19_21_3 19.21.3
    exit /b 2
)
python GUNCELLEME_UYGULA.py %1 %2
pause
