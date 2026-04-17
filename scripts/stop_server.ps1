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

# 3. Kill AI Engine (Llama)
Write-Output "Stopping AI Engine (Llama)..."
Stop-Process -Name "llama-server" -Force -ErrorAction SilentlyContinue
& taskkill /F /IM llama-server.exe /T 2>$null

# 4. Extra insurance: Port cleanup (5000, 80, 443)
$ports = @(5000, 80, 443)
foreach ($port in $ports) {
    $portProcess = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
    if ($portProcess) {
        Write-Output "Force-killing process on port $port (PID: $portProcess)..."
        Stop-Process -Id $portProcess -Force -ErrorAction SilentlyContinue
    }
}

Write-Output "✅ All server processes stopped."
