# =============================================================================
# FILE: run_scadascout.bat (Windows)
# =============================================================================
@echo off
REM SCADA Scout Launcher for Windows
REM Double-click this file to start the application

echo ========================================
echo SCADA Scout - Starting...
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org
    pause
    exit /b 1
)

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo WARNING: Virtual environment not found
    echo Using system Python
)

REM Run application
echo Starting SCADA Scout...
python src\main.py

REM Keep window open if error occurred
if errorlevel 1 (
    echo.
    echo Application exited with error
    pause
)


# =============================================================================
# FILE: run_scadascout.sh (Linux/macOS)
# =============================================================================
#!/bin/bash
# SCADA Scout Launcher for Linux and macOS
# Make executable: chmod +x run_scadascout.sh
# Run: ./run_scadascout.sh

echo "========================================"
echo "SCADA Scout - Starting..."
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Display Python version
echo "Python version: $(python3 --version)"

# Check if virtual environment exists
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "WARNING: Virtual environment not found"
    echo "Using system Python"
    echo "Consider creating venv: python3 -m venv venv"
fi

# Check if dependencies are installed
python3 -c "import PySide6" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: Dependencies not installed"
    echo "Run: pip install -r requirements.txt"
    exit 1
fi

# Run application
echo "Starting SCADA Scout..."
python3 src/main.py

# Capture exit code
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "Application exited with error code: $EXIT_CODE"
    read -p "Press Enter to continue..."
fi


# =============================================================================
# FILE: install_scadascout.bat (Windows)
# =============================================================================
@echo off
REM SCADA Scout Installation Script for Windows

echo ========================================
echo SCADA Scout - Installation
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python 3.8+ from https://www.python.org
    pause
    exit /b 1
)

echo Python found: 
python --version
echo.

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip

echo Installing dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo To run SCADA Scout, double-click:
echo   run_scadascout.bat
echo.
pause


# =============================================================================
# FILE: install_scadascout.sh (Linux/macOS)
# =============================================================================
#!/bin/bash
# SCADA Scout Installation Script for Linux and macOS

echo "========================================"
echo "SCADA Scout - Installation"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found"
    echo ""
    echo "Installation instructions:"
    echo "  Ubuntu/Debian: sudo apt-get install python3 python3-pip python3-venv"
    echo "  Fedora/RHEL: sudo dnf install python3 python3-pip"
    echo "  macOS: brew install python3"
    exit 1
fi

echo "Python found: $(python3 --version)"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment"
    exit 1
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "To run SCADA Scout:"
echo "  ./run_scadascout.sh"
echo ""
echo "Or manually:"
echo "  source venv/bin/activate"
echo "  python src/main.py"
echo ""


# =============================================================================
# FILE: Makefile (Linux/macOS convenience)
# =============================================================================
# SCADA Scout - Makefile
# Run: make install, make run, make test, etc.

.PHONY: help install run test clean

help:
	@echo "SCADA Scout - Available Commands"
	@echo "================================="
	@echo ""
	@echo "  make install    - Install dependencies"
	@echo "  make run        - Run application"
	@echo "  make test       - Run tests"
	@echo "  make clean      - Remove virtual environment"
	@echo "  make lint       - Run code linting"
	@echo ""

install:
	@echo "Installing SCADA Scout..."
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -r requirements.txt
	@echo "Installation complete!"

run:
	@echo "Starting SCADA Scout..."
	. venv/bin/activate && python src/main.py

test:
	@echo "Running tests..."
	. venv/bin/activate && pytest

clean:
	@echo "Cleaning up..."
	rm -rf venv
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "Clean complete!"

lint:
	@echo "Running linter..."
	. venv/bin/activate && flake8 src/
	@echo "Lint complete!"
