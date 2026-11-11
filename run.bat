@echo off
title Flood Risk and Shelter WebGIS
setlocal

rem --- Flood Risk and Shelter WebGIS one-click launcher ---
rem 1) starts the portable PostgreSQL 16 + PostGIS (port 5433) if it is not running
rem 2) starts the FastAPI backend (uvicorn, port 8000)
rem 3) opens the browser once the app answers /api/health

set "PGBIN=C:\Users\Yaseen\postgres-pg16\bin"
set "PGDATA=C:\Users\Yaseen\postgres-pg16\pgdata"
set "PGPORT=5433"
set "APPURL=http://127.0.0.1:8000/"

if "%~1"==":openbrowser" goto openbrowser

cd /d "%~dp0backend"

rem --- 1) PostgreSQL + PostGIS ---
"%PGBIN%\pg_ctl.exe" -D "%PGDATA%" status >nul 2>&1
if errorlevel 1 (
    echo [1/3] Starting PostgreSQL on port %PGPORT% ...
    "%PGBIN%\pg_ctl.exe" -D "%PGDATA%" -l "C:\Users\Yaseen\postgres-pg16\pglog.txt" -o "-p %PGPORT%" -w start
    if errorlevel 1 (
        echo.
        echo PostgreSQL failed to start - see the messages above.
        pause
        exit /b 1
    )
) else (
    echo [1/3] PostgreSQL is already running on port %PGPORT%.
)

rem --- 2) Backend already running? Just open the browser and leave. ---
curl -sf -o nul http://127.0.0.1:8000/api/health
if not errorlevel 1 (
    echo [2/3] The app is already running on %APPURL%
    start "" "%APPURL%"
    timeout /t 3 >nul
    exit /b 0
)

rem --- 3) Start the backend; the browser opens itself once it is ready. ---
echo [2/3] Starting the web app - the browser will open automatically.
echo [3/3] Keep this window open while using the app. Close it to stop the server.
set "DATABASE_URL=postgresql://postgres:postgres@localhost:5433/webgis"
set "PSYCOPG_IMPL=python"
set "PATH=%PGBIN%;%PATH%"
start "" cmd /c call "%~f0" :openbrowser
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
echo.
echo The app stopped.
pause
exit /b 0

:openbrowser
rem Poll /api/health for up to 60 s, then open the default browser.
for /l %%i in (1,1,60) do (
    curl -sf -o nul http://127.0.0.1:8000/api/health
    if not errorlevel 1 (
        start "" "http://127.0.0.1:8000/"
        exit /b 0
    )
    timeout /t 1 /nobreak >nul
)
exit /b 0
