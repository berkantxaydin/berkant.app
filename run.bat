@echo off
set PORTABLE_MODE=true
powershell -ExecutionPolicy Bypass -File "scripts\restart_server.ps1"
pause
