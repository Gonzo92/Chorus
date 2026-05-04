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
echo   Chorus v2.2 — Dependency Installer
echo ========================================
echo.

REM 1. Check Python
echo [1/4] Checking Python...
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

REM 2. Uninstall old versions
echo [2/4] Removing old versions...
python -m pip uninstall matplotlib folium -y 2>nul
echo   Done.
echo.

REM 3. Install with fallback mirrors
echo [3/4] Installing matplotlib and folium...
echo.

echo   Attempt 1: standard PyPI...
python -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org 2>nul
if errorlevel 0 (
    echo   Success!
) else (
    echo   Attempt 2: mirror Tsinghua...
    python -m pip install matplotlib folium ^
        --index-url https://pypi.tuna.tsinghua.edu.cn/simple/ ^
        --trusted-host pypi.tuna.tsinghua.edu.cn 2>nul
    if errorlevel 0 (
        echo   Success!
    ) else (
        echo   Attempt 3: mirror Aliyun...
        python -m pip install matplotlib folium ^
            --index-url https://mirrors.aliyun.com/pypi/simple/ ^
            --trusted-host mirrors.aliyun.com 2>nul
        if errorlevel 0 (
            echo   Success!
        ) else (
            echo   Attempt 4: no mirrors (check internet)...
            python -m pip install matplotlib folium
            if errorlevel 1 (
                echo.
                echo ERROR: Installation failed. Check your internet connection.
                echo.
                pause
                popd
                exit /b 1
            )
            echo   Success!
        )
    )
)

REM 4. Verify
echo.
echo [4/4] Verifying installation...
python -c "import matplotlib; import folium; print('OK - matplotlib ' + matplotlib.__version__ + ' | folium ' + folium.__version__)" 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: Verification failed. One or more packages could not be imported.
    echo.
    pause
    popd
    exit /b 1
)
echo.
echo ========================================
echo   Installation complete!
echo ========================================
echo.
echo You can now run Chorus with:
echo   run.bat
echo.
popd
pause
