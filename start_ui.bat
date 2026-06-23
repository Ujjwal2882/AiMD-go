@echo off
echo ===================================================
echo   Starting AiMD-go Web UI on Port 3000...
echo ===================================================
cd static
python -m http.server 3000
