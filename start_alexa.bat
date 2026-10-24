@echo off
chcp 65001 >nul
title Alexa
cd /d "%~dp0"

rem Find the virtual environment's python (first match wins)
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

rem Pass "now" to skip the startup delay: start_alexa.bat now
if /i not "%~1"=="now" timeout /t 10 /nobreak >nul

set /a FAILS=0

:loop
"%PY%" -X utf8 main.py
rem Save the exit code right away, later commands may overwrite it
set "CODE=%errorlevel%"
if "%CODE%"=="0" (
    echo.
    echo Alexa exited normally.
    exit /b 0
)

set /a FAILS+=1
echo.
echo Alexa crashed (exit code %CODE%, crash %FAILS% of 5).
if %FAILS% geq 5 (
    echo Too many crashes in a row. Check the error above and fix it.
    pause
    exit /b %CODE%
)

echo Restarting in 5 seconds (close the window to quit)...
timeout /t 5 /nobreak >nul
goto loop
