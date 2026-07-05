@echo off
chcp 65001 >nul 2>&1

:: Kill any old server on port 8765
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8765.*LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Change to script directory
cd /d "%~dp0"

:: Use absolute path to TeleAgent Python
set "PY=C:\Users\xiaoh\.local\share\TeleAgent\runtimes\python\python.exe"

:: Fallback: try system python if bundled not found
if not exist "%PY%" (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PY=python"
    ) else (
        echo [ERROR] Python not found!
        pause
        exit /b 1
    )
)

:: Run server (it will auto-open browser)
"%PY%" "flower_server.py"
echo.
echo [INFO] Server stopped.
pause
