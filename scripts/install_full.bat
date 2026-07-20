@echo off
setlocal EnableDelayedExpansion
title Chorus - Full Installer

echo.
echo  =========================================
echo   Chorus - Full Installer
echo   Automated Voice Call Testing Tool
echo  =========================================
echo.

:: ── 1. Check Python ──────────────────────────────────────────
echo [1/4] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [!] Python not found — installing now...
    echo.
    
    :: Try winget first (Windows 10/11 built-in)
    winget --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo  Using winget to install Python...
        winget install --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements --scope machine --silent
        if %errorlevel% neq 0 (
            echo  [ERROR] winget installation failed.
            echo  Please install Python manually from:
            echo  https://www.python.org/downloads/
            echo.
            echo  IMPORTANT: Check "Add Python to PATH" during install.
            echo.
            pause
            exit /b 1
        )
    ) else (
        :: winget not available — manual instructions
        echo  [!] winget not available.
        echo  Please install Python manually from:
        echo  https://www.python.org/downloads/
        echo.
        echo  IMPORTANT: During installation, check:
        echo  "Add Python to PATH"
        echo.
        pause
        exit /b 1
    )
    
    echo  [OK] Python installed
) else (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do echo  [OK] Python %%v
)

:: ── 2. Check pip ─────────────────────────────────────────────
echo.
echo [2/4] Checking pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] pip not found. Please reinstall Python.
    pause
    exit /b 1
)
echo  [OK] pip found

:: ── 3. Install Python packages ───────────────────────────────
echo.
echo [3/4] Installing Python packages...
echo  (this may take a few minutes)
echo.
python -m pip install --upgrade pip --quiet
python -m pip install matplotlib folium --quiet
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install packages.
    echo  Try running manually: pip install matplotlib folium
    pause
    exit /b 1
)
echo  [OK] All packages installed

:: ── 4. Check ADB (optional) ─────────────────────────────────
echo.
echo [4/4] Checking ADB...
adb version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [!] ADB not found — device control will not work.
    echo.
    echo  To install ADB:
    echo  1. Download Platform Tools from:
    echo     https://developer.android.com/tools/releases/platform-tools
    echo  2. Extract the ZIP (e.g. to C:\platform-tools)
    echo  3. Add that folder to your system PATH, or
    echo     place adb.exe in the same folder as Chorus.
    echo.
) else (
    for /f "tokens=*" %%v in ('adb version 2^>^&1 ^| findstr /i "Android Debug Bridge"') do echo  [OK] %%v
)

:: ── Summary ──────────────────────────────────────────────────
echo.
echo  =========================================
echo   Installation complete!
echo  =========================================
echo.
echo  To launch Chorus:
echo    python main.py
echo.
echo  Or double-click: run_chorus.bat
echo.
pause
