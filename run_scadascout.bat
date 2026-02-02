@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

where python >nul 2>&1
if %errorlevel%==0 (
    python src\main.py
) else (
    py -3 src\main.py
)

if errorlevel 1 pause
endlocal
