@echo off
cd /d "%~dp0"
echo !!! WARNING: THIS WILL DELETE ALL DATABASE DATA AND UPLOADS !!!
set /p confirm="Type YES to confirm factory reset: "
if /i "%confirm%"=="YES" (
    powershell -ExecutionPolicy Bypass -File "factory_reset.ps1"
) else (
    echo Reset cancelled.
)
pause
