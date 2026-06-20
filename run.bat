@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Windows Local Hardware Monitor
echo ========================================

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating the .venv virtual environment...
    where py >nul 2>nul
    if not errorlevel 1 (
        py -m venv .venv
    ) else (
        python -m venv .venv
    )

    if errorlevel 1 (
        echo.
        echo Failed to create the virtual environment.
        echo Install Python 3.10 or newer and enable "Add Python to PATH".
        pause
        exit /b 1
    )
) else (
    echo [1/3] Existing virtual environment found.
)

echo [2/3] Installing or checking dependencies...
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Dependency installation failed. Check the network and try again.
    pause
    exit /b 1
)

echo [3/3] Starting the server...
echo.
echo The browser will open automatically when the server is ready.
echo Address: http://127.0.0.1:8000
echo Press Ctrl+C to stop the server.
echo.

rem Wait until FastAPI is reachable, then open the default browser.
start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "$url='http://127.0.0.1:8000'; for ($i=0; $i -lt 60; $i++) { try { $response=Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 1; if ($response.StatusCode -eq 200) { Start-Process $url; exit 0 } } catch {}; Start-Sleep -Milliseconds 500 }; exit 1"

python -m uvicorn main:app --host 127.0.0.1 --port 8000

echo.
echo Server stopped.
pause
