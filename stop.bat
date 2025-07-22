@echo off
title University AI System Shutdown
color 0C

echo.
echo ======================================================
echo              University AI Assistant
echo                 Stopping System...
echo ======================================================
echo.

REM Navigate to script directory
cd /d "%~dp0"

REM Stop all containers
echo Stopping all Docker containers...
docker-compose down

echo.
echo ✅ All services stopped successfully!
echo.
echo To restart the system, run: start.bat
echo.
pause