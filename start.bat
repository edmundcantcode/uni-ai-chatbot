@echo off
title University AI System Startup
color 0A
echo.
echo ======================================================
echo              University AI Assistant
echo                  Starting System...
echo ======================================================
echo.

REM Navigate to script directory first
cd /d "%~dp0"

REM [1/4] Check if Docker is running
echo [1/4] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker not found! Please install Docker Desktop first.
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not running! Please start Docker Desktop.
    pause
    exit /b 1
)
echo ✅ Docker detected and running

REM [2/4] Clean up existing containers
echo [2/4] Cleaning up existing containers...
docker-compose down --remove-orphans >nul 2>&1
echo ✅ Cleanup completed

REM [3/4] Start all services
echo [3/4] Starting all services...
echo     This may take a few minutes on first run...
docker-compose up -d --build
if errorlevel 1 (
    echo ❌ Failed to start services
    echo.
    echo Troubleshooting:
    echo 1. Check Docker Desktop is running
    echo 2. Try: docker-compose down --volumes
    echo 3. Then restart this script
    pause
    exit /b 1
)
echo ✅ All services started

REM [4/4] Wait and open browser
echo [4/4] Waiting for services to initialize...
echo     Please wait while services start up...

REM Wait for backend to be ready
set /a count=0
:check_backend
timeout /t 3 /nobreak >nul
curl -s http://localhost:8000 >nul 2>&1
if errorlevel 1 (
    set /a count+=1
    if %count% lss 20 (
        echo     Starting services... (%count%/20)
        goto check_backend
    ) else (
        echo ⚠️  Services taking longer than expected, opening browser anyway...
    )
) else (
    echo ✅ Backend is ready
)

REM Open web browser
echo Opening web browser...
start http://localhost:3000

echo.
echo ======================================================
echo                 System Status
echo ======================================================
echo ✅ Frontend: http://localhost:3000
echo ✅ Backend:  http://localhost:8000
echo ✅ Ollama:   http://localhost:11434
echo ======================================================
echo          System Started Successfully!
echo ======================================================
echo.
echo 📝 NOTE: AI features require Llama model download
echo    To download model: docker-compose exec ollama ollama pull llama3.2:latest
echo    Check model status: docker-compose exec ollama ollama list
echo.
echo Login Credentials:
echo   Admin:   username=admin,    password=admin
echo   Student: username=12345,    password=12345
echo.
echo Useful Commands:
echo   View logs:    docker-compose logs -f
echo   Stop system:  docker-compose down
echo   Restart:      docker-compose restart
echo.
pause