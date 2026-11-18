@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
set "PYEXE=py -3.12"
%PYEXE% --version >nul 2>&1
if errorlevel 1 (
    set "PYEXE=py -3"
    py -3 --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python 3.12 x64 is recommended. Install Python, then run build.cmd again.
        exit /b 1
    )
)
if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creating project virtual environment...
    %PYEXE% -m venv .venv
    if errorlevel 1 exit /b 1
)
set "P=.venv\Scripts\python.exe"
echo [2/5] Installing fixed game dependencies and build tool...
"%P%" -m pip install --disable-pip-version-check -r requirements-build.txt
if errorlevel 1 exit /b 1
echo [3/5] Running headless puzzle and model tests...
"%P%" -m unittest discover -s tests -v
if errorlevel 1 (
    echo [ERROR] Tests failed. Build aborted.
    exit /b 1
)
echo [4/5] Building 64-bit Windows executable...
"%P%" -m PyInstaller --noconfirm --clean --onedir --windowed --name SanGuoHuaRongDao --icon "huarongdao\assets\icon.ico" --add-data "huarongdao\assets;huarongdao\assets" main.py
if errorlevel 1 exit /b 1
echo [5/5] Checking output...
if not exist "dist\SanGuoHuaRongDao\SanGuoHuaRongDao.exe" (
    echo [ERROR] Expected executable is missing.
    exit /b 1
)
echo.
echo [SUCCESS] Output: dist\SanGuoHuaRongDao\SanGuoHuaRongDao.exe
echo Keep all files inside this directory when distributing the game.
exit /b 0
