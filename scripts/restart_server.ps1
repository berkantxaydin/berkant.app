# restart_server.ps1
# This script is called by GitHub Actions to deploy the app on Windows.

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$NginxDir = "$ProjectDir\nginx-1.30.0"

# 0. Ensure logs directory exists
if (-not (Test-Path "$ProjectDir\logs")) {
    New-Item -ItemType Directory -Path "$ProjectDir\logs" -Force
}

Write-Output "--- 🚀 Starting Native Windows Deployment ---"

# 1. Kill existing background processes (Waitress, Nginx, or lingering Git/Python)
Write-Output "Staging: Cleaning up old processes..."

# List of process names to terminate if they are locking the project directory
$processesToKill = @("waitress-serve", "python", "nginx", "git")

foreach ($procName in $processesToKill) {
    $foundProcs = Get-Process -Name $procName -ErrorAction SilentlyContinue
    foreach ($proc in $foundProcs) {
        try {
            # Only kill if the process is related to this project (optional path check)
            # If path check fails due to permissions, we still kill waitress/nginx by name
            if ($proc.Path -like "$ProjectDir*" -or $procName -eq "waitress-serve" -or $procName -eq "nginx") {
                Write-Output "Stopping $procName (PID: $($proc.Id))..."
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
            Write-Output "⚠️ Could not stop $procName (PID: $($proc.Id)) - it might already be closing."
        }
    }
}

# Also ensure port 5000 is definitely free
$portProcess = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
if ($portProcess) {
    Write-Output "Force-killing leftover process on port 5000 (PID: $portProcess)..."
    Stop-Process -Id $portProcess -Force -ErrorAction SilentlyContinue
}

# Give Windows a moment to release file handles
Start-Sleep -Seconds 3

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
