# restart_server.ps1
# This script is called by GitHub Actions to deploy the app on Windows.

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$NginxDir = "$ProjectDir\nginx-1.30.0"

# 0. Ensure logs directory exists
if (-not (Test-Path "$ProjectDir\logs")) {
    New-Item -ItemType Directory -Path "$ProjectDir\logs" -Force
}

Write-Output "--- 🚀 Starting Native Windows Deployment ---"

# 1. Kill existing Waitress process on port 5000
Write-Output "Staging: Cleaning up old processes..."
$oldProcess = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
if ($oldProcess) {
    Write-Output "Stopping existing app (PID: $oldProcess)..."
    Stop-Process -Id $oldProcess -Force
    Start-Sleep -Seconds 2
}

# 2. Update dependencies
Write-Output "Updating dependencies..."
& "$ProjectDir\venv\Scripts\python.exe" -m pip install -r "$ProjectDir\requirements.txt"

# 3. Start Waitress in the background
Write-Output "Starting Waitress server on port 5000..."
Start-Process -FilePath "$ProjectDir\venv\Scripts\waitress-serve.exe" -ArgumentList "--port=5000 --call app:create_app" -WindowStyle Hidden -WorkingDirectory $ProjectDir

# 4. Check/Restart Nginx
Write-Output "Checking Nginx status..."
$nginxProcess = Get-Process nginx -ErrorAction SilentlyContinue
if ($nginxProcess) {
    Write-Output "Reloading Nginx configuration..."
    Set-Location $NginxDir
    .\nginx.exe -s reload
} else {
    Write-Output "Starting Nginx..."
    Set-Location $NginxDir
    Start-Process -FilePath ".\nginx.exe" -WindowStyle Hidden
}

# 5. Verify Health
Start-Sleep -Seconds 2
& "$ProjectDir\scripts\check_health.ps1"

Write-Output "✅ Native Deployment Complete!"
