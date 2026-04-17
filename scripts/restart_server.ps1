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

# 3. Start the server
& "$ProjectDir\scripts\start_server.ps1"

Write-Output "✅ Native Deployment Complete!"