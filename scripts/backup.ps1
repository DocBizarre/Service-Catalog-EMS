# Sauvegarde quotidienne du Service Catalog EMS - Version Windows
#
# À planifier via le Planificateur de tâches Windows :
#   - Déclencheur : quotidien à 03:00
#   - Action : powershell.exe -ExecutionPolicy Bypass -File C:\catalog\scripts\backup.ps1
#   - Exécuter avec les privilèges les plus élevés

$ErrorActionPreference = "Stop"

# ============ CONFIGURATION ============
$AppDir = "C:\catalog\backend"
$BackupRoot = "D:\backups\catalog"
$RetentionDays = 30
$LogFile = "C:\catalog\logs\backup.log"
# ========================================

$Date = Get-Date -Format "yyyy-MM-dd_HHmmss"
$Dest = Join-Path $BackupRoot $Date

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

# Créer les dossiers si absents
New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) | Out-Null
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

Write-Log "=== Début sauvegarde ==="

if (-not (Test-Path "$AppDir\catalog.db")) {
    Write-Log "ERREUR : $AppDir\catalog.db introuvable"
    exit 1
}

New-Item -ItemType Directory -Force -Path $Dest | Out-Null

# Copie de la DB
Write-Log "Sauvegarde DB"
Copy-Item "$AppDir\catalog.db" "$Dest\catalog.db"

# Copie des uploads
if (Test-Path "$AppDir\uploads_storage") {
    Write-Log "Sauvegarde uploads_storage\"
    Copy-Item -Recurse "$AppDir\uploads_storage" "$Dest\uploads_storage"
} else {
    Write-Log "uploads_storage absent, ignoré"
}

# Compression
$Archive = "$BackupRoot\$Date.zip"
Compress-Archive -Path "$Dest\*" -DestinationPath $Archive
Remove-Item -Recurse -Force $Dest
Write-Log "Archive créée : $Archive"

# Purge
Write-Log "Purge des sauvegardes > $RetentionDays jours"
Get-ChildItem $BackupRoot -Filter "*.zip" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$RetentionDays) } |
    Remove-Item -Force

$Size = (Get-Item $Archive).Length / 1MB
Write-Log ("=== Sauvegarde terminée ({0:N2} Mo) ===" -f $Size)
