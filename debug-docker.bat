@echo off
echo ========================================
echo Docker Services Debug Script
echo ========================================
echo.

echo [1] Checking Docker status...
docker version
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running!
    pause
    exit /b 1
)

echo.
echo [2] Current running containers:
docker ps -a

echo.
echo [3] Checking Ollama service...
docker-compose logs --tail=20 ollama

echo.
echo [4] Testing Ollama connection...
curl -f http://localhost:11434/ 2>nul
if %errorlevel% eq 0 (
    echo Ollama is responding!
) else (
    echo Ollama is not responding yet...
)

echo.
echo [5] Checking if model is loaded...
docker exec university_ollama ollama list 2>nul

echo.
echo [6] Checking backend service...
docker-compose logs --tail=20 backend

echo.
echo [7] Testing backend health...
curl -f http://localhost:8000/health 2>nul
if %errorlevel% eq 0 (
    echo Backend is healthy!
) else (
    echo Backend is not responding yet...
)

echo.
echo [8] Checking frontend service...
docker-compose logs --tail=10 frontend

echo.
echo ========================================
echo Debug Options:
echo ========================================
echo 1. View all logs: docker-compose logs -f
echo 2. Restart all: docker-compose restart
echo 3. Pull model manually: docker exec university_ollama ollama pull qwen3:8b
echo 4. Stop all: docker-compose down
echo 5. Clean everything: docker-compose down -v
echo.
pause