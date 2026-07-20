@echo off
cd /d "%~dp0"
python main.py
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Chorus failed to start.
    echo  Run install.bat first if you haven't already.
    echo.
    pause
)
