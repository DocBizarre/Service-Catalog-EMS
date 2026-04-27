# Charger les variables d'environnement depuis .env (si présent)
# DOIT être fait avant l'import des modules applicatifs (auth, etc.)
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timedelta
import models, auth, mailer
from database import engine, get_db, SessionLocal
import models as m
from dependencies import get_current_user
from routers import apps as apps_router
from routers import admin as admin_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os, secrets

models.Base.metadata.create_all(bind=engine)

# -- Migrations légères
def migrate_users_table():
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()]
        if "must_change_password" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()
        if "email" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN email TEXT"))
            conn.commit()
            conn.execute(text(
                "UPDATE users SET email = username || '@placeholder.local' WHERE email IS NULL"
            ))
            conn.commit()

        # Supprimer l'ancienne contrainte CHECK sur users.role si présente
        row = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
        )).fetchone()
        if row and row[0] and "check" in row[0].lower() and "role in" in row[0].lower():
            print("[MIGRATION] Suppression de l'ancienne contrainte CHECK sur users.role")
            conn.execute(text("""
                CREATE TABLE users_new (
                    id INTEGER NOT NULL,
                    username VARCHAR NOT NULL,
                    email VARCHAR,
                    password VARCHAR NOT NULL,
                    role VARCHAR NOT NULL,
                    must_change_password BOOLEAN DEFAULT 0 NOT NULL,
                    created_at DATETIME,
                    PRIMARY KEY (id),
                    UNIQUE (username)
                )
            """))
            conn.execute(text("""
                INSERT INTO users_new (id, username, email, password, role, must_change_password, created_at)
                SELECT id, username, email, password, role,
                       COALESCE(must_change_password, 0), created_at
                FROM users
            """))
            conn.execute(text("DROP TABLE users"))
            conn.execute(text("ALTER TABLE users_new RENAME TO users"))
            conn.commit()
            print("[MIGRATION] Table users migrée avec succès")

def migrate_permissions_table():
    """
    Supprime l'ancienne contrainte CHECK qui limitait les rôles à (admin, manager, collab).
    SQLite ne permet pas DROP CONSTRAINT : on recrée la table.
    """
    with engine.connect() as conn:
        # Récupérer le SQL de création actuel
        row = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='permissions'"
        )).fetchone()
        if not row or not row[0]:
            return
        ddl = row[0].lower()
        # Si la contrainte CHECK sur role IN (...) est présente, on migre
        if "check" in ddl and "role in" in ddl:
            print("[MIGRATION] Suppression de l'ancienne contrainte CHECK sur permissions.role")
            conn.execute(text("""
                CREATE TABLE permissions_new (
                    id INTEGER NOT NULL,
                    app_id INTEGER,
                    role VARCHAR NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(app_id) REFERENCES apps (id) ON DELETE CASCADE
                )
            """))
            conn.execute(text("INSERT INTO permissions_new SELECT id, app_id, role FROM permissions"))
            conn.execute(text("DROP TABLE permissions"))
            conn.execute(text("ALTER TABLE permissions_new RENAME TO permissions"))
            conn.commit()
            print("[MIGRATION] Table permissions migrée avec succès")

