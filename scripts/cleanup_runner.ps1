# cleanup_runner.ps1
# Consistently stops all processes and clears runner locks.

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$RunnerDir = "C:\Users\berka\runner_work"

Write-Output "--- 🧹 Starting Surgical Runner Cleanup ---"

# 1. Kill processes (Waitress, Nginx, AI Engine)
Write-Output "Stopping all platform processes..."
$locks = @("waitress-serve", "python", "nginx", "llama-server", "git", "node", "git-remote-https")
foreach ($name in $locks) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    & taskkill /F /IM "$name.exe" /T 2>$null
}

# 2. Clear Ports (80, 443, 5000, 8082)
$ports = @(80, 443, 5000, 8082)
foreach ($port in $ports) {
    $portProcess = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
    if ($portProcess) {
        Write-Output "Killing process on port $port (PID: $portProcess)..."
        Stop-Process -Id $portProcess -Force -ErrorAction SilentlyContinue
        & taskkill /F /PID $portProcess /T 2>$null
    }
}

# 3. Clear the _temp directories inside _work (Prevents EBUSY)
if (Test-Path "$RunnerDir\_temp") {
    Write-Output "Clearing runner _temp folders..."
    Get-ChildItem -Path "$RunnerDir\_temp" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

# 4. Stop Git Daemons
& git fsmonitor--daemon stop 2>$null
& git maintenance stop 2>$null

Write-Output "✅ Runner environment stabilized and unlocked."
