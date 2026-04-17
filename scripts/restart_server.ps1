# restart_server.ps1
# Master script for server startup, self-healing, and health verification.
# 100% ASCII ONLY to prevent encoding-related CMD crashes.

$ConfirmPreference = 'None'
$ProgressPreference = 'SilentlyContinue'
$ErrorActionPreference = "Continue"

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$NginxDir = "$ProjectDir\nginx-1.30.0"

Write-Output "--- Starting Platform Recovery & Startup ---"

# --- STEP 1: SAFETY CLEANUP (In case of manual restart) ---
$processesToKill = @("waitress-serve", "python", "nginx", "llama-server")
foreach ($name in $processesToKill) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    & taskkill /F /IM "$name.exe" /T 2> $null | Out-Null
}

# --- STEP 2: UPDATE DEPENDENCIES ---
Write-Output "Updating dependencies..."
& "$ProjectDir\venv\Scripts\python.exe" -m pip install -r "$ProjectDir\requirements.txt"

# --- STEP 3: NGINX SELF-HEALING ---
Write-Output "Self-healing: Verifying Nginx directories..."
$nginxTempDirs = @("temp", "temp/client_body_temp", "temp/proxy_temp", "temp/fastcgi_temp", "temp/uwsgi_temp", "temp/scgi_temp", "logs")
foreach ($dir in $nginxTempDirs) {
    if (-not (Test-Path "$NginxDir\$dir")) {
        New-Item -ItemType Directory -Path "$NginxDir\$dir" -Force | Out-Null
    }
}

# --- STEP 4: STARTUP ---
Write-Output "Starting Waitress on port 5000..."
Start-Process -FilePath "$ProjectDir\venv\Scripts\waitress-serve.exe" -ArgumentList "--port=5000 --call app:create_app" -WindowStyle Hidden -WorkingDirectory $ProjectDir

Write-Output "Starting Nginx..."
Set-Location $NginxDir
Start-Process -FilePath ".\nginx.exe" -WindowStyle Hidden

# --- STEP 5: VERIFY HEALTH ---
Write-Output "Waiting for stability..."
Start-Sleep -Seconds 5

Write-Output "[ Final System Health Check ]"
Write-Output "------------------------------------------------"
if (Get-Process nginx -ErrorAction SilentlyContinue) { Write-Output "OK: Nginx is [RUNNING]" } else { Write-Output "FAILED: Nginx did not start" }

try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/health" -TimeoutSec 5 -UseBasicParsing
    if ($response.StatusCode -eq 200) { Write-Output "OK: App (Waitress) is [ACTIVE]" }
} catch {
    Write-Output "FAILED: App (Waitress) is [UNREACHABLE]"
}

$cf = Get-Service cloudflared -ErrorAction SilentlyContinue
if ($cf -and $cf.Status -eq "Running") { Write-Output "OK: Tunnel is [ACTIVE]" }

Write-Output "------------------------------------------------"
Write-Output "DEPLOYMENT COMPLETE!"
