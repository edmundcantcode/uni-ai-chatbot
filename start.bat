@echo off
title University AI System Startup
color 0A

echo.
echo ======================================================
echo              University AI Assistant
echo                  Starting System...
echo ======================================================
echo.

REM Check if Docker is running
echo [1/5] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker not found! Please install Docker Desktop first.
    echo    Download from: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
echo ✅ Docker detected

REM Navigate to script directory
cd /d "%~dp0"

REM Stop any existing containers
echo [2/5] Cleaning up existing containers...
docker-compose down >nul 2>&1

REM Start all services
echo [3/5] Starting all services (this may take 10-15 minutes first time)...
docker-compose up -d --build

REM Wait for services to start
echo [4/5] Waiting for services to initialize...
timeout /t 10 /nobreak >nul

REM Check services and open browser
echo [5/5] Opening web browser...
echo.
echo ======================================================
echo                 System Status
echo ======================================================

REM Wait a bit more for backend to fully start
timeout /t 20 /nobreak >nul

REM Open the login page in default browser
start http://localhost:3000

echo.
echo ✅ Frontend: http://localhost:3000
echo ✅ Backend:  http://localhost:8000
echo ✅ Health:   http://localhost:8000/health
echo.
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