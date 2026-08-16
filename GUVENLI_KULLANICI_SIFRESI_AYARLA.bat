@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" SECURE_USER_SETUP.py
) else (
  py SECURE_USER_SETUP.py
)
pause