def migrate_announcements_table():
    """Ajouter les colonnes image/category/featured/breaking si absentes."""
    with engine.connect() as conn:
        # La table peut ne pas encore exister (sera créée par create_all juste après)
        tables = [t[0] for t in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='announcements'"
        )).fetchall()]
        if not tables:
            return
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(announcements)")).fetchall()]
        if "image" not in cols:
            conn.execute(text("ALTER TABLE announcements ADD COLUMN image TEXT"))
            conn.commit()
        if "category" not in cols:
            conn.execute(text("ALTER TABLE announcements ADD COLUMN category TEXT"))
            conn.commit()
        if "featured" not in cols:
            conn.execute(text("ALTER TABLE announcements ADD COLUMN featured BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()
        if "breaking" not in cols:
            conn.execute(text("ALTER TABLE announcements ADD COLUMN breaking BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()

migrate_users_table()
migrate_permissions_table()
migrate_announcements_table()

def seed_roles():
    db = SessionLocal()
    try:
        defaults = [("admin", True), ("manager", False), ("collab", False)]
        for name, is_system in defaults:
            if not db.query(m.Role).filter(m.Role.name == name).first():
                db.add(m.Role(name=name, is_system=is_system))
        used = {u.role for u in db.query(m.User).all() if u.role}
        for name in used:
            if not db.query(m.Role).filter(m.Role.name == name).first():
                db.add(m.Role(name=name, is_system=False))
        db.commit()
    finally:
        db.close()

seed_roles()

# -- Dossier pour stocker les logos uploadés
LOGOS_DIR = os.path.join(os.path.dirname(__file__), "uploads_storage", "logos")
os.makedirs(LOGOS_DIR, exist_ok=True)

app = FastAPI(title="Service Catalog EMS")

# Origines CORS : liste par défaut pour le dev local, override en prod via env
default_origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]
env_origins = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in env_origins.split(",") if o.strip()] or default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir les logos uploadés à l'URL /logos/*
app.mount("/logos", StaticFiles(directory=LOGOS_DIR), name="logos")

# Logo de la société
COMPANY_LOGOS_DIR = os.path.join(os.path.dirname(__file__), "uploads_storage", "company")
os.makedirs(COMPANY_LOGOS_DIR, exist_ok=True)
app.mount("/company-logo", StaticFiles(directory=COMPANY_LOGOS_DIR), name="company-logo")

# Images d'annonces
ANNOUNCEMENTS_DIR = os.path.join(os.path.dirname(__file__), "uploads_storage", "announcements")
os.makedirs(ANNOUNCEMENTS_DIR, exist_ok=True)
app.mount("/announcement-images", StaticFiles(directory=ANNOUNCEMENTS_DIR), name="announcement-images")

from routers import home as home_router
app.include_router(apps_router.router)
app.include_router(admin_router.router)
app.include_router(home_router.router)

class ChangePasswordBody(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)

class ForgotPasswordBody(BaseModel):
    email: EmailStr

class ResetPasswordBody(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

# -- Endpoint de health check (pour le monitoring)
@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    """
    Vérifie que l'app et la DB répondent.
    Utilisé par les outils de monitoring (Zabbix, Centreon, PRTG, uptime-kuma, etc.).
    Retourne 200 si tout va bien, 503 si la DB est inaccessible.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {e}")

@app.post("/api/login")
def login(response: Response, username: str, password: str, db: Session = Depends(get_db)):
    user = auth.authenticate_user(db, username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    token = auth.create_token({"user_id": user.id, "role": user.role})
    # COOKIE_SECURE=true en production HTTPS, false en dev HTTP local
    cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(
        "token", token, httponly=True, max_age=28800,
        samesite="lax", secure=cookie_secure, path="/",
    )
    db.add(m.AuditLog(
        user_id=user.id, action="login",
        detail=f"Connexion de {user.username} (rôle={user.role})"
    ))
    db.commit()
    return {
        "username": user.username,
        "role": user.role,
        "must_change_password": user.must_change_password,
    }

@app.post("/api/logout")
def logout(response: Response, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    db.add(m.AuditLog(
        user_id=current_user.id, action="logout",
        detail=f"Déconnexion de {current_user.username}"
    ))
    db.commit()
    response.delete_cookie("token", path="/")
    return {"message": "Déconnecté"}

@app.get("/api/me")
def me(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "must_change_password": current_user.must_change_password,
    }

@app.post("/api/change-password")
def change_password(
    body: ChangePasswordBody,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.password = auth.hash_password(body.new_password)
    current_user.must_change_password = False
    db.add(m.AuditLog(
        user_id=current_user.id, action="change_password",
        detail=f"{current_user.username} a changé son mot de passe"
    ))
    db.commit()
    return {"message": "Mot de passe mis à jour"}

@app.post("/api/forgot-password")
def forgot_password(body: ForgotPasswordBody, db: Session = Depends(get_db)):
    user = db.query(m.User).filter(m.User.email == body.email).first()
    if user:
        db.query(m.PasswordResetToken).filter(
            m.PasswordResetToken.user_id == user.id,
            m.PasswordResetToken.used == False
        ).update({"used": True})
        token_value = secrets.token_urlsafe(32)
        token = m.PasswordResetToken(
            user_id=user.id, token=token_value,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.add(token)
        db.add(m.AuditLog(
            user_id=user.id, action="forgot_password",
            detail=f"Demande de reset via {body.email}"
        ))
        db.commit()
        mailer.send_password_reset_email(user.email, user.username, token_value)
    return {"message": "Si cet email est enregistré, un lien de réinitialisation a été envoyé."}

@app.post("/api/reset-password")
def reset_password(body: ResetPasswordBody, db: Session = Depends(get_db)):
    token = db.query(m.PasswordResetToken).filter(
        m.PasswordResetToken.token == body.token
    ).first()
    if not token:
        raise HTTPException(status_code=400, detail="Lien invalide")
    if token.used:
        raise HTTPException(status_code=400, detail="Ce lien a déjà été utilisé")
    if token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Ce lien a expiré")
    user = db.query(m.User).filter(m.User.id == token.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Utilisateur introuvable")
    user.password = auth.hash_password(body.new_password)
    user.must_change_password = False
    token.used = True
    db.add(m.AuditLog(
        user_id=user.id, action="reset_password",
        detail=f"{user.username} a réinitialisé son mot de passe via email"
    ))
    db.commit()
    return {"message": "Mot de passe réinitialisé"}

@app.get("/api/apps")
def get_apps(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    permitted_ids = [
        p.app_id for p in db.query(m.Permission)
        .filter(m.Permission.role == current_user.role).all()
    ]
    apps = db.query(m.App).filter(m.App.id.in_(permitted_ids)).all()
    fav_ids = {
        f.app_id for f in db.query(m.Favorite)
        .filter(m.Favorite.user_id == current_user.id).all()
    }
    return [
        {
            "id": a.id, "name": a.name, "url": a.url,
            "icon": a.icon, "tag": a.tag, "online": a.online,
            "favorite": a.id in fav_ids
        }
        for a in apps
    ]

# Frontend
frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(frontend_path, 'index.html'))
