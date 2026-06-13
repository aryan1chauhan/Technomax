@echo off
title MediRoute - Docker Start
color 0E

echo.
echo  ============================================
echo    MediRoute - Docker One-Click Start
echo  ============================================
echo.

:: Check Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not installed.
    echo Download Docker Desktop from: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
echo [OK] Docker found.

:: Check Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Desktop is not running. Please start it first.
    echo Look for the Docker whale icon in your taskbar.
    pause
    exit /b 1
)
echo [OK] Docker is running.

echo.
echo Starting all services (this may take 2-3 minutes on first run)...
echo.

:: Build and start
docker-compose up --build -d

echo.
echo Waiting for database to be ready...
timeout /t 10 /nobreak >nul

echo.
echo Seeding database with hospitals and users...
docker exec mediroute_backend python seed_db.py
docker exec mediroute_backend python seed_hospitals_roorkee.py
docker exec mediroute_backend python seed_users.py

echo.
echo  ============================================
echo    ALL DONE! Opening browser...
echo  ============================================
echo.
echo  Frontend: http://localhost:3000
echo  Backend:  http://localhost:8000
echo.
echo  Login Credentials:
echo    Admin:     admin@test.com / test123
echo    Ambulance: amb1@test.com  / test123
echo    Hospital:  hospital@test.com / test123
echo    Hospital:  bhagwati@test.com / test123
echo.
echo  To stop:  docker-compose down
echo  To restart: just run this file again
echo  ============================================

start http://localhost:3000

pause
