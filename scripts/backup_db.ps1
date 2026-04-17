# backup_db.ps1
# Automated Database Backup Script

$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$BackupDir = "$ProjectDir\backups"
$DbFile = "$ProjectDir\proglem.db"

if (Test-Path $DbFile) {
    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir | Out-Null
    }
    
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $BackupFile = "$BackupDir\proglem_backup_$Timestamp.db"
    
    Copy-Item -Path $DbFile -Destination $BackupFile -Force
    
    # Keep only last 30 days of backups
    Get-ChildItem -Path $BackupDir | 
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | 
        Remove-Item -Force
        
    Write-Output "Backup Complete!"
} else {
    Write-Output "Error: Database file not found at $DbFile. No backup performed."
}
