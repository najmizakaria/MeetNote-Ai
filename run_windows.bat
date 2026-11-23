@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto dependencies
py -3.11 -m venv .venv
if errorlevel 1 if exist "%LocalAppData%\Python\pythoncore-3.11-64\python.exe" "%LocalAppData%\Python\pythoncore-3.11-64\python.exe" -m venv .venv
if errorlevel 1 (
    echo Install Python 3.11 for Windows with the py launcher, then open this file again.
    goto failed
)
:dependencies
.venv\Scripts\python.exe -c "import faster_whisper, httpx, docx, sounddevice" >nul 2>&1
if errorlevel 1 (
    .venv\Scripts\python.exe -m pip install -r requirements-windows.txt
    if errorlevel 1 goto failed
)
.venv\Scripts\python.exe desktop_app.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo MeetNote AI could not start.
pause
exit /b 1
