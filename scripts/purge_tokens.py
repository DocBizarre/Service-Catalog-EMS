"""
Purge des tokens de reset de mot de passe expirés ou déjà utilisés.

À lancer 1 fois par semaine via cron (Linux) ou Planificateur de tâches (Windows).

LINUX (crontab -e) :
    0 3 * * 0 cd /opt/catalog/backend && /opt/catalog/venv/bin/python scripts/purge_tokens.py

WINDOWS (Planificateur de tâches) :
    Programme : C:\\catalog\\backend\\venv\\Scripts\\python.exe
    Arguments : C:\\catalog\\backend\\scripts\\purge_tokens.py
    Démarrer dans : C:\\catalog\\backend
"""
import sys
import os
from datetime import datetime, timedelta

# Ajouter le dossier parent au PYTHONPATH pour pouvoir importer depuis backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models as m


def purge_tokens():
    """
    Supprime :
    - Les tokens utilisés depuis plus de 7 jours
    - Les tokens expirés depuis plus de 7 jours
    """
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)

        # Tokens utilisés il y a plus de 7 jours
        used_old = db.query(m.PasswordResetToken).filter(
            m.PasswordResetToken.used == True,
            m.PasswordResetToken.created_at < cutoff,
        ).count()

        # Tokens expirés il y a plus de 7 jours
        expired_old = db.query(m.PasswordResetToken).filter(
            m.PasswordResetToken.used == False,
            m.PasswordResetToken.expires_at < cutoff,
        ).count()

        total = used_old + expired_old

        if total == 0:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Aucun token à purger.")
            return

        db.query(m.PasswordResetToken).filter(
            (m.PasswordResetToken.used == True) & (m.PasswordResetToken.created_at < cutoff)
        ).delete(synchronize_session=False)

        db.query(m.PasswordResetToken).filter(
            (m.PasswordResetToken.used == False) & (m.PasswordResetToken.expires_at < cutoff)
        ).delete(synchronize_session=False)

        db.commit()
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Purgé {total} tokens "
              f"({used_old} utilisés + {expired_old} expirés)")
    finally:
        db.close()


if __name__ == "__main__":
    purge_tokens()
