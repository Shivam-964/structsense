@echo off
title StructSense - Building Health Monitoring
cd /d "%~dp0"

echo =======================================================
echo   Starting StructSense Building Health Monitoring...
echo =======================================================

if exist "..\.venv\Scripts\python.exe" (
    echo Using project virtual environment: ..\.venv
    "..\.venv\Scripts\python.exe" app.py
) else if exist ".venv\Scripts\python.exe" (
    echo Using project virtual environment: .venv
    ".venv\Scripts\python.exe" app.py
) else (
    echo Using system Python...
    python app.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred while running StructSense.
    pause
)
