@echo off
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

echo [1/2] Starting FastAPI server on port 8000...
start "FastAPI Server" /min .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

timeout /t 3 /nobreak >nul

echo [2/2] Starting Cloudflare tunnel...

:: Try cloudflared from various locations
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
echo  Close this window when done.
echo ================================
echo.

pause
