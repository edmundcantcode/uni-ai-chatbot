@echo off
title University AI System Startup
color 0A

echo.
echo ======================================================
echo              University AI Assistant
echo                  Starting System...
echo ======================================================
echo.

REM [1/6] Check if Docker is running
echo [1/6] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker not found! Please install Docker Desktop first.
    echo    Download from: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
echo ✅ Docker detected

REM [2/6] Pull the Llama 3.2 model
echo [2/6] Pulling Llama 3.2 model…
ollama pull llama-3.2 >nul 2>&1
if errorlevel 1 (
    echo ❌ Failed to pull Llama model. Make sure Ollama CLI is installed and on your PATH.
    pause
    exit /b 1
)
echo ✅ Model ready

REM Navigate to script directory
cd /d "%~dp0"

REM [3/6] Stop any existing containers
echo [3/6] Cleaning up existing containers...
docker-compose down >nul 2>&1

REM [4/6] Start all services
echo [4/6] Starting all services (this may take 10-15 minutes first time)…
docker-compose up -d --build

REM [5/6] Wait for services to initialize
echo [5/6] Waiting for services to initialize…
timeout /t 10 /nobreak >nul

REM [6/6] Opening web browser…
timeout /t 20 /nobreak >nul
start http://localhost:3000

echo.
echo ======================================================
echo                 System Status
echo ======================================================
echo ✅ Frontend: http://localhost:3000
echo ✅ Backend:  http://localhost:8000
echo ✅ Health:   http://localhost:8000/health
echo ======================================================
echo          System Started Successfully!
echo ======================================================
echo.
echo Login Credentials:
echo   Admin:   username=admin,    password=admin
echo   Student: username=12345,    password=12345
echo.
echo To stop the system, run: stop.bat
echo.
pause
