# cleanup_runner.ps1
# Consistently stops all platform processes and clears runner locks.
# Hardened to avoid the 'Suicide Bug' by only cleaning STALE temp files.

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$RunnerDir = "C:\Users\berka\runner_work"

Write-Output "--- Starting Surgical Runner Cleanup ---"

# 1. Kill processes (Waitress, Nginx, AI Engine)
Write-Output "Stopping all platform processes..."
$locks = @("waitress-serve", "python", "nginx", "llama-server", "git", "node", "git-remote-https")
foreach ($name in $locks) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    & taskkill /F /IM "$name.exe" /T 2> $null | Out-Null
}

# 2. Clear Ports (80, 443, 5000, 8082)
$ports = @(80, 443, 5000, 8082)
foreach ($port in $ports) {
    try {
        $portProcess = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
        if ($portProcess) {
            Write-Output "Killing process on port $port (PID: $portProcess)..."
            Stop-Process -Id $portProcess -Force -ErrorAction SilentlyContinue
            & taskkill /F /PID $portProcess /T 2> $null | Out-Null
        }
    } catch { }
}

# 3. Clear STALE runner temp folders (Older than 5 minutes)
# This prevents the script from deleting the current run's temp batch file.
if (Test-Path "$RunnerDir\_temp") {
    Write-Output "Clearing stale runner temp folders (Safety Window: 5m)..."
    $staleLimit = (Get-Date).AddMinutes(-5)
    Get-ChildItem -Path "$RunnerDir\_temp" -ErrorAction SilentlyContinue | 
        Where-Object { $_.LastWriteTime -lt $staleLimit } | 
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

# 4. Stop Git Daemons (Silent)
& git fsmonitor--daemon stop 2> $null | Out-Null
& git maintenance stop 2> $null | Out-Null

Write-Output "CLEANUP COMPLETE. ENVIRONMENT UNLOCKED."
exit 0
