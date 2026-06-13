@echo off
title AI Barber Bot - Stop

echo Stopping AI Barber Bot services...

:: Kill uvicorn / python (FastAPI)
taskkill /F /FI "WINDOWTITLE eq FastAPI Server" 2>nul
taskkill /F /IM python.exe /FI "WindowTitle eq FastAPI*" 2>nul

:: Kill OpenWA dashboard window + node processes
taskkill /F /FI "WINDOWTITLE eq OpenWA Dashboard" 2>nul
taskkill /F /FI "WINDOWTITLE eq OpenWA Gateway" 2>nul

:: Kill cloudflared if running
taskkill /F /IM cloudflared.exe 2>nul

:: Kill any node.exe leftover from OpenWA
taskkill /F /IM node.exe /FI "WindowTitle eq OpenWA*" 2>nul
taskkill /F /IM node.exe /FI "WindowTitle eq Dashboard*" 2>nul

:: Kill any remaining python on port 8000 (FastAPI)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do (
    taskkill /F /PID %%a 2>nul
)

:: Kill any remaining node on port 2785 (OpenWA API)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":2785"') do (
    taskkill /F /PID %%a 2>nul
)

:: Kill any remaining node on port 2886 (OpenWA dashboard)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":2886"') do (
    taskkill /F /PID %%a 2>nul
)

echo.
echo All services stopped.
timeout /t 2 /nobreak >nul
