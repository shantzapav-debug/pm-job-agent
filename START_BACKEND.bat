@echo off
echo Starting Pavan Job Agent Backend...
cd /d "%~dp0backend"
py -3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
