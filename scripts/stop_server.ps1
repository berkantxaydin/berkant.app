# stop_server.ps1
# Manually stops all server-related processes (Waitress and Nginx).

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"

Write-Output "--- 🛑 Stopping Server Processes ---"

# 1. Kill Waitress/Python
Write-Output "Stopping Waitress (Python)..."
Stop-Process -Name "waitress-serve" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue

# 2. Kill Nginx
Write-Output "Stopping Nginx..."
Stop-Process -Name "nginx" -Force -ErrorAction SilentlyContinue
& taskkill /F /IM nginx.exe /T 2>$null

# 3. Extra insurance: Port 5000 cleanup
$portProcess = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
if ($portProcess) {
    Write-Output "Force-killing leftover process on port 5000 (PID: $portProcess)..."
    Stop-Process -Id $portProcess -Force -ErrorAction SilentlyContinue
}

Write-Output "✅ All server processes stopped."
