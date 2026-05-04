@echo off
setlocal

REM ── change to script directory (handles spaces in path) ──
pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Cannot change to script directory.
    echo Path: %~dp0
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Chorus v2.2 — Launcher
echo ========================================
echo.

REM 1. Find Python
echo [1/3] Finding Python...
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo.
    echo Please install Python 3.9+:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    popd
    exit /b 1
)

for /f "tokens=*" %%p in ('where python') do set PYTHON_PATH=%%p
echo   Found: !PYTHON_PATH!
echo.

REM 2. Run dependency check
echo [2/3] Checking dependencies...
echo.
python check_deps.py
if errorlevel 1 (
    echo.
    echo Dependency check failed. Please fix the issues above.
    echo.
    echo Quick fix — install missing packages:
    echo   pip install matplotlib folium
    echo.
    pause
    popd
    exit /b 1
)
echo.

REM 3. Launch Chorus
echo [3/3] Starting Chorus...
echo.
python main.py %*
set EXIT_CODE=!errorlevel!

echo.
echo Chorus closed successfully.
echo.
popd
pause
exit /b !EXIT_CODE!
