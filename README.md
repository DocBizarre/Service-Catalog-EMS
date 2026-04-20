# Service Catalog EMS

Portail web interne pour centraliser l'accès aux applications de l'entreprise. Chaque utilisateur se connecte et voit les apps auxquelles son rôle lui donne droit, avec ses favoris épinglés.

## Fonctionnalités

**Authentification et sécurité**
- Connexion par cookie sécurisé (JWT signé, httponly)
- Mots de passe hashés avec bcrypt
- Forçage du changement de mot de passe à la première connexion
- Réinitialisation du mot de passe par l'admin ou via lien email (valable 1h)
- Protection du super-admin (compte `admin` non supprimable, rôle verrouillé)

**Gestion du catalogue**
- Ajout, modification, suppression d'applications
- Upload de logos personnalisés (PNG, JPG, SVG, WebP, max 2 Mo)
- Tags et filtrage
- Système de favoris par utilisateur

**Administration**
- Gestion dynamique des rôles (création, suppression, attribution)
- Matrice de permissions par rôle et par application
- Création et suppression d'utilisateurs depuis l'interface
- Génération automatique de mots de passe initiaux
- Recherche et filtre des utilisateurs (par texte, par rôle)
- Journal d'audit complet avec usernames et détails de chaque action

## Structure du projet

```
projet/
├── backend/
│   ├── main.py                 # Point d'entrée FastAPI, auth, migrations
│   ├── auth.py                 # Hash bcrypt, JWT
│   ├── database.py             # SQLAlchemy setup
│   ├── models.py               # Modèles ORM
│   ├── dependencies.py         # get_current_user, require_admin
│   ├── mailer.py               # Envoi email (dry-run console par défaut)
│   ├── requirements.txt
│   ├── catalog.db              # Base SQLite (ignorée par Git)
│   ├── uploads_storage/logos/  # Logos uploadés (ignorés par Git)
│   └── routers/
│       ├── apps.py             # /api/favorites
│       └── admin.py            # /api/admin/*
└── frontend/
    └── index.html              # Application monopage (pas de build)
```

## Prérequis

- Python 3.11 ou supérieur
- pip

## Installation

```bash
cd backend
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Linux / Mac
source venv/bin/activate

pip install -r requirements.txt
```

## Lancement en développement

```bash
cd backend
uvicorn main:app --reload
```

Le serveur démarre sur http://127.0.0.1:8000.

Ouvrir `frontend/index.html` dans le navigateur (via Live Server VSCode ou directement), ou accéder à http://127.0.0.1:8000 si le frontend est servi par FastAPI.

## Premier démarrage

Créer l'utilisateur administrateur initial (une seule fois, avec le venv actif) :

```bash
python -c "
from database import SessionLocal
import models as m, auth
db = SessionLocal()
if not db.query(m.User).filter(m.User.username == 'admin').first():
    db.add(m.User(
        username='admin',
        email='admin@ems.fr',
        password=auth.hash_password('changeme123'),
        role='admin',
        must_change_password=True,
    ))
    db.commit()
    print('Admin créé : login=admin / mdp=changeme123')
db.close()
"
```

Se connecter avec `admin` / `changeme123`. Le système imposera automatiquement le changement de mot de passe à la première connexion.

## Rôles

Trois rôles système sont créés automatiquement au démarrage :

- `admin` : accès complet à l'administration, protégé (non supprimable)
- `manager` : rôle intermédiaire, modifiable
- `collab` : rôle de base, modifiable

Des rôles personnalisés peuvent être créés depuis l'interface admin (onglet Administration, section Rôles).

## Migrations automatiques

Le serveur effectue au démarrage les migrations nécessaires sur la base SQLite si elle provient d'une version antérieure :
- Ajout de la colonne `must_change_password` sur `users` si absente
- Ajout de la colonne `email` sur `users` si absente
- Suppression des anciennes contraintes `CHECK` sur `role` qui limitaient aux rôles historiques

Ces migrations sont idempotentes : lancer le serveur plusieurs fois ne pose aucun problème.

## Configuration email

Par défaut, `mailer.py` fonctionne en mode **dry-run** : les emails (reset de mot de passe notamment) sont affichés dans la console du serveur au lieu d'être envoyés. Utile pour tester en local.

Pour passer en SMTP réel en production, modifier la fonction `send_email` dans `mailer.py` avec la configuration SMTP EMS (smtplib, adresse du relais, credentials).

## Endpoints API principaux

Authentification :
- `POST /api/login` — connexion
- `POST /api/logout` — déconnexion
- `GET /api/me` — profil de l'utilisateur connecté
- `POST /api/change-password` — changer son mot de passe
- `POST /api/forgot-password` — demander un lien de reset par email
- `POST /api/reset-password` — consommer un token de reset

Catalogue utilisateur :
- `GET /api/apps` — apps accessibles selon le rôle
- `GET /api/favorites` — liste des favoris
- `POST /api/favorites/{id}` — ajouter un favori
- `DELETE /api/favorites/{id}` — retirer un favori

Administration (tous les endpoints `/api/admin/*` sont protégés par le rôle admin) :
- Apps : `GET`, `POST`, `PUT`, `DELETE /api/admin/apps`, `POST /api/admin/apps/{id}/logo`
- Rôles : `GET`, `POST`, `DELETE /api/admin/roles`
- Utilisateurs : `GET`, `POST`, `DELETE /api/admin/users`, `PUT /api/admin/users/{id}/role`, `PUT /api/admin/users/{id}/email`, `POST /api/admin/users/{id}/reset-password`
- Permissions : `GET`, `POST`, `DELETE /api/admin/permissions`
- Audit : `GET /api/admin/audit`

La documentation interactive Swagger est disponible sur http://127.0.0.1:8000/docs quand le serveur tourne.

## Mise en production

Points à adapter avant un déploiement sur serveur interne :

- Extraire `SECRET_KEY` de `auth.py` vers une variable d'environnement
- Passer `secure=True` sur le cookie dans `main.py` (requiert HTTPS)
- Restreindre `allow_origins` à l'URL de production uniquement
- Remplacer le dry-run de `mailer.py` par une vraie configuration SMTP
- Mettre en place des sauvegardes quotidiennes de `catalog.db` et `uploads_storage/`
- Déployer derrière un reverse proxy (nginx) avec un certificat TLS
- Utiliser systemd pour relancer le service en cas de crash

## Stack technique

- Python 3.11+
- FastAPI 0.136
- SQLAlchemy 2.0
- SQLite
- bcrypt (hash des mots de passe)
- python-jose (JWT)
- HTML / CSS / JavaScript vanille, sans build
