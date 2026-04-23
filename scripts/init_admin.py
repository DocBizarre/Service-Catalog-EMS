"""
Création du premier utilisateur admin.

À lancer UNE SEULE FOIS après la première installation du serveur.
Génère un mot de passe aléatoire qui sera affiché une seule fois :
le noter dans un gestionnaire de mots de passe.

Si un user 'admin' existe déjà, le script ne fait rien (pas de doublon).

LINUX :
    cd /opt/catalog/backend
    source venv/bin/activate
    python scripts/init_admin.py

WINDOWS :
    cd C:\\catalog\\backend
    .\\venv\\Scripts\\Activate.ps1
    python scripts\\init_admin.py
"""
import sys
import os
import secrets
import string

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models as m
import auth


def generate_password(length: int = 14) -> str:
    alphabet = "".join(c for c in string.ascii_letters + string.digits if c not in "Oo0Il1")
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isalpha() for c in pwd) and any(c.isdigit() for c in pwd):
            return pwd


def init_admin():
    db = SessionLocal()
    try:
        existing = db.query(m.User).filter(m.User.username == "admin").first()
        if existing:
            print("L'utilisateur 'admin' existe déjà. Script ignoré.")
            print("Pour réinitialiser son mot de passe, utilisez scripts/reset_admin.py")
            return

        # Vérifier que le rôle 'admin' existe
        if not db.query(m.Role).filter(m.Role.name == "admin").first():
            db.add(m.Role(name="admin", is_system=True))
            db.commit()

        password = generate_password()
        admin = m.User(
            username="admin",
            email="admin@ems.local",
            password=auth.hash_password(password),
            role="admin",
            must_change_password=True,
        )
        db.add(admin)
        db.commit()

        print("=" * 60)
        print("Utilisateur 'admin' créé avec succès")
        print("=" * 60)
        print(f"  Identifiant : admin")
        print(f"  Email       : admin@ems.local  (à modifier au premier login)")
        print(f"  Mot de passe: {password}")
        print("=" * 60)
        print("⚠ NOTEZ CE MOT DE PASSE, il ne sera plus jamais affiché.")
        print("  Vous devrez le changer à la première connexion.")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    init_admin()
