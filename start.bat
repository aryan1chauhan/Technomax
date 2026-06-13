@echo off
title MediRoute - Running...
color 0B

echo.
echo  ============================================
echo    MediRoute - Starting Both Servers
echo  ============================================
echo.
echo  Backend  will run at: http://localhost:8000
echo  Frontend will run at: http://localhost:5173
echo.
echo  Login Credentials:
echo    Admin:     admin@test.com / test123
echo    Ambulance: amb1@test.com  / test123
echo    Hospital:  hospital@test.com / test123
echo    Hospital:  bhagwati@test.com / test123
echo.
echo  Close BOTH terminal windows to stop the servers.
echo  ============================================
echo.

:: Start backend in a new window
start "MediRoute Backend" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate.bat && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait 3 seconds for backend to initialize
timeout /t 3 /nobreak >nul

:: Start frontend in a new window
start "MediRoute Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

:: Wait 2 seconds then open browser
timeout /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo  Both servers started! Browser opening...
echo  You can close this window.
echo.
timeout /t 3 >nul
