@echo off
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)
python src\main.py
if errorlevel 1 pause
