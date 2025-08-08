@echo off
echo ====================================
echo Starting University Chatbot
echo ====================================
echo.

REM Set GPU environment variables
set CUDA_VISIBLE_DEVICES=0
set NVIDIA_VISIBLE_DEVICES=all

REM Step 1: Clean up
echo Cleaning up old containers...
docker-compose down
timeout /t 2 >nul

REM Step 2: ALWAYS rebuild to get latest code
echo Building with latest code...
docker-compose build backend --no-cache
docker-compose build frontend --no-cache

REM Step 3: Start everything
echo Starting all services with GPU support...
docker-compose up -d

REM Step 4: Wait a bit
echo Waiting for services to start...
timeout /t 15 >nul

REM Step 5: Show status
echo.
echo Current status:
docker-compose ps

echo.
echo ====================================
echo Services available at:
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo GPU:      ENABLED (if Docker supports it)
echo ====================================
echo.
echo To see logs: docker-compose logs -f
echo To stop: run stop.bat
echo To check GPU: nvidia-smi
echo.
pause