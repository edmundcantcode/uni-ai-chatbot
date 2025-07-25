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

REM [1/6] Check if Docker is running
echo [1/6] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker not found! Please install Docker Desktop first.
    echo    Download from: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

REM Check if Docker daemon is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not running! Please start Docker Desktop.
    pause
    exit /b 1
)
echo ✅ Docker detected and running

REM [2/6] Clean up existing containers
echo [2/6] Cleaning up existing containers...
docker-compose down --remove-orphans >nul 2>&1
echo ✅ Cleanup completed

REM [3/6] Build containers
echo [3/6] Building containers...
docker-compose build --no-cache
if errorlevel 1 (
    echo ❌ Failed to build containers
    pause
    exit /b 1
)
echo ✅ Containers built successfully

REM [4/6] Start Ollama service first
echo [4/6] Starting Ollama service...
docker-compose up -d ollama
if errorlevel 1 (
    echo ❌ Failed to start Ollama service
    pause
    exit /b 1
)
echo ✅ Ollama service started

REM [5/6] Pull Llama model inside container
echo [5/6] Pulling Llama 3.2 model (this may take several minutes on first run)...
echo     Please wait while the model downloads...
docker-compose up model_init
if errorlevel 1 (
    echo ⚠️  Model pull failed, but continuing anyway
    echo     You can pull it manually later with: docker-compose exec ollama ollama pull llama3.2:latest
) else (
    echo ✅ Llama model ready
)

REM [6/6] Start all remaining services
echo [6/6] Starting all services...
docker-compose up -d
if errorlevel 1 (
    echo ❌ Failed to start services
    pause
    exit /b 1
)

REM Wait for services to initialize
echo.
echo Waiting for services to initialize...
echo This may take 1-2 minutes for all services to be ready...
timeout /t 30 /nobreak >nul

REM Check if services are responding
echo.
echo Checking service health...
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Backend may still be starting up...
    timeout /t 30 /nobreak >nul
)

REM Open web browser
echo Opening web browser...
timeout /t 5 /nobreak >nul
start http://localhost:3000

echo.
echo ======================================================
echo                 System Status
echo ======================================================
echo ✅ Frontend: http://localhost:3000
echo ✅ Backend:  http://localhost:8000
echo ✅ Health:   http://localhost:8000/health
echo ✅ Ollama:   http://localhost:11434
echo ======================================================
echo          System Started Successfully!
echo ======================================================
echo.
echo Login Credentials:
echo   Admin:   username=admin,    password=admin
echo   Student: username=12345,    password=12345
echo.
echo Useful Commands:
echo   View logs:    docker-compose logs -f
echo   Stop system:  docker-compose down
echo   Restart:      docker-compose restart [service-name]
echo.
pause