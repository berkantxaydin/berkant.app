# restart_server.ps1
# Master script for server startup, self-healing, and health verification.
# 100% ASCII ONLY to prevent encoding-related CMD crashes.

# Magic Fix: Detach processes from GitHub Actions runner cleanup
$env:RUNNER_TRACKING_ID = ""

$ConfirmPreference = 'None'
$ProgressPreference = 'SilentlyContinue'
$ErrorActionPreference = "Continue"

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$NginxDir = "$ProjectDir\nginx-1.30.0"

Write-Output "--- Starting Platform Recovery & Startup ---"

# --- STEP 0: ENVIRONMENT CLEANUP ---
# Remove any inherited Python variables that might cause "No Python at..." errors
$env:PYTHONHOME = $null
$env:PYTHONPATH = $null
$env:PYTHONNOUSERSITE = "1"

# --- STEP 1: SAFETY CLEANUP (In case of manual restart) ---
$processesToKill = @("waitress-serve", "python", "nginx", "llama-server")
foreach ($name in $processesToKill) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    & taskkill /F /IM "$name.exe" /T 2> $null | Out-Null
}

# --- STEP 2: VIRTUAL ENVIRONMENT HEALTH CHECK ---
Write-Output "Checking Python environment..."
$PythonExe = "$ProjectDir\venv\Scripts\python.exe"
$VenvBroken = $false

if (-not (Test-Path $PythonExe)) {
    Write-Output "WARNING: Virtual environment missing."
    $VenvBroken = $true
} else {
    try {
        & $PythonExe --version 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Python launcher failed" }
    } catch {
        Write-Output "WARNING: Virtual environment is BROKEN (launcher error)."
        $VenvBroken = $true
    }
}

if ($VenvBroken) {
    Write-Output "Self-healing: Recreating virtual environment..."
    $GlobalPython = "C:\Users\berka\AppData\Local\Programs\Python\Python312\python.exe"
    if (-not (Test-Path $GlobalPython)) {
        Write-Output "ERROR: Global Python not found at $GlobalPython. Cannot proceed."
        exit 1
    }
    
    if (Test-Path "$ProjectDir\venv") {
        Remove-Item -Path "$ProjectDir\venv" -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    & $GlobalPython -m venv "$ProjectDir\venv"
    if ($LASTEXITCODE -ne 0) {
        Write-Output "ERROR: Failed to create virtual environment."
        exit 1
    }
    Write-Output "SUCCESS: Virtual environment recreated."
}

# --- STEP 3: UPDATE DEPENDENCIES ---
Write-Output "Updating dependencies..."
& "$ProjectDir\venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
& "$ProjectDir\venv\Scripts\python.exe" -m pip install -r "$ProjectDir\requirements.txt"
if ($LASTEXITCODE -ne 0) {
    Write-Output "ERROR: Failed to install dependencies."
    exit 1
}

# --- STEP 3: NGINX SELF-HEALING ---
Write-Output "Self-healing: Verifying Nginx directories..."
$nginxTempDirs = @("temp", "temp/client_body_temp", "temp/proxy_temp", "temp/fastcgi_temp", "temp/uwsgi_temp", "temp/scgi_temp", "logs")
foreach ($dir in $nginxTempDirs) {
    if (-not (Test-Path "$NginxDir\$dir")) {
        New-Item -ItemType Directory -Path "$NginxDir\$dir" -Force | Out-Null
    }
}

# --- STEP 4: STARTUP ---
Write-Output "Preparing hidden startup configuration..."
$wmiProcess = [wmiclass]"Win32_Process"
$wmiStartup = [wmiclass]"Win32_ProcessStartup"
$startupConfig = $wmiStartup.CreateInstance()
$startupConfig.ShowWindow = [uint16]0 # 0 = Hidden

Write-Output "Starting Waitress on port 5000..."
$waitressCmd = "`"$ProjectDir\venv\Scripts\waitress-serve.exe`" --port=5000 --call app:create_app"
$wmiProcess.Create($waitressCmd, $ProjectDir, $startupConfig) | Out-Null

Write-Output "Starting Background Worker..."
$workerCmd = "`"$ProjectDir\venv\Scripts\python.exe`" bin/worker.py"
$wmiProcess.Create($workerCmd, $ProjectDir, $startupConfig) | Out-Null

Write-Output "Starting Nginx..."
$nginxCmd = "`"$NginxDir\nginx.exe`""
$wmiProcess.Create($nginxCmd, $NginxDir, $startupConfig) | Out-Null

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

if (Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like "*worker.py*" }) { Write-Output "OK: Worker is [ACTIVE]" } else { Write-Output "FAILED: Worker did not start" }

$cf = Get-Service cloudflared -ErrorAction SilentlyContinue
if ($cf -and $cf.Status -eq "Running") { Write-Output "OK: Tunnel is [ACTIVE]" }

Write-Output "------------------------------------------------"
Write-Output "DEPLOYMENT COMPLETE!"
