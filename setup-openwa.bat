@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   OpenWA Setup - Local Development
echo ============================================
echo.

REM ----- Step 1: Clone or update OpenWA -----
if not exist "openwa" (
    echo [1/6] Cloning OpenWA...
    git clone https://github.com/rmyndharis/OpenWA.git openwa
    if !errorlevel! neq 0 (
        echo ERROR: Failed to clone OpenWA. Check your internet connection and git.
        pause
        exit /b 1
    )
    echo       Done!
) else (
    echo [1/6] OpenWA already exists, skipping clone
    cd openwa
    echo       Pulling latest...
    git pull --ff-only 2>nul
    if !errorlevel! neq 0 (
        echo       (pull skipped - no network or local changes)
    )
    cd ..
)

REM ----- Step 2: Install root dependencies -----
echo.
echo [2/6] Installing OpenWA API dependencies...
cd openwa
if not exist "node_modules" (
    call npm install
    if !errorlevel! neq 0 (
        echo ERROR: npm install failed. Make sure Node.js 22 LTS is installed.
        pause
        exit /b 1
    )
) else (
    echo       node_modules already present
)
echo       Done!

REM ----- Step 3: Install dashboard dependencies -----
echo.
echo [3/6] Installing OpenWA Dashboard dependencies (Vite + React)...
cd dashboard
if not exist "node_modules" (
    call npm install
    if !errorlevel! neq 0 (
        echo ERROR: Dashboard npm install failed.
        pause
        exit /b 1
    )
) else (
    echo       dashboard/node_modules already present
)
cd ..
echo       Done!

REM ----- Step 4: Create .env from example if missing -----
echo.
echo [4/6] Configuring OpenWA...
if not exist ".env" (
    copy .env.example .env >nul
    echo       Created .env from .env.example
)

REM Make sure database + engine are pinned (whatsapp-web.js is the only engine
REM bundled in v0.1.6; Baileys is listed as "future" in the example).
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$p = '.env';" ^
    "if ((Get-Content $p) -notmatch '^DATABASE_TYPE=') { Add-Content $p 'DATABASE_TYPE=sqlite' }" ^
    "if ((Get-Content $p) -notmatch '^ENGINE_TYPE=')   { Add-Content $p 'ENGINE_TYPE=whatsapp-web.js' }" ^
    "(Get-Content $p) | ForEach-Object { $_ -replace '^ENGINE_TYPE=.*','ENGINE_TYPE=whatsapp-web.js' -replace '^DATABASE_TYPE=.*','DATABASE_TYPE=sqlite' } | Set-Content $p"
echo       Engine = whatsapp-web.js
echo       Database = sqlite
echo       Done!

REM ----- Step 5: Build TypeScript -----
echo.
echo [5/6] Building OpenWA API (TypeScript ^> JS)...
if not exist "dist\main.js" (
    call npm run build
    if !errorlevel! neq 0 (
        echo ERROR: build failed
        pause
        exit /b 1
    )
) else (
    echo       dist\main.js already present
)
echo       Done!

cd ..

REM ----- Step 6: Bootstrap main .env with OpenWA defaults -----
echo.
echo [6/6] Configuring Python bot .env...
if not exist ".env" (
    copy .env.example .env >nul
    echo       Created .env from .env.example
)

REM Ensure the OpenWA section exists, leaving values blank for the user to fill.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$p = '.env';" ^
    "if ((Get-Content $p) -notmatch '^OPENWA_API_URL=')        { Add-Content $p 'OPENWA_API_URL=http://localhost:2785' }" ^
    "if ((Get-Content $p) -notmatch '^OPENWA_API_KEY=')        { Add-Content $p 'OPENWA_API_KEY=' }" ^
    "if ((Get-Content $p) -notmatch '^OPENWA_SESSION_ID=')      { Add-Content $p 'OPENWA_SESSION_ID=barber-bot' }" ^
    "if ((Get-Content $p) -notmatch '^OPENWA_WEBHOOK_SECRET=')  { Add-Content $p 'OPENWA_WEBHOOK_SECRET=barber-webhook-secret' }"

echo.
echo ============================================
echo   OpenWA setup complete!
echo ============================================
echo.
echo NEXT STEPS (one time):
echo.
echo   1. Start OpenWA + the bot:
echo        start-openwa.bat
echo.
echo   2. Open the OpenWA dashboard:
echo        http://localhost:2886
echo.
echo   3. In the dashboard:
echo        - Create an API key   (Settings -^> API Keys)
echo        - Create a session    named "barber-bot"  (Sessions tab)
echo        - Start the session   and SCAN the QR code with WhatsApp
echo        - Copy the API key into the main .env:
echo              OPENWA_API_KEY=...
echo              OPENWA_SESSION_ID=barber-bot
echo        - Create a webhook   (Webhooks tab):
echo              URL   : http://localhost:8000/webhook
echo              Events: message.received, session.status
echo              Secret: barber-webhook-secret   (must match OPENWA_WEBHOOK_SECRET)
echo.
echo   4. Restart the bot:   start-openwa.bat
echo   5. Send "hi" to the barber's WhatsApp number.
echo.
echo NO TUNNELING, NO META WEBHOOK CONFIG, NO CERT ISSUES.
echo.
endlocal
pause
