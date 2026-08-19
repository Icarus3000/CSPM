@echo off
cd /d "%~dp0"
setlocal enabledelayedexpansion

set "CSPM_SPLASH_WEBENGINE=1"
set "CSPM_SPLASH_FORCE_WEBENGINE=1"
set "CSPM_SPLASH_WEBVIEW=0"
set "CSPM_SPLASH_LOGO_VARIANT=animated"
set "CSPM_PREINIT_WEBENGINE=1"
set "CSPM_SPLASH_TOTAL_MS=500"

set "PYTHON_EXE="
if exist ".venv_CORY_CorySchneider\Scripts\python.exe" (
    set "PYTHON_EXE=.venv_CORY_CorySchneider\Scripts\python.exe"
) else (
    for /d %%D in (.venv*) do (
        if exist "%%D\Scripts\python.exe" (
            set "PYTHON_EXE=%%D\Scripts\python.exe"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    echo [ERROR] No Python virtual environment found.
    pause
    exit /b 1
)

echo ========================================
echo  CSPM Launcher (%COMPUTERNAME% / %USERNAME%)
echo ========================================
echo Using Python: %PYTHON_EXE%
echo Launching application...
echo.

"%PYTHON_EXE%" src\python\main.py %*
if errorlevel 1 (
    echo.
    echo [CSPM] Application exited with error code %ERRORLEVEL%
    pause
)
