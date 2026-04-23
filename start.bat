@echo off
echo ============================================
echo   PNJ AI Trend Radar V2 - Startup Script
echo ============================================
echo.

REM Kich hoat virtual environment
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [LOI] Khong tim thay .venv
    echo Vui long chay: python -m venv .venv
    echo Roi: .venv\Scripts\activate.bat
    echo Roi: pip install -r requirements.txt
    pause
    exit /b 1
)

echo [OK] Virtual environment da kich hoat
echo [OK] Dang khoi dong Streamlit...
echo.
echo App se mo tai: http://localhost:8501
echo Nhan Ctrl+C de dung app
echo.

streamlit run app.py
pause
