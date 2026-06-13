@echo off
title MediRoute - One-Click Setup
color 0A

echo.
echo  ============================================
echo    MediRoute - One-Click Local Setup
echo  ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Download from: https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    pause
    exit /b 1
)
echo [OK] Python found.

:: Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo Download from: https://nodejs.org/
    pause
    exit /b 1
)
echo [OK] Node.js found.

:: Check PostgreSQL
psql --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] psql not found in PATH. 
    echo Make sure PostgreSQL is installed and added to PATH.
    echo Typical path: C:\Program Files\PostgreSQL\15\bin
    echo.
    echo If PostgreSQL is installed, add its bin folder to your PATH:
    echo   1. Search "Environment Variables" in Windows
    echo   2. Edit "Path" under System Variables
    echo   3. Add: C:\Program Files\PostgreSQL\15\bin
    echo   4. Restart this terminal and run setup.bat again
    echo.
    pause
    exit /b 1
)
echo [OK] PostgreSQL found.

echo.
echo ---- Step 1: Creating Python virtual environment ----
cd /d "%~dp0backend"
if not exist ".venv" (
    python -m venv .venv
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

echo.
echo ---- Step 2: Installing Python dependencies ----
call .venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
echo [OK] Python dependencies installed.

echo.
echo ---- Step 3: Creating PostgreSQL database ----
echo Enter your PostgreSQL password (the one you set during PostgreSQL installation):
set /p PG_PASS=Password: 

:: Try creating database (ignore error if it already exists)
set PGPASSWORD=%PG_PASS%
psql -U postgres -c "CREATE DATABASE mediroute;" 2>nul
if %errorlevel% equ 0 (
    echo [OK] Database 'mediroute' created.
) else (
    echo [OK] Database 'mediroute' already exists.
)

:: Update the .env file with the correct password
echo.
echo ---- Step 4: Configuring backend .env ----
(
echo DATABASE_URL=postgresql://postgres:%PG_PASS%@localhost:5432/mediroute
echo SECRET_KEY=mediroute_uttarakhand_2026_xK9mP2vL
echo ALGORITHM=HS256
echo ACCESS_TOKEN_EXPIRE_MINUTES=60
echo GEMINI_API_KEY=AIzaSyABnWRG8dHETiDyOQE9PIlFJQ36PMbJpsA
echo ORS_API_KEY=eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImZmNzEyNTRmOTMyMmEzYTY0OTgxMDI0YzVkNzM1OTNhYmFmNjMwZjgzYTg0ZmVmMTNjYmRkYTBlIiwiaCI6Im11cm11cjY0In0=
echo FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json
echo MODEL_SHA256=a46ae388b1fdc321edd355a3ae431d0eb5cd85f109227563d39c6edd8ee776b7
) > "%~dp0backend\.env"
echo [OK] Backend .env configured.

echo.
echo ---- Step 5: Running database migrations ----
alembic upgrade head
echo [OK] Database tables created.

echo.
echo ---- Step 6: Seeding database (hospitals + users) ----
python seed_db.py
python seed_hospitals_roorkee.py
python seed_users.py
echo [OK] Database seeded with hospitals and users.

echo.
echo ---- Step 7: Installing frontend dependencies ----
cd /d "%~dp0frontend"
call npm install --silent
echo [OK] Frontend dependencies installed.

echo.
echo  ============================================
echo    SETUP COMPLETE!
echo  ============================================
echo.
echo  To run the project, use: start.bat
echo  (or run the two commands manually)
echo.
echo  Login Credentials:
echo    Admin:     admin@test.com / test123
echo    Ambulance: amb1@test.com  / test123
echo    Hospital:  hospital@test.com / test123
echo    Hospital:  bhagwati@test.com / test123
echo.
pause
