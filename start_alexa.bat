@echo off
chcp 65001 >nul
title Alexa
cd /d "%~dp0"

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not defined PY if exist "env\Scripts\python.exe" set "PY=env\Scripts\python.exe"

if not defined PY (
    echo Virtual environment not found in %cd%
    echo Create it with:  python -m venv .venv
    echo Or edit start_alexa.bat and set PY to your python.exe path.
    pause
    exit /b 1
)

if not exist "main.py" (
    echo main.py not found in %cd%
    pause
    exit /b 1
)

timeout /t 10 /nobreak >nul

:loop
"%PY%" main.py
echo.
echo Alexa stopped. Restarting in 5 seconds (close the window to quit)...
timeout /t 5 /nobreak >nul
goto loop