@echo off
REM Setup script for Insurance PD Report Analyzer
REM Run this after cloning the repository

echo ================================================================================
echo Insurance PD Report Analyzer - Setup Script
echo ================================================================================
echo.

REM Check Python installation
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from https://www.python.org/
    pause
    exit /b 1
)
python --version
echo.

REM Install dependencies
echo [2/4] Installing dependencies...
echo This may take 5-10 minutes on first run...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

REM Create .env file if it doesn't exist
echo [3/4] Setting up configuration...
if not exist .env (
    echo Creating .env file from template...
    copy .env.example .env
    echo.
    echo IMPORTANT: Please edit .env file and add your ANTHROPIC_API_KEY
    echo Get your API key from: https://console.anthropic.com/
    echo.
) else (
    echo .env file already exists
)
echo.

REM Verify setup
echo [4/4] Verifying setup...
python scripts/verify_setup.py
echo.

echo ================================================================================
echo Setup Complete!
echo ================================================================================
echo.
echo Next steps:
echo   1. Edit .env file and add your ANTHROPIC_API_KEY
echo   2. Add PDF files to data/pdfs/ folder
echo   3. Run: python scripts/ingest_all.py
echo   4. Test: python scripts/test_query.py --q "your question"
echo   5. Launch UI: streamlit run app/streamlit_app.py
echo.
echo For detailed instructions, see SETUP_GUIDE.md
echo.
pause
