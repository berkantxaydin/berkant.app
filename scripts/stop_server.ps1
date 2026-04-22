# stop_server.ps1
# Stops all platform processes and cleans up temporary/backup folders.

$ProjectDir = (Get-Item $PSScriptRoot).Parent.FullName

Write-Output "--- Stopping Platform Processes ---"

# 1. Kill Application Processes
$processes = @("waitress-serve", "python", "nginx", "llama-server", "cloudflared")
foreach ($name in $processes) {
    Write-Output "Stopping $name..."
    Get-Process -Name $name -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    & taskkill /F /IM "$name.exe" /T 2> $null | Out-Null
}

# 2. Cleanup old venv folders
Write-Output "Cleaning up old virtual environment backups..."
Get-ChildItem -Path $ProjectDir -Filter "venv_old_*" -ErrorAction SilentlyContinue | 
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Output "--- System Stopped & Cleaned ---"
