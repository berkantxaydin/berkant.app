# restart_server.ps1
# MASTER SCRIPT: Handles complete shutdown, self-healing, and startup of the platform.
# This script is designed for both manual use and automated GitHub Runners.

# 1. Force non-interactive mode
$ConfirmPreference = 'None'
$ProgressPreference = 'SilentlyContinue'
$ErrorActionPreference = "Continue"

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$NginxDir = "$ProjectDir\nginx-1.30.0"

Write-Output "`n--- 🚀 Starting Consolidated Native Recovery & Deployment ---"

# --- STEP 1: AGGRESSIVE CLEANUP (Kill everything to free RAM and Ports) ---
Write-Output "Staging: Performing aggressive process cleanup..."

# Stop Git services first
& git fsmonitor--daemon stop 2>$null
& git maintenance stop 2>$null

$processesToKill = @("waitress-serve", "python", "nginx", "llama-server", "git", "node", "git-remote-https", "git-lfs")

foreach ($name in $processesToKill) {
    Write-Output "Stopping all $name processes..."
    # Attempt polite kill
    Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    # Forceful nuke (includes child processes)
    & taskkill /F /IM "$name.exe" /T 2>$null
}

# --- STEP 2: PORT HARDENING (Ensure ports 80, 443, 5000, 8082 are clear) ---
$ports = @(80, 443, 5000, 8082)
foreach ($port in $ports) {
    $portProcess = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
    if ($portProcess) {
        Write-Output "Force-killing process on port $port (PID: $portProcess)..."
        Stop-Process -Id $portProcess -Force -ErrorAction SilentlyContinue
        & taskkill /F /PID $portProcess /T 2>$null
    }
}

# Give Windows a moment to release file handles
Start-Sleep -Seconds 3
Write-Output "✅ RAM and Ports cleared."

# --- STEP 3: UPDATE DEPENDENCIES ---
Write-Output "Updating dependencies..."
& "$ProjectDir\venv\Scripts\python.exe" -m pip install -r "$ProjectDir\requirements.txt"

# --- STEP 4: NGINX SELF-HEALING (Fix 'The system cannot find the path specified' crash) ---
Write-Output "Self-healing: Verifying Nginx directory structure..."
$nginxTempDirs = @("temp", "temp/client_body_temp", "temp/proxy_temp", "temp/fastcgi_temp", "temp/uwsgi_temp", "temp/scgi_temp", "logs")
foreach ($dir in $nginxTempDirs) {
    if (-not (Test-Path "$NginxDir\$dir")) {
        New-Item -ItemType Directory -Path "$NginxDir\$dir" -Force | Out-Null
    }
}

# --- STEP 5: STARTUP (Waitress & Nginx) ---
Write-Output "Starting Waitress server on port 5000..."
Start-Process -FilePath "$ProjectDir\venv\Scripts\waitress-serve.exe" -ArgumentList "--port=5000 --call app:create_app" -WindowStyle Hidden -WorkingDirectory $ProjectDir

Write-Output "Starting Nginx..."
Set-Location $NginxDir
Start-Process -FilePath ".\nginx.exe" -WindowStyle Hidden

# --- STEP 6: VERIFY HEALTH (Non-Interactive) ---
Write-Output "Waiting for system stability..."
Start-Sleep -Seconds 5

Write-Output "`n[ Final System Health Check ]"
Write-Output "------------------------------------------------"

# Nginx Check
$nginxProc = Get-Process nginx -ErrorAction SilentlyContinue
if ($nginxProc) {
    Write-Output "✅ Nginx: [RUNNING]"
} else {
    Write-Output "❌ Nginx: [FAILED TO START] - Check $NginxDir\logs\error.log"
}

# Waitress Check (Force Basic Parsing to avoid IE prompt)
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/health" -TimeoutSec 5 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Output "✅ App (Waitress): [ACTIVE] (API OK)"
    } else {
        Write-Output "⚠️ App (Waitress): [ERROR] (HTTP $($response.StatusCode))"
    }
} catch {
    Write-Output "❌ App (Waitress): [UNREACHABLE] - API did not respond"
}

# Tunnel Check
$cf = Get-Service cloudflared -ErrorAction SilentlyContinue
if ($cf -and $cf.Status -eq "Running") {
    Write-Output "✅ Tunnel: [ACTIVE]"
} else {
    Write-Output "❌ Tunnel: [INACTIVE]"
}

Write-Output "------------------------------------------------"
Write-Output "✅ Native Deployment Complete (Master Script)!"
