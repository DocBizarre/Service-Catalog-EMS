"""
Purge des logs d'audit anciens (politique RGPD).

Par défaut : supprime les logs de plus de 6 mois.
Ajuster RETENTION_DAYS selon la politique de rétention de EMS.

À lancer 1 fois par mois via cron ou Planificateur de tâches.

LINUX (crontab -e) :
    0 4 1 * * cd /opt/catalog/backend && /opt/catalog/venv/bin/python scripts/purge_audit.py

WINDOWS (Planificateur de tâches, mensuel) :
    Programme : C:\\catalog\\backend\\venv\\Scripts\\python.exe
    Arguments : C:\\catalog\\backend\\scripts\\purge_audit.py
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models as m

# ============ CONFIGURATION ============
RETENTION_DAYS = 180  # 6 mois — ajuster selon politique EMS
# ========================================


def purge_audit():
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)

        count = db.query(m.AuditLog).filter(
            m.AuditLog.created_at < cutoff
        ).count()

        if count == 0:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Aucun log à purger "
                  f"(rétention: {RETENTION_DAYS} jours).")
            return

        db.query(m.AuditLog).filter(
            m.AuditLog.created_at < cutoff
        ).delete(synchronize_session=False)
        db.commit()

        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Purgé {count} logs d'audit "
              f"antérieurs au {cutoff:%Y-%m-%d}")
    finally:
        db.close()


if __name__ == "__main__":
    purge_audit()
