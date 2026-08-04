@echo off
title AI Barber Bot (OpenWA mode)

echo ================================
echo  AI Barber Bot - OpenWA Mode
echo ================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found.
    echo Run: python -m venv .venv  ^&^&  .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "openwa\dist\main.js" (
    echo [ERROR] OpenWA API is not built. Run setup-openwa.bat first.
    pause
    exit /b 1
)

if not exist "openwa\dashboard\node_modules" (
    echo [ERROR] OpenWA Dashboard dependencies are missing. Run setup-openwa.bat first.
    pause
    exit /b 1
)

if not exist "openwa\.env" (
    echo [ERROR] openwa\.env is missing. Run setup-openwa.bat first.
    pause
    exit /b 1
)

echo [1/4] Starting OpenWA Dashboard (Vite dev server, port 2886)...
start "OpenWA Dashboard" cmd /k "cd openwa\dashboard && npm run dev"

echo [2/4] Starting OpenWA API (Nest, port 2785)...
start "OpenWA Gateway" cmd /k "cd openwa && npm start"

echo [3/4] Waiting 8 seconds for OpenWA services to boot...
timeout /t 8 /nobreak >nul

echo [4/4] Starting FastAPI server on port 8000...
start "FastAPI Server" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo.
echo ================================
echo  All services launched!
echo.
echo  OpenWA Dashboard: http://localhost:2886
echo  OpenWA API:       http://localhost:2785/api
echo  FastAPI:          http://localhost:8000
echo.
echo  IMPORTANT (one-time setup):
echo  1. Open the OpenWA dashboard  -^>  http://localhost:2886
echo  2. Create an API key          -^>  Settings -^> API Keys
echo  3. Create a session "barber-bot" -^> Sessions tab -^> Scan QR code
echo  4. Paste the API key into the main .env:
echo         OPENWA_API_KEY=...
echo  5. Create a webhook  -^>  Webhooks tab:
echo         URL   : http://localhost:8000/webhook
echo         Events: message.received, session.status
echo         Secret: barber-webhook-secret
echo  6. Restart this script.
echo.
echo  After the first setup, the bot runs locally with NO TUNNEL and
echo  no Meta webhook configuration.  Send "hi" to the WhatsApp number
echo  linked to the scanned QR.
echo ================================
echo.

start http://localhost:2886
pause
