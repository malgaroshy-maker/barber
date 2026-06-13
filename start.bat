@echo off
setlocal enabledelayedexpansion
title AI Barber Bot

echo ================================
echo  AI Barber WhatsApp Bot
echo ================================
echo.

:: Check if .venv exists
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Run: python -m venv .venv
    pause
    exit /b 1
)

:: -------------------------------------------------------------------------
:: Decide which WhatsApp mode to use based on .env configuration.
::   - OpenWA mode if OPENWA_API_KEY and OPENWA_SESSION_ID are filled in.
::   - Otherwise, fall back to Meta Cloud API + Cloudflare Tunnel mode.
:: -------------------------------------------------------------------------
set "USE_OPENWA=0"
if exist ".env" (
    for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
        if /i "%%a"=="OPENWA_API_KEY"   if not "%%b"=="" set "USE_OPENWA=1"
        if /i "%%a"=="OPENWA_SESSION_ID" if not "%%b"=="" set "USE_OPENWA=1"
    )
)

if "!USE_OPENWA!"=="1" (
    echo [INFO] OpenWA mode detected.
    echo.
    if not exist "openwa\dist\main.js" (
        echo [ERROR] openwa\dist\main.js is missing.
        echo Run setup-openwa.bat first.
        pause
        exit /b 1
    )
    echo [1/2] Starting OpenWA API + Dashboard...
    start "OpenWA Gateway" /min cmd /c "cd openwa && npm start"
    timeout /t 6 /nobreak >nul
    echo [2/2] Starting FastAPI server on port 8000...
    start "FastAPI Server" /min .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    echo.
    echo ================================
    echo  Both services launched!
    echo.
    echo  OpenWA Dashboard: http://localhost:2886
    echo  OpenWA API:       http://localhost:2785/api
    echo  FastAPI:          http://localhost:8000
    echo.
    echo  No tunneling, no random URLs.  Just scan a QR code once.
    echo ================================
    echo.
    pause
    exit /b 0
)

:: -------------------------------------------------------------------------
:: Meta Cloud API + Cloudflare Tunnel mode (legacy / fallback).
:: -------------------------------------------------------------------------
echo [INFO] Meta Cloud API mode detected (OpenWA keys not set).
echo.

echo [1/2] Starting FastAPI server on port 8000...
start "FastAPI Server" /min .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
timeout /t 3 /nobreak >nul

echo [2/2] Starting Cloudflare tunnel...
where cloudflared >nul 2>nul
if %errorlevel% equ 0 (
    start "Cloudflare Tunnel" cloudflared tunnel --url http://localhost:8000
) else if exist "%USERPROFILE%\cloudflared.exe" (
    start "Cloudflare Tunnel" "%USERPROFILE%\cloudflared.exe" tunnel --url http://localhost:8000
) else (
    echo.
    echo [WARNING] cloudflared not found. Install it:
    echo   winget install Cloudflare.cloudflared
    echo.
    echo Or start manually in another terminal:
    echo   cloudflared tunnel --url http://localhost:8000
    echo.
    pause
    exit /b 1
)

echo.
echo ================================
echo  Both servers launched!
echo.
echo  FastAPI:    http://localhost:8000
echo.
echo  IMPORTANT:
echo  1. Check the Cloudflare Tunnel window for your URL
echo  2. Copy it to Meta WhatsApp -^> Configuration -^> Callback URL
echo     e.g. https://xxxx.trycloudflare.com/webhook
echo  3. Click "Verify and save"
echo  4. Send "hi" to your test number on WhatsApp
echo.
echo  TIP: switch to OpenWA mode (start-openwa.bat) to avoid the
echo  random URL and certificate warnings.
echo ================================
echo.

pause
