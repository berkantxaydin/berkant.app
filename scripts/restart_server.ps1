# restart_server.ps1
# Master script for server startup, self-healing, and health verification.
# 100% ASCII ONLY to prevent encoding-related CMD crashes.

# Magic Fix: Detach processes from GitHub Actions runner cleanup
$env:RUNNER_TRACKING_ID = ""

$ConfirmPreference = 'None'
$ProgressPreference = 'SilentlyContinue'
$ErrorActionPreference = "Continue"

# Auto-detect Project Directory (Portable)
$ProjectDir = (Get-Item $PSScriptRoot).Parent.FullName
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

if (Test-Path "$ProjectDir\venv\bin\python.exe" -ErrorAction SilentlyContinue) {
    Write-Output "WARNING: MSYS2-style virtual environment detected. Forcing migration to standard Windows Python..."
    $VenvBroken = $true
} elseif (-not (Test-Path $PythonExe -ErrorAction SilentlyContinue)) {
    Write-Output "WARNING: Virtual environment missing."
    $VenvBroken = $true
} else {
    try {
        & $PythonExe --version 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Python launcher failed" }
        # NEW: Verify pip exists
        & $PythonExe -m pip --version 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Pip missing" }
    } catch {
        Write-Output "WARNING: Virtual environment is BROKEN or incomplete ($($_.Exception.Message))."
        $VenvBroken = $true
    }
}

if ($VenvBroken) {
    Write-Output "Self-healing: Recreating virtual environment..."
    
    # Robust Python Discovery
    $GlobalPython = $null
    
    # Try 1: Dynamic Discovery (PATH & Launcher)
    $GlobalPython = (Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
    if (-not $GlobalPython) {
        try { $GlobalPython = & py -3.12 -c "import sys; print(sys.executable)" 2>$null } catch { }
    }

    # Try 2: Common Global Paths
    if (-not $GlobalPython) {
        $commonPaths = @(
            "$env:SystemDrive\Program Files\Python312\python.exe",
            "$env:SystemDrive\Program Files\Python311\python.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
        )
        foreach ($path in $commonPaths) {
            if (Test-Path $path -ErrorAction SilentlyContinue) {
                $GlobalPython = $path
                break
            }
        }
    }

    # Try 3: Local Lab Fallback (Specific to current environment)
    if (-not $GlobalPython) {
        $labPath = "C:\Users\berka\AppData\Local\Programs\Python\Python312\python.exe"
        if (Test-Path $labPath -ErrorAction SilentlyContinue) { $GlobalPython = $labPath }
    }

    if (-not $GlobalPython -or -not (Test-Path $GlobalPython -ErrorAction SilentlyContinue)) {
        Write-Output "ERROR: No suitable Global Python found for self-healing."
        exit 1
    }
    
    Write-Output "Using source Python: $GlobalPython"
    
    if (Test-Path "$ProjectDir\venv") {
        Write-Output "Removing old virtual environment..."
        # Surgical Kill: Stop any process running from THIS venv
        Get-Process | Where-Object { $_.Path -like "$ProjectDir\venv\*" } | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        
        try {
            Remove-Item -Path "$ProjectDir\venv" -Recurse -Force -ErrorAction Stop
        } catch {
            Write-Output "WARNING: Could not delete venv folder (Locked). Renaming to preserve state..."
            $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
            Move-Item -Path "$ProjectDir\venv" -Destination "$ProjectDir\venv_old_$timestamp" -ErrorAction SilentlyContinue
        }
    }
    
    # Cleanup any very old venv_old folders (older than 1 hour)
    Get-ChildItem -Path $ProjectDir -Filter "venv_old_*" -ErrorAction SilentlyContinue | 
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddHours(-1) } | 
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    
    & $GlobalPython -m venv "$ProjectDir\venv" --with-pip
    if ($LASTEXITCODE -ne 0) {
        Write-Output "WARNING: standard venv creation failed. Trying secondary method..."
        & $GlobalPython -m venv "$ProjectDir\venv"
        & $PythonExe -m ensurepip --upgrade
    }
    
    if (-not (Test-Path $PythonExe)) {
        Write-Output "ERROR: Failed to create virtual environment."
        exit 1
    }
    Write-Output "SUCCESS: Virtual environment recreated."
}

# --- STEP 3: UPDATE DEPENDENCIES ---
Write-Output "Updating dependencies..."
& $PythonExe -m pip install --upgrade pip | Out-Null
& $PythonExe -m pip install -r "$ProjectDir\requirements.txt" --prefer-binary
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
$waitressPath = "$ProjectDir\venv\Scripts\waitress-serve.exe"
if (-not (Test-Path $waitressPath)) { $waitressPath = "$ProjectDir\venv\bin\waitress-serve.exe" }
$waitressCmd = "`"$waitressPath`" --port=5000 --call app:create_app"
$wmiProcess.Create($waitressCmd, $ProjectDir, $startupConfig) | Out-Null

Write-Output "Starting Background Worker..."
$workerCmd = "`"$PythonExe`" bin/worker.py"
$wmiProcess.Create($workerCmd, $ProjectDir, $startupConfig) | Out-Null

Write-Output "Starting Nginx..."
$nginxCmd = "`"$NginxDir\nginx.exe`""
$wmiProcess.Create($nginxCmd, $NginxDir, $startupConfig) | Out-Null

# --- STEP 5: NETWORKING (Portable/Random Tunnel) ---
if ($env:PORTABLE_MODE -eq "true") {
    Write-Output "Portable Mode Detected: Initializing random Cloudflared tunnel..."
    $cfPath = (Get-Command cloudflared.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
    if (-not $cfPath) { $cfPath = "$ProjectDir\bin\cloudflared.exe" }
    
    if (Test-Path $cfPath) {
        Write-Output "Launching Cloudflared in a new window to show the random URL..."
        Start-Process -FilePath $cfPath -ArgumentList "tunnel --url http://127.0.0.1" -WindowStyle Normal
    } else {
        Write-Output "WARNING: cloudflared.exe not found in PATH or bin/. External access will be disabled."
    }
}

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

if ($env:PORTABLE_MODE -eq "true") {
    if (Get-Process cloudflared -ErrorAction SilentlyContinue) { Write-Output "OK: Random Tunnel is [RUNNING]" }
} else {
    $cf = Get-Service cloudflared -ErrorAction SilentlyContinue
    if ($cf -and $cf.Status -eq "Running") { Write-Output "OK: Production Tunnel is [ACTIVE]" }
}

Write-Output "------------------------------------------------"
Write-Output "DEPLOYMENT COMPLETE!"
