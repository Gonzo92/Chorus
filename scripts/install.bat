@echo off
setlocal EnableDelayedExpansion
title Chorus - Installer

echo.
echo  =========================================
echo   Chorus - Installer
echo   Automated Voice Call Testing Tool
echo  =========================================
echo.

:: ── 1. Check Python ──────────────────────────────────────────
echo [1/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Python not found in PATH.
    echo.
    echo  Please install Python 3.10 or newer from:
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: During installation, check:
    echo  "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:: Check Python version is 3.10+
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)
if !PYMAJ! LSS 3 (
    echo  [ERROR] Python 3.10+ required. Found: !PYVER!
    pause
    exit /b 1
)
if !PYMAJ! EQU 3 if !PYMIN! LSS 10 (
    echo  [ERROR] Python 3.10+ required. Found: !PYVER!
    pause
    exit /b 1
)
echo  [OK] Python !PYVER!

:: ── 2. Check pip ─────────────────────────────────────────────
echo.
echo [2/5] Checking pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] pip not found. Trying to install...
    python -m ensurepip --upgrade
    if %errorlevel% neq 0 (
        echo  [ERROR] Could not install pip. Please reinstall Python.
        pause
        exit /b 1
    )
)
echo  [OK] pip found

:: ── 3. Install Python packages ───────────────────────────────
echo.
echo [3/5] Installing Python packages...
echo  (matplotlib, this may take a moment)
echo.
python -m pip install matplotlib --quiet --upgrade
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install matplotlib.
    echo  Try running manually: pip install matplotlib
    pause
    exit /b 1
)
echo  [OK] matplotlib installed

:: ── 4. Check ADB ─────────────────────────────────────────────
echo.
echo [4/5] Checking ADB...
adb version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [WARNING] ADB not found in PATH.
    echo.
    echo  To install ADB:
    echo  1. Download Platform Tools from:
    echo     https://developer.android.com/tools/releases/platform-tools
    echo  2. Extract the ZIP (e.g. to C:\platform-tools)
    echo  3. Add that folder to your system PATH, or
    echo     place adb.exe in the same folder as Chorus.
    echo.
    echo  Chorus will still launch but device control won't work
    echo  until ADB is available.
    echo.
    set ADB_OK=0
) else (
    for /f "tokens=*" %%v in ('adb version 2^>^&1 ^| findstr /i "Android Debug Bridge"') do echo  [OK] %%v
    set ADB_OK=1
)

:: ── 5. Check scrcpy (optional) ───────────────────────────────
echo.
echo [5/5] Checking scrcpy (optional)...
scrcpy --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [INFO] scrcpy not found - screen mirroring will be unavailable.
    echo  To install: https://github.com/Genymobile/scrcpy
    echo  Or place scrcpy.exe in C:\scrcpy\
) else (
    for /f "tokens=*" %%v in ('scrcpy --version 2^>^&1 ^| findstr /i "scrcpy"') do echo  [OK] %%v
)

:: ── Summary ──────────────────────────────────────────────────
echo.
echo  =========================================
echo   Installation complete!
echo  =========================================
echo.
if "!ADB_OK!"=="0" (
    echo  [!] ADB missing - see instructions above.
    echo.
)
echo  To launch Chorus, run:
echo    python main.py
echo.
echo  Or double-click: run_chorus.bat
echo.
pause
endlocal
