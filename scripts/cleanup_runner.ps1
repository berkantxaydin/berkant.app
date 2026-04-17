# cleanup_runner.ps1
# Surgical cleanup for GitHub Actions self-hosted runner on Windows.
# This script targets lingering processes that lock the 'runner_work' directory.

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$RunnerDir = "C:\Users\berka\runner_work"
$CurrentPID = $PID

Write-Output "--- 🧹 Starting Surgical Runner Cleanup ---"

# 1. Kill stale processes locking the runner_work or project directories
# We specifically target processes that are NOT our current PowerShell session.
Write-Output "Cleaning up stale locks..."
& git fsmonitor--daemon stop 2>$null
& git maintenance stop 2>$null
git config --local core.fsmonitor false

$locks = @("waitress-serve", "python", "nginx", "git", "node", "git-remote-https", "git-lfs")
foreach ($name in $locks) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$ProjectDir*" -or $_.Path -like "$RunnerDir*" } | Stop-Process -Force -ErrorAction SilentlyContinue
}

# 3. Clear the _temp directories inside _work
# This is often where EBUSY happens.
if (Test-Path "$RunnerDir\_temp") {
    Write-Output "Clearing runner _temp folders..."
    Get-ChildItem -Path "$RunnerDir\_temp" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output "✅ Runner environment stabilized."
