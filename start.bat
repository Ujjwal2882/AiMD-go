@echo off
echo ===================================================
echo   Starting AiMD-go...
echo ===================================================

echo Checking dependencies...
python -m pip install -r requirements.txt

echo.
echo Starting server...
python main.py

pause
