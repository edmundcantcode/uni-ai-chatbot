@echo off
echo ========================================
echo COMPLETE SYSTEM RESET
echo This will delete EVERYTHING and start fresh
echo ========================================
echo.
pause

echo [1/8] Stopping all containers...
docker-compose down -v
docker stop $(docker ps -aq) 2>nul
timeout /t 2 >nul

echo.
echo [2/8] Removing all containers...
docker rm -f $(docker ps -aq) 2>nul
docker-compose rm -f 2>nul
timeout /t 2 >nul

echo.
echo [3/8] Removing all images...
docker rmi -f uni-ai-chatbotv3-backend 2>nul
docker rmi -f uni-ai-chatbotv3-frontend 2>nul
docker rmi -f $(docker images -q) 2>nul
timeout /t 2 >nul

echo.
echo [4/8] Removing all volumes...
docker volume rm university_ollama_data 2>nul
docker volume rm $(docker volume ls -q) 2>nul
timeout /t 2 >nul

echo.
echo [5/8] Cleaning Docker system...
docker system prune -a --volumes -f
timeout /t 2 >nul

echo.
echo [6/8] Cleaning builder cache...
docker builder prune -a -f
timeout /t 2 >nul

echo.
echo [7/8] Removing Python caches...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul
timeout /t 2 >nul

echo.
echo [8/8] Removing temporary files...
del /s /q backend\llm\llama_integration.py 2>nul
rd /s /q .pytest_cache 2>nul
rd /s /q .coverage 2>nul
timeout /t 2 >nul

echo.
echo ========================================
echo RESET COMPLETE!
echo ========================================
echo.
echo Docker status:
docker ps -a
docker images
docker volume ls
echo.
echo ========================================
echo Everything has been cleaned!
echo Run start-fresh.bat to begin with a clean setup
echo ========================================
pause