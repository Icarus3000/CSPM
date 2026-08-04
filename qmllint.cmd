@echo off
setlocal

set "_SCRIPT=%~dp0scripts\qmllint.ps1"
if not exist "%_SCRIPT%" (
  echo [QMLLINT] Missing script: "%_SCRIPT%"
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%_SCRIPT%" %*
exit /b %ERRORLEVEL%
