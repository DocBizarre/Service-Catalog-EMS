"""
Module d'envoi d'emails.

Actuellement en mode DRY-RUN : affiche les emails dans la console serveur
au lieu de les envoyer réellement. Pour passer en SMTP réel, remplacez
le corps de `send_email` par une implémentation smtplib.
"""
import sys

FRONTEND_BASE_URL = "http://127.0.0.1:8000"  # À ajuster selon le déploiement

def send_email(to: str, subject: str, body: str) -> None:
    print("\n" + "=" * 60, file=sys.stderr)
    print(f"[MAIL DRY-RUN]  À : {to}", file=sys.stderr)
    print(f"              Sujet : {subject}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)
    print(body, file=sys.stderr)
    print("=" * 60 + "\n", file=sys.stderr)

def send_password_reset_email(to: str, username: str, token: str) -> None:
    reset_link = f"{FRONTEND_BASE_URL}/?reset_token={token}"
    body = (
        f"Bonjour {username},\n\n"
        f"Vous avez demandé une réinitialisation de votre mot de passe sur le Service Catalog EMS.\n\n"
        f"Cliquez sur ce lien (valable 1 heure) :\n"
        f"{reset_link}\n\n"
        f"Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n\n"
        f"— Service Catalog EMS"
    )
    send_email(to, "Réinitialisation de votre mot de passe", body)
