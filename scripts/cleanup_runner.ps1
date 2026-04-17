# cleanup_runner.ps1
# Emergency script to clear GitHub Action Runner locks on Windows.
# Run this if deployment continuously fails with EBUSY errors.

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$RunnerWorkDir = "$ProjectDir\actions-runner\_work"

Write-Output "--- 🧹 Starting Emergency Runner Cleanup ---"

# 1. Stop the Runner Service if it's running
Write-Output "Stopping GitHub Runner services..."
Get-Service "actions.runner.*" | Stop-Service -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 2. Kill all potentially locking processes
Write-Output "Killing ALL Flask, Waitress, Nginx, Git, and Node processes..."

# Explicitly stop Git daemons
& git fsmonitor--daemon stop 2>$null
& git maintenance stop 2>$null
git config --local core.fsmonitor false

$locks = @("waitress-serve", "python", "nginx", "git", "node")
foreach ($name in $locks) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

# 3. Clear the _temp directories inside _work
Write-Output "Cleaning temporary runner files..."
if (Test-Path "$RunnerWorkDir\_temp") {
    Remove-Item -Path "$RunnerWorkDir\_temp\*" -Recurse -Force -ErrorAction SilentlyContinue
}

# 4. Success message
Write-Output "✅ Cleanup complete. You can now restart the runner service."
Write-Output "Run: Start-Service 'actions.runner.*'"
