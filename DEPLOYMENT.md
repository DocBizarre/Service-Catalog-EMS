    # Guide de déploiement — Service Catalog EMS

Document destiné à l'équipe IT pour la mise en production du portail.

## Sommaire

1. [Architecture cible](#architecture-cible)
2. [Prérequis serveur](#prérequis-serveur)
3. [Installation (Linux)](#installation-linux)
4. [Installation (Windows Server)](#installation-windows-server)
5. [Configuration HTTPS](#configuration-https)
6. [Sauvegardes](#sauvegardes)
7. [Monitoring](#monitoring)
8. [Tâches planifiées](#tâches-planifiées)
9. [Migration depuis le poste de développement](#migration-depuis-le-poste-de-développement)
10. [Exploitation courante](#exploitation-courante)

---

## Architecture cible

```
┌──────────────┐         HTTPS        ┌─────────────────────────────┐
│ Navigateurs  │ ◄──────────────────► │  Serveur interne EMS        │
│ utilisateurs │                      │                             │
└──────────────┘                      │  nginx (443)                │
                                      │    │                        │
                                      │    ▼ proxy 127.0.0.1:8000   │
                                      │  uvicorn + FastAPI          │
                                      │    │                        │
                                      │    ▼                        │
                                      │  SQLite (catalog.db)        │
                                      │  uploads_storage/logos/     │
                                      └─────────────────────────────┘
                                              │
                                              ▼
                                      ┌─────────────────────────────┐
                                      │ NAS / système de backup EMS │
                                      │  (snapshots quotidiens)     │
                                      └─────────────────────────────┘
```

Composants :
- **nginx** : reverse proxy, termine le TLS, sert les fichiers statiques
- **uvicorn** : serveur ASGI qui fait tourner FastAPI
- **systemd** (Linux) ou **Service Windows** : supervise uvicorn et le redémarre en cas de crash
- **SQLite** : base de données intégrée à l'app, fichier unique `catalog.db`

## Prérequis serveur

| Ressource | Minimum | Recommandé |
|-----------|---------|------------|
| RAM       | 1 Go    | 2 Go       |
| vCPU      | 1       | 2          |
| Disque    | 5 Go    | 20 Go (pour backups locaux et croissance logos) |
| OS        | Debian/Ubuntu LTS ou Windows Server 2019+ | |
| Réseau    | IP fixe, accès HTTP(S) sortant pour les emails | |

Logiciels :
- Python 3.11 ou supérieur
- nginx (Linux) ou IIS (Windows, en reverse proxy)
- Accès au serveur SMTP interne de EMS

## Installation (Linux)

### 1. Préparer l'environnement

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx sqlite3 git

# Créer un user dédié (ne jamais faire tourner en root)
sudo useradd -r -s /bin/false -d /opt/catalog catalog
sudo mkdir -p /opt/catalog /mnt/backups/catalog
sudo chown -R catalog:catalog /opt/catalog
```

### 2. Déployer le code

```bash
sudo -u catalog bash
cd /opt/catalog
git clone <URL_DU_REPO> .
python3 -m venv venv
source venv/bin/activate
cd backend
pip install -r requirements.txt
exit
```

### 3. Créer le premier admin

```bash
cd /opt/catalog/backend
sudo -u catalog ../venv/bin/python scripts/init_admin.py
```

**Noter le mot de passe affiché**, il ne sera plus jamais visible.

### 4. Configurer uvicorn en service systemd

Créer `/etc/systemd/system/catalog.service` :

```ini
[Unit]
Description=Service Catalog EMS
After=network.target

[Service]
User=catalog
Group=catalog
WorkingDirectory=/opt/catalog/backend
ExecStart=/opt/catalog/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/var/log/catalog.log
StandardError=append:/var/log/catalog.log

[Install]
WantedBy=multi-user.target
```

```bash
sudo touch /var/log/catalog.log
sudo chown catalog:catalog /var/log/catalog.log
sudo systemctl daemon-reload
sudo systemctl enable catalog
sudo systemctl start catalog
sudo systemctl status catalog
```

### 5. Configurer nginx

Créer `/etc/nginx/sites-available/catalog` :

```nginx
server {
    listen 80;
    server_name catalog.ems.local;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name catalog.ems.local;

    ssl_certificate     /etc/ssl/certs/catalog.ems.local.crt;
    ssl_certificate_key /etc/ssl/private/catalog.ems.local.key;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # Upload de logos jusqu'à 2 Mo, on met 5 pour la marge
    client_max_body_size 5M;

    access_log /var/log/nginx/catalog-access.log;
    error_log  /var/log/nginx/catalog-error.log;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/catalog /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. Ouvrir le pare-feu

```bash
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp
```

## Installation (Windows Server)

Les grandes étapes équivalentes :

1. Installer Python 3.11+ pour tous les utilisateurs
2. Déployer le code dans `C:\catalog\`
3. Créer le venv et installer les dépendances
4. Lancer `python scripts\init_admin.py`
5. Installer **NSSM** (Non-Sucking Service Manager) et l'utiliser pour créer un service Windows qui lance uvicorn
6. Configurer IIS avec le module **URL Rewrite** + **Application Request Routing** comme reverse proxy vers `127.0.0.1:8000`
7. Binder le certificat TLS sur le site IIS

NSSM (plus simple que d'écrire un service Windows natif) :
```powershell
nssm install catalog "C:\catalog\venv\Scripts\uvicorn.exe"
nssm set catalog AppParameters "main:app --host 127.0.0.1 --port 8000"
nssm set catalog AppDirectory "C:\catalog\backend"
nssm start catalog
```

## Configuration HTTPS

Trois options selon l'infrastructure EMS :

1. **PKI interne EMS** (recommandé) : demander un certificat pour le nom DNS choisi à l'équipe sécurité / PKI. Idéalement valide plusieurs années.

2. **Certificat auto-signé** (uniquement pour validation initiale) : génère un warning dans tous les navigateurs, pas acceptable en production mais utile pour tester la chaîne.

3. **Let's Encrypt** : nécessite que le serveur soit exposé à Internet pour le challenge ACME, rarement faisable en intranet pur.

## Sauvegardes

Deux chemins à sauvegarder impérativement :
- `/opt/catalog/backend/catalog.db` — la base
- `/opt/catalog/backend/uploads_storage/` — les logos uploadés

**Option A — Intégrer dans le backup existant de EMS**
Si EMS a déjà un système qui sauvegarde le serveur (Veeam, Bacula, snapshots VMware, rsync vers NAS), ajouter simplement ces deux chemins aux règles existantes. **C'est la solution recommandée.**

**Option B — Script autonome**
Utiliser `scripts/backup.sh` (Linux) ou `scripts/backup.ps1` (Windows) fournis dans le repo.

Installation Linux :
```bash
sudo cp /opt/catalog/scripts/backup.sh /etc/cron.daily/backup-catalog
sudo chmod +x /etc/cron.daily/backup-catalog
sudo /etc/cron.daily/backup-catalog  # tester
```

Le script utilise `sqlite3 .backup` pour une copie cohérente de la base (même en cas d'écritures concurrentes), compresse en `.tar.gz`, et purge automatiquement les archives > 30 jours.

**Test de restauration** : faire un test de restauration au moins une fois avant la mise en prod, puis tous les 6 mois. Une sauvegarde jamais testée est une sauvegarde qui n'existe pas.

## Monitoring

Endpoint à surveiller : `GET https://catalog.ems.local/api/health`

- Retourne `200 {"status": "ok", "database": "ok"}` si tout va bien
- Retourne `503` si la base est inaccessible
- Toute autre erreur (timeout, 500, connection refused) = service en panne

Fréquence suggérée : toutes les 1 à 5 minutes selon l'outil de monitoring utilisé chez EMS (Zabbix, Centreon, PRTG, uptime-kuma, etc.).

Alertes à configurer :
- Health check échoué 3 fois consécutives → alerter l'admin
- Usage disque > 80 % sur la partition du serveur
- Logs nginx 5xx > 10/min

## Tâches planifiées

Trois tâches à programmer :

| Fréquence   | Script                    | Rôle                                  |
|-------------|---------------------------|---------------------------------------|
| Quotidien   | `backup.sh`               | Sauvegarde DB + logos                 |
| Hebdo       | `purge_tokens.py`         | Nettoie les tokens de reset expirés   |
| Mensuel     | `purge_audit.py`          | Nettoie les logs d'audit > 6 mois (RGPD) |

Exemples de crontab Linux (à éditer avec `sudo crontab -u catalog -e`) :

```cron
# Sauvegarde quotidienne à 03:00 (déjà fait via /etc/cron.daily/ si backup.sh y est)
# 0 3 * * * /opt/catalog/scripts/backup.sh

# Purge tokens le dimanche à 03:30
30 3 * * 0 cd /opt/catalog/backend && /opt/catalog/venv/bin/python scripts/purge_tokens.py

# Purge logs le 1er du mois à 04:00
0 4 1 * * cd /opt/catalog/backend && /opt/catalog/venv/bin/python scripts/purge_audit.py
```

## Migration depuis le poste de développement

Si des données ont été créées pendant la phase de développement et doivent être conservées :

```bash
# Depuis le PC de développement
scp backend/catalog.db user@serveur:/tmp/
scp -r backend/uploads_storage user@serveur:/tmp/

# Sur le serveur, arrêter l'app puis copier
sudo systemctl stop catalog
sudo cp /tmp/catalog.db /opt/catalog/backend/
sudo cp -r /tmp/uploads_storage /opt/catalog/backend/
sudo chown -R catalog:catalog /opt/catalog/backend/catalog.db /opt/catalog/backend/uploads_storage
sudo systemctl start catalog
```

Les migrations de schéma se jouent automatiquement au démarrage si la base vient d'une version antérieure.

## Exploitation courante

### Consulter les logs

```bash
# Logs applicatifs
sudo tail -f /var/log/catalog.log

# Logs nginx
sudo tail -f /var/log/nginx/catalog-access.log
sudo tail -f /var/log/nginx/catalog-error.log

# Journal systemd
sudo journalctl -u catalog -f
```

### Redémarrer le service

```bash
sudo systemctl restart catalog
```

### Mettre à jour l'application

```bash
cd /opt/catalog
sudo -u catalog git pull
sudo -u catalog venv/bin/pip install -r backend/requirements.txt
sudo systemctl restart catalog
```

### Accès à la base pour audit manuel

```bash
sudo -u catalog sqlite3 /opt/catalog/backend/catalog.db
sqlite> .tables
sqlite> SELECT username, role, created_at FROM users;
sqlite> .quit
```

### Réinitialiser le mot de passe admin en urgence

Si l'admin a perdu son mot de passe et ne peut plus se connecter :

```bash
cd /opt/catalog/backend
sudo -u catalog ../venv/bin/python -c "
from database import SessionLocal
import models as m, auth, secrets, string

alphabet = ''.join(c for c in string.ascii_letters + string.digits if c not in 'Oo0Il1')
pwd = ''.join(secrets.choice(alphabet) for _ in range(14))

db = SessionLocal()
admin = db.query(m.User).filter(m.User.username == 'admin').first()
admin.password = auth.hash_password(pwd)
admin.must_change_password = True
db.commit()
db.close()
print(f'Nouveau mot de passe admin : {pwd}')
"
```

## Contacts

- Développement initial : [ton nom], stagiaire
- Référent métier : [à compléter]
- Référent IT : [à compléter]
