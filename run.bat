@echo off
title StructSense - Building Health Monitoring
cd /d "%~dp0"
echo Starting StructSense...
if exist "..\structsensen\.venv\Scripts\python.exe" (
    "..\structsensen\.venv\Scripts\python.exe" run.py
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py
) else (
    python run.py
)
