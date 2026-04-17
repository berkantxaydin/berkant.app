# start_server.ps1
# Manually starts the server processes (Waitress and Nginx).

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$NginxDir = "$ProjectDir\nginx-1.30.0"

Write-Output "--- 🚀 Starting Server Processes ---"

# 1. Start Waitress
Write-Output "Starting Waitress server on port 5000..."
Start-Process -FilePath "$ProjectDir\venv\Scripts\waitress-serve.exe" -ArgumentList "--port=5000 --call app:create_app" -WindowStyle Hidden -WorkingDirectory $ProjectDir

# 2. Start Nginx
Write-Output "Starting Nginx..."
if (Test-Path "$NginxDir\nginx.exe") {
    Set-Location $NginxDir
    Start-Process -FilePath ".\nginx.exe" -WindowStyle Hidden
} else {
    Write-Output "❌ Error: Nginx not found at $NginxDir"
}

# 3. Verify Health
Start-Sleep -Seconds 2
& "$ProjectDir\scripts\check_health.ps1"

Write-Output "✅ Server processes started."
