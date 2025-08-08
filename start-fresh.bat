@echo off
echo ========================================
echo FRESH START - Building Everything New
echo ========================================
echo.

echo [1/6] Building backend image from scratch...
docker-compose build backend --no-cache
if %errorlevel% neq 0 (
    echo ERROR: Backend build failed!
    pause
    exit /b 1
)
timeout /t 2 >nul

echo.
echo [2/6] Building frontend image from scratch...
docker-compose build frontend --no-cache
if %errorlevel% neq 0 (
    echo ERROR: Frontend build failed!
    pause
    exit /b 1
)
timeout /t 2 >nul

echo.
echo [3/6] Starting Ollama service...
docker-compose up -d ollama
timeout /t 10 >nul

echo.
echo [4/6] Pulling Qwen model...
docker-compose run --rm model_init
timeout /t 5 >nul

echo.
echo [5/6] Starting backend service...
docker-compose up -d backend
timeout /t 10 >nul

echo.
echo [6/6] Starting frontend service...
docker-compose up -d frontend
timeout /t 5 >nul

echo.
echo ========================================
echo Checking service status...
echo ========================================
docker-compose ps

echo.
echo ========================================
echo Fresh setup complete!
echo ========================================
echo.
echo Services available at:
echo - Frontend: http://localhost:3000
echo - Backend API: http://localhost:8000/docs
echo - Ollama: http://localhost:11434
echo.
echo To view logs: docker-compose logs -f
echo.
pause