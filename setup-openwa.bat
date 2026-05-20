@echo off
echo ============================================
echo   OpenWA Setup - Local Development
echo ============================================
echo.

REM Check if OpenWA is already cloned
if not exist "openwa" (
    echo [1/4] Cloning OpenWA...
    git clone https://github.com/rmyndharis/OpenWA.git openwa
    if %errorlevel% neq 0 (
        echo ERROR: Failed to clone OpenWA
        pause
        exit /b 1
    )
    echo Done!
) else (
    echo [1/4] OpenWA already exists, skipping clone
)

cd openwa

echo [2/4] Installing dependencies...
call npm install
if %errorlevel% neq 0 (
    echo ERROR: npm install failed. Make sure Node.js is installed.
    pause
    exit /b 1
)
echo Done!

echo [3/4] Configuring Baileys engine...
if not exist ".env" (
    copy .env.example .env
)

REM Set Baileys engine in .env
powershell -Command "(Get-Content .env) -replace 'ENGINE_TYPE=.*', 'ENGINE_TYPE=baileys' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'DATABASE_TYPE=.*', 'DATABASE_TYPE=sqlite' | Set-Content .env"
echo Engine set to Baileys (lightweight, no Chromium)
echo Done!

echo.
echo [4/4] Starting OpenWA...
echo.
echo After startup:
echo   1. Go to http://localhost:2886 (Dashboard)
echo   2. Create an API key
echo   3. Create a session named 'barber-bot'
echo   4. Start the session and scan the QR code
echo   5. Copy the session ID and API key to .env
echo.
echo API:  http://localhost:2785/api
echo Docs: http://localhost:2785/api/docs
echo.

start http://localhost:2886

call npm run dev
