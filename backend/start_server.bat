@echo off
chcp 65001 >nul
REM TenderWord Backend Startup Script for Windows
REM This script ensures proper PYTHONPATH for uvicorn reload mode

cd /d "%~dp0\.."

echo Starting TenderWord Backend...
echo Project root: %CD%
echo.

set PYTHONPATH=%CD%

 cd backend
 
 echo Running: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
 echo.
 uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
