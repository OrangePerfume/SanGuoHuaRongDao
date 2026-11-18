@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [INFO] First install dependencies: py -3.12 -m venv .venv
  echo [INFO] Then: .venv\Scripts\python -m pip install -r requirements.txt
  exit /b 1
)
".venv\Scripts\python.exe" main.py
exit /b %errorlevel%
