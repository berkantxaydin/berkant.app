# restart_server.ps1
# This script is called by GitHub Actions to deploy the app on Windows.

# Suppress all confirmation prompts globally for this script
$ConfirmPreference = 'None'

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$NginxDir = "$ProjectDir\nginx-1.30.0"

# 0. Ensure logs directory exists
if (-not (Test-Path "$ProjectDir\logs")) {
    New-Item -ItemType Directory -Path "$ProjectDir\logs" -Force
}

Write-Output "--- 🚀 Starting Native Windows Deployment ---"

# 1. Stop existing server processes
& "$ProjectDir\scripts\stop_server.ps1"

# 1b. Extra cleanup for deployment (Git daemons/locks)
Write-Output "Staging: Cleaning up development/Git processes..."
& git fsmonitor--daemon stop 2>$null
& git maintenance stop 2>$null

$extraProcesses = @("git", "node", "git-remote-https", "git-lfs")
foreach ($procName in $extraProcesses) {
    Get-Process -Name $procName -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

# Give Windows a moment to release file handles
Start-Sleep -Seconds 3

# 2. Update dependencies
Write-Output "Updating dependencies..."
& "$ProjectDir\venv\Scripts\python.exe" -m pip install -r "$ProjectDir\requirements.txt"

# 3. Start Waitress in the background
Write-Output "Starting Waitress server on port 5000..."
Start-Process -FilePath "$ProjectDir\venv\Scripts\waitress-serve.exe" -ArgumentList "--port=5000 --call app:create_app" -WindowStyle Hidden -WorkingDirectory $ProjectDir

# 4. Restart Nginx (Forceful restart is more reliable during deployment)
Write-Output "Restarting Nginx..."
# Ensure any previous instances are completely terminated
Stop-Process -Name nginx -Force -ErrorAction SilentlyContinue
# Fallback to taskkill for multi-process stubbornness
& taskkill /F /IM nginx.exe /T 2>$null

Start-Sleep -Seconds 1
Set-Location $NginxDir
Start-Process -FilePath ".\nginx.exe" -WindowStyle Hidden

# 5. Verify Health
Start-Sleep -Seconds 2
& "$ProjectDir\scripts\check_health.ps1"

Write-Output "✅ Native Deployment Complete!"