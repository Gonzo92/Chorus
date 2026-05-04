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
echo   Chorus v2.2 — Build Standalone .exe
echo ========================================
echo.
echo This will create a standalone Chorus.exe using PyInstaller.
echo The output will be in the current directory.
echo.
echo Requirements:
echo   - Python 3.9+
echo   - pip install pyinstaller pillow
echo.
pause

REM 0. Generate icon (if not exists)
echo [0/6] Generating satellite dish icon...
if not exist "Chorus.ico" (
    python tools\generate_icon.py
) else (
    echo   Chorus.ico already exists — skipping.
)
echo.

REM 1. Check Python
echo [1/6] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    pause
    popd
    exit /b 1
)
for /f "tokens=*" %%p in ('where python') do set PYTHON_PATH=%%p
echo   Found: !PYTHON_PATH!
echo.

REM 2. Check/install PyInstaller
echo [2/6] Checking PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo   PyInstaller not found. Installing...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller.
        pause
        popd
        exit /b 1
    )
) else (
    python -c "import PyInstaller; print('  PyInstaller ' + PyInstaller.__version__)"
)
echo.

REM 3. Check/install Pillow (for icon generation)
echo [3/6] Checking Pillow...
python -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo   Pillow not found. Installing...
    python -m pip install pillow
    if errorlevel 1 (
        echo WARNING: Failed to install Pillow. Icon may not generate.
    )
) else (
    echo   Pillow OK
)
echo.

REM 4. Check dependencies
echo [4/6] Checking Chorus dependencies...
python check_deps.py
if errorlevel 1 (
    echo.
    echo Dependency check failed. Please fix issues before building.
    pause
    popd
    exit /b 1
)
echo.

REM 5. Clean old build
echo [5/6] Cleaning old build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "Chorus.spec" del /q "Chorus.spec"
echo   Cleaned.
echo.

REM 6. Build with PyInstaller (output to root, with icon)
echo [6/6] Building Chorus.exe...
echo.
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "Chorus_v2.2" ^
    --icon "Chorus.ico" ^
    --distpath "." ^
    --add-data "config.py;." ^
    --add-data "core;core" ^
    --add-data "gui;gui" ^
    --add-data "utils;utils" ^
    --hidden-import matplotlib.pyplot ^
    --hidden-import folium ^
    --hidden-import matplotlib.backends.backend_tkagg ^
    --hidden-import winsound ^
    main.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed. Check the output above.
    pause
    popd
    exit /b 1
)

echo.
echo ========================================
echo   BUILD COMPLETE
echo ========================================
echo.
echo   Output: Chorus_v2.2.exe (in this directory)
echo.
echo You can distribute this single file to other Windows machines.
echo No Python installation required on target machines.
echo.
popd
pause
