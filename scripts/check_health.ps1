# --- 🩺 Platform Health Diagnostic Tool ---
# Suppress all interactive prompts and progress bars for CI/CD
$ProgressPreference = 'SilentlyContinue'
$ConfirmPreference = 'None'
$ErrorActionPreference = "SilentlyContinue"

Write-Output "`n[ System Health Report - $(Get-Date) ]"
Write-Output "------------------------------------------------"

# 1. Check Nginx
$nginx = Get-Process nginx
if ($nginx) {
    Write-Output "✅ Nginx: [RUNNING] (PIDs: $($nginx.Id -join ', '))"
} else {
    Write-Output "❌ Nginx: [CRASHED/STOPPED]"
}

# 2. Check Waitress (Flask)
$waitress = Get-Process waitress-serve
if ($waitress) {
    # Perform a deep check via the /health API
    try {
        # Added -UseBasicParsing here to prevent the "Script Execution Risk" prompt!
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/health" -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Output "✅ App (Waitress): [ACTIVE] (API: OK)"
        } else {
            Write-Output "⚠️ App (Waitress): [RUNNING] (API: Error $($response.StatusCode))"
        }
    } catch {
        Write-Output "❌ App (Waitress): [ZOMBIE] (Process exists but API is unreachable)"
    }
} else {
    Write-Output "❌ App (Waitress): [CRASHED/STOPPED]"
}

# 3. Check Cloudflared Tunnel
$cf = Get-Service cloudflared
if ($cf -and $cf.Status -eq "Running") {
    Write-Output "✅ Tunnel (Cloudflared): [ACTIVE]"
} else {
    Write-Output "❌ Tunnel (Cloudflared): [INACTIVE/STOPPED]"
}

Write-Output "------------------------------------------------`n"