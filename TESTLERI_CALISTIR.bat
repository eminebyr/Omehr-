@echo off
REM Baslangic test iskeletini calistirir (tests/README.md'deki kapsamla sinirli).
REM Bu, eski "YESIL_PAKET_TESTI.bat"in tam yerine gecmez (bkz. tests/README.md
REM "Kapsam DISI" bolumu) - yalniz bu turda eklenen testleri calistirir.
cd /d "%~dp0"

echo BASDAS - baslangic test iskeleti calistiriliyor...
python -m pytest tests/ %*

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SONUC: YESIL - tum testler gecti.
) else (
    echo.
    echo SONUC: KIRMIZI - en az bir test basarisiz oldu, yukariyi kontrol edin.
)
exit /b %ERRORLEVEL%
