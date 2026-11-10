@echo off
echo ===================================================
echo   Starting EduEval AI Platform
echo ===================================================

echo Starting Backend Server (FastAPI on port 8000)...
start "EduEval AI - Backend" cmd /k "cd /d %~dp0Backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting Frontend Server (Vite on port 5173)...
start "EduEval AI - Frontend" cmd /k "cd /d %~dp0Frontend && npm run dev"

echo.
echo Both servers are launching!
echo Frontend: http://localhost:5173
echo Backend:  http://127.0.0.1:8000
echo Docs:     http://127.0.0.1:8000/docs
echo ===================================================
timeout /t 3 >nul
start http://localhost:5173

