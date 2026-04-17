# --- 🛡️ Automated Database Backup Script ---
$ProjectDir = "C:\Users\berka\Downloads\berkant.app"
$BackupDir = "$ProjectDir\backups"
$DbFile = "$ProjectDir\proglem.db"

# 1. Create backup directory if missing
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force
}

# 2. Generate Timestamped Filename
$Timestamp = Get-Date -Format "yyyyMMdd_HHmm"
$TargetFile = "$BackupDir\proglem_$Timestamp.db"

# 3. Perform the Backup
if (Test-Path $DbFile) {
    Write-Output "Backing up database to: $TargetFile..."
    Copy-Item -Path $DbFile -Destination $TargetFile -Force
    
    # 4. Cleanup old backups (Keep last 30 days)
    Get-ChildItem -Path $BackupDir -Filter "proglem_*.db" | 
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | 
        Remove-Item -Force
        
    Write-Output "✅ Backup Complete!"
} else {
    Write-Output "❌ Error: Database file not found at $DbFile. No backup performed."
}
