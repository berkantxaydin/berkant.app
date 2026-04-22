# factory_reset.ps1
# WARNING: This script deletes ALL user data, databases, and logs.
# Use this to return the platform to a pristine, "just installed" state.

$ProjectDir = (Get-Item $PSScriptRoot).Parent.FullName

# 1. Stop everything first
Write-Output "Stopping all processes..."
powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\stop_server.ps1"

Write-Output "--- Performing Factory Reset ---"

# 2. Delete Databases
Write-Output "Deleting databases..."
Get-ChildItem -Path $ProjectDir -Filter "*.db*" -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Path "$ProjectDir\db" -Filter "*.db*" -ErrorAction SilentlyContinue | Remove-Item -Force

# 3. Clear Local Submissions (Mock S3)
$mockS3 = "$ProjectDir\app\static\mock_s3"
if (Test-Path $mockS3) {
    Write-Output "Clearing local file submissions..."
    Remove-Item -Path $mockS3 -Recurse -Force -ErrorAction SilentlyContinue
}

# 4. Clear Logs
Write-Output "Clearing logs..."
$logDirs = @("$ProjectDir\logs", "$ProjectDir\nginx-1.30.0\logs")
foreach ($dir in $logDirs) {
    if (Test-Path $dir) {
        Get-ChildItem -Path $dir -Filter "*.log" | Remove-Item -Force
    }
}

# 5. Clear temporary venv backups
Write-Output "Clearing venv backups..."
Get-ChildItem -Path $ProjectDir -Filter "venv_old_*" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

Write-Output "--- Factory Reset Complete! ---"
Write-Output "Run run.bat to start fresh."
