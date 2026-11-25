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
echo [3/5] Running strict unit and Qt GUI tests...
"%P%" -X faulthandler tools/run_tests.py --require-qt
if errorlevel 1 (
    echo [ERROR] Tests failed. Build aborted.
    exit /b 1
)
echo [4/5] Building 64-bit Windows executable...
"%P%" -m PyInstaller --noconfirm --clean --onefile --windowed --name SanGuoHuaRongDao --icon "huarongdao\assets\icon.ico" --add-data "huarongdao\assets;huarongdao\assets" main.py
if errorlevel 1 exit /b 1
echo [5/5] Checking output...
if not exist "dist\SanGuoHuaRongDao.exe" (
    echo [ERROR] Expected executable is missing.
    exit /b 1
)
echo.
"%P%" tools/check_frozen.py "dist\SanGuoHuaRongDao.exe"
if errorlevel 1 exit /b 1
echo [SUCCESS] Output: dist\SanGuoHuaRongDao.exe
"%P%" tools/package_windows.py --exe "dist\SanGuoHuaRongDao.exe" --stage "build\release-package" --zip-dir dist
if errorlevel 1 exit /b 1
echo [SUCCESS] Single-file executable and three-file ZIP created.
echo [SIZE] Measured Windows output sizes:
"%P%" tools/report_build_size.py --dir "build\release-package" --exe "dist\SanGuoHuaRongDao.exe"
if errorlevel 1 exit /b 1
exit /b 0
