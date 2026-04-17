# --- 🩺 Platform Health Diagnostic Tool ---
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
    # Perform a deep check via the /health API (increased timeout for 8GB RAM hardware)
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/health" -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Output "✅ App (Waitress): [ACTIVE] (API: OK)"
        } else {
            Write-Output "⚠️ App (Waitress): [RUNNING] (API: Error $($response.StatusCode))"
        }
    } catch {
        $err = $_.Exception.Message
        Write-Output "❌ App (Waitress): [ZOMBIE] ($err)"
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
