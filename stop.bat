@echo off
title AI Barber Bot - Stop

echo Stopping AI Barber Bot servers...

:: Kill uvicorn / python processes
taskkill /F /FI "WINDOWTITLE eq FastAPI Server" 2>nul
taskkill /F /IM python.exe /FI "WindowTitle eq FastAPI*" 2>nul

:: Kill cloudflared
taskkill /F /IM cloudflared.exe 2>nul

:: Kill any remaining python on port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do (
    taskkill /F /PID %%a 2>nul
)

echo.
echo All servers stopped.
timeout /t 2 /nobreak >nul
