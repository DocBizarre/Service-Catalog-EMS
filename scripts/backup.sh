#!/bin/bash
#
# Sauvegarde quotidienne du Service Catalog EMS
# À placer dans /etc/cron.daily/backup-catalog et rendre exécutable :
#   sudo chmod +x /etc/cron.daily/backup-catalog
#
# Sauvegarde :
#   - La base SQLite (catalog.db)
#   - Le dossier uploads_storage/ (logos uploadés)
#
# Rétention : 30 jours (configurable ci-dessous)

set -euo pipefail

# ============ CONFIGURATION ============
APP_DIR="/opt/catalog/backend"
BACKUP_ROOT="/mnt/backups/catalog"
RETENTION_DAYS=30
LOGFILE="/var/log/catalog-backup.log"
# ========================================

DATE=$(date +%Y-%m-%d_%H%M%S)
DEST="$BACKUP_ROOT/$DATE"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"
}

log "=== Début sauvegarde ==="

# Vérifications préalables
if [[ ! -f "$APP_DIR/catalog.db" ]]; then
    log "ERREUR : $APP_DIR/catalog.db introuvable"
    exit 1
fi

mkdir -p "$DEST"

# Sauvegarde de la base SQLite via l'API .backup de sqlite3
# (plus sûr qu'un simple cp qui pourrait attraper une écriture en cours)
if command -v sqlite3 &> /dev/null; then
    log "Sauvegarde DB via sqlite3 .backup"
    sqlite3 "$APP_DIR/catalog.db" ".backup '$DEST/catalog.db'"
else
    log "sqlite3 non disponible, utilisation de cp (moins sûr)"
    cp "$APP_DIR/catalog.db" "$DEST/catalog.db"
fi

# Sauvegarde des logos uploadés
if [[ -d "$APP_DIR/uploads_storage" ]]; then
    log "Sauvegarde uploads_storage/"
    rsync -a "$APP_DIR/uploads_storage/" "$DEST/uploads_storage/"
else
    log "uploads_storage/ absent, ignoré"
fi

# Créer une archive compressée (optionnel mais pratique)
cd "$BACKUP_ROOT"
tar czf "$DATE.tar.gz" "$DATE"
rm -rf "$DATE"
log "Archive créée : $DATE.tar.gz"

# Purge des anciennes sauvegardes
log "Purge des sauvegardes > $RETENTION_DAYS jours"
find "$BACKUP_ROOT" -maxdepth 1 -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

SIZE=$(du -h "$BACKUP_ROOT/$DATE.tar.gz" | cut -f1)
log "=== Sauvegarde terminée ($SIZE) ==="
