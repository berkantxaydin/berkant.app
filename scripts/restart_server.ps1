# --- Configuration ---
$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$NginxDir = "$ProjectDir\nginx-1.30.0"
$AppPort = 5000

# 0. Ensure crucial directories exist (Robocopy /MIR deletes these!)
$RequiredDirs = @(
    "$ProjectDir\logs",
    "$NginxDir\temp\client_body_temp",
    "$NginxDir\temp\proxy_temp",
    "$NginxDir\temp\fastcgi_temp",
    "$NginxDir\logs"
)

foreach ($dir in $RequiredDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Output "Restored missing directory: $dir"
    }
}

Write-Output "--- 🚀 Starting Native Windows Deployment ---"

# 1. Kill existing background processes
Write-Output "Staging: Cleaning up old processes..."
$processesToKill = @("waitress-serve", "python", "nginx", "git")

# Stop Git daemons
& git fsmonitor--daemon stop 2>$null

foreach ($procName in $processesToKill) {
    $foundProcs = Get-Process -Name $procName -ErrorAction SilentlyContinue
    if ($foundProcs) {
        Write-Output "Stopping $procName..."
        Stop-Process -Name $procName -Force -ErrorAction SilentlyContinue
    }
}

# Ensure port 5000 is free
$portProcess = Get-NetTCPConnection -LocalPort $AppPort -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
if ($portProcess) {
    Stop-Process -Id $portProcess -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2

# 2. Update dependencies
Write-Output "Updating dependencies..."
& "$ProjectDir\venv\Scripts\python.exe" -m pip install -r "$ProjectDir\requirements.txt"

# 3. Start Waitress in the background
Write-Output "Starting Waitress server on port $AppPort..."
$waitressArgs = "--port=$AppPort --call app:create_app"
Start-Process -FilePath "$ProjectDir\venv\Scripts\waitress-serve.exe" -ArgumentList $waitressArgs -WindowStyle Hidden -WorkingDirectory $ProjectDir

# 4. CRITICAL: Wait for Waitress to be READY (Fixes ZOMBIE status)
Write-Output "Waiting for App API to start listening..."
$retry = 0
$success = $false
while ($retry -lt 15) {
    $check = Test-NetConnection -ComputerName 127.0.0.1 -Port $AppPort -WarningAction SilentlyContinue
    if ($check.TcpTestSucceeded) {
        Write-Output "[OK] Waitress is ACTIVE and listening."
        $success = $true
        break
    }
    Start-Sleep -Seconds 1
    $retry++
}

if (-not $success) {
    Write-Error "Waitress failed to start within 15 seconds. Check app logs."
    exit 1
}

# 5. Start/Restart Nginx
Write-Output "Starting Nginx..."
Set-Location $NginxDir
# If Nginx crashed, 'reload' won't work, so we just start it fresh
if (Get-Process nginx -ErrorAction SilentlyContinue) {
    .\nginx.exe -s stop
    Start-Sleep -Seconds 1
}
Start-Process -FilePath ".\nginx.exe" -WindowStyle Hidden

# 6. Verify Health
Write-Output "Running health check..."
Start-Sleep -Seconds 2
& "$ProjectDir\scripts\check_health.ps1"

Write-Output "✅ Native Deployment Complete!"