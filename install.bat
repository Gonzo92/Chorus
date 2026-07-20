@echo off
setlocal EnableDelayedExpansion
title Chorus v2.6 - Requirements Installer

echo.
echo  =========================================
echo   Chorus v2.6 - Requirements Installer
echo   Automated Voice Call Testing Tool
echo  =========================================
echo.

:: ── 1. Check Python ──────────────────────────────────────────
echo [1/6] Checking Python...
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
echo [2/6] Checking pip...
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

:: ── 3. Upgrade pip ───────────────────────────────────────────
echo.
echo [3/6] Upgrading pip...
python -m pip install --upgrade pip --quiet 2>nul
if %errorlevel% equ 0 (
    echo  [OK] pip upgraded
) else (
    echo  [WARN] pip upgrade skipped
)

:: ── 4. Install Python packages ───────────────────────────────
echo.
echo [4/6] Installing Python packages...
echo  (this may take a moment)
echo.

:: Install all packages from requirements.txt
python -m pip install -r requirements.txt --quiet --upgrade 2>nul
if %errorlevel% neq 0 (
    echo  [WARN] Some packages failed to install, trying individually...
    echo.
    
    :: Install matplotlib
    echo  Installing matplotlib...
    python -m pip install "matplotlib>=3.7.0" --quiet 2>nul
    if %errorlevel% equ 0 (
        echo  [OK] matplotlib
    ) else (
        echo  [ERROR] matplotlib failed
    )
    
    :: Install folium
    echo  Installing folium...
    python -m pip install "folium>=0.14.0" --quiet 2>nul
    if %errorlevel% equ 0 (
        echo  [OK] folium
    ) else (
        echo  [ERROR] folium failed
    )
    
    :: Install pandas
    echo  Installing pandas...
    python -m pip install "pandas>=2.0.0" --quiet 2>nul
    if %errorlevel% equ 0 (
        echo  [OK] pandas
    ) else (
        echo  [ERROR] pandas failed
    )
    
    :: Install openpyxl
    echo  Installing openpyxl...
    python -m pip install "openpyxl>=3.1.0" --quiet 2>nul
    if %errorlevel% equ 0 (
        echo  [OK] openpyxl
    ) else (
        echo  [ERROR] openpyxl failed
    )
    
    :: Install pyinstaller
    echo  Installing pyinstaller...
    python -m pip install "pyinstaller>=6.0.0" --quiet 2>nul
    if %errorlevel% equ 0 (
        echo  [OK] pyinstaller
    ) else (
        echo  [ERROR] pyinstaller failed
    )
)

echo.
echo  [OK] All Python packages installed

:: ── 5. Check installed packages ──────────────────────────────
echo.
echo [5/6] Verifying installed packages...
echo.

python -c "import matplotlib; print('  matplotlib', matplotlib.__version__)" 2>nul || echo  [MISSING] matplotlib
python -c "import folium; print('  folium', folium.__version__)" 2>nul || echo  [MISSING] folium
python -c "import pandas; print('  pandas', pandas.__version__)" 2>nul || echo  [MISSING] pandas
python -c "import openpyxl; print('  openpyxl', openpyxl.__version__)" 2>nul || echo  [MISSING] openpyxl
python -c "import PyInstaller; print('  pyinstaller', PyInstaller.__version__)" 2>nul || echo  [MISSING] pyinstaller

:: ── 6. Check ADB and scrcpy ──────────────────────────────────
echo.
echo [6/6] Checking ADB and scrcpy...
echo.

:: Check ADB
adb version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('adb version 2^>^&1 ^| findstr /i "Android Debug Bridge"') do echo  [OK] %%v
) else (
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
    set ADB_OK=0
)

:: Check scrcpy
scrcpy --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('scrcpy --version 2^>^&1 ^| findstr /i "scrcpy"') do echo  [OK] %%v
) else (
    echo  [INFO] scrcpy not found - screen mirroring will be unavailable.
    echo  To install: https://github.com/Genymobile/scrcpy
    echo  Or place scrcpy.exe in C:\scrcpy\
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
