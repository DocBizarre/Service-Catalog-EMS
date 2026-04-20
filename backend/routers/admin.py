from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel, EmailStr, Field
from database import get_db
from dependencies import require_admin
from typing import Optional
import models, auth
import re, secrets, string, os, uuid

router = APIRouter(prefix="/api/admin")

# Nom réservé du super-admin (celui créé à l'install)
SUPER_ADMIN_USERNAME = "admin"

LOGOS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads_storage", "logos")
ALLOWED_LOGO_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2 Mo

# ============ SCHÉMAS ============

class AppCreate(BaseModel):
    name: str
    url: str
    icon: str = "📦"
    description: str = ""
    tag: str = "Général"

class AppUpdate(BaseModel):
    name: str = None
    url: str = None
    icon: str = None
    description: str = None
    tag: str = None
    online: int = None

class RoleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=30)

class UserRoleUpdate(BaseModel):
    role: str

class UserEmailUpdate(BaseModel):
    email: EmailStr

class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=40)
    email: EmailStr
    role: str
    password: Optional[str] = None

# ============ UTILS ============

def _generate_password(length: int = 12) -> str:
    alphabet = "".join(c for c in string.ascii_letters + string.digits if c not in "Oo0Il1")
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isalpha() for c in pwd) and any(c.isdigit() for c in pwd):
            return pwd

def _is_super_admin(user) -> bool:
    """True si c'est le user 'admin' d'origine, intouchable."""
    return user.username == SUPER_ADMIN_USERNAME

# ============ APPS ============

@router.get("/apps")
def list_all_apps(_admin=Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(models.App).all()

@router.post("/apps")
def create_app(data: AppCreate, admin=Depends(require_admin), db: Session = Depends(get_db)):
    app = models.App(**data.model_dump())
    db.add(app)
    db.flush()
    db.add(models.AuditLog(
        user_id=admin.id, action="create_app",
        detail=f"{admin.username} a créé l'app '{app.name}' (id={app.id})"
    ))
    db.commit()
    db.refresh(app)
    return app

@router.put("/apps/{app_id}")
def update_app(app_id: int, data: AppUpdate, admin=Depends(require_admin), db: Session = Depends(get_db)):
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App introuvable")
    changes = []
    for key, value in data.model_dump(exclude_none=True).items():
        if getattr(app, key) != value:
            changes.append(f"{key}={value}")
        setattr(app, key, value)
    if changes:
        db.add(models.AuditLog(
            user_id=admin.id, action="update_app",
            detail=f"{admin.username} a modifié '{app.name}' ({', '.join(changes)})"
        ))
    db.commit()
    db.refresh(app)
    return app

@router.delete("/apps/{app_id}")
def delete_app(app_id: int, admin=Depends(require_admin), db: Session = Depends(get_db)):
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App introuvable")
    # Si c'était un logo uploadé, on supprime le fichier
    if app.icon and app.icon.startswith("/logos/"):
        file_path = os.path.join(LOGOS_DIR, os.path.basename(app.icon))
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
    db.add(models.AuditLog(
        user_id=admin.id, action="delete_app",
        detail=f"{admin.username} a supprimé l'app '{app.name}' (id={app.id})"
    ))
    db.delete(app)
    db.commit()
    return {"message": "App supprimée"}

@router.post("/apps/{app_id}/logo")
async def upload_logo(
    app_id: int,
    file: UploadFile = File(...),
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App introuvable")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_LOGO_EXTS:
        raise HTTPException(status_code=400, detail=f"Extension non supportée. Autorisées : {', '.join(ALLOWED_LOGO_EXTS)}")

    # Lire tout en mémoire (on a plafonné à 2 Mo, acceptable)
    content = await file.read()
    if len(content) > MAX_LOGO_SIZE:
        raise HTTPException(status_code=400, detail="Fichier trop lourd (max 2 Mo)")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Fichier vide")

    # Supprimer l'ancien logo s'il existait
    if app.icon and app.icon.startswith("/logos/"):
        old_path = os.path.join(LOGOS_DIR, os.path.basename(app.icon))
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    # Écrire le nouveau fichier avec un nom unique
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(LOGOS_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    app.icon = f"/logos/{filename}"
    db.add(models.AuditLog(
        user_id=admin.id, action="upload_logo",
        detail=f"{admin.username} a uploadé un logo pour '{app.name}'"
    ))
    db.commit()
    return {"icon": app.icon}

# ============ ROLES ============

@router.get("/roles")
def list_roles(_admin=Depends(require_admin), db: Session = Depends(get_db)):
    roles = db.query(models.Role).order_by(models.Role.name).all()
    return [{"name": r.name, "is_system": r.is_system} for r in roles]

@router.post("/roles")
def create_role(data: RoleCreate, admin=Depends(require_admin), db: Session = Depends(get_db)):
    name = data.name.strip().lower()
    if not re.match(r"^[a-z0-9_-]+$", name):
        raise HTTPException(status_code=400, detail="Nom invalide : uniquement lettres, chiffres, tirets et underscores")
    if db.query(models.Role).filter(models.Role.name == name).first():
        raise HTTPException(status_code=400, detail="Ce rôle existe déjà")
    db.add(models.Role(name=name, is_system=False))
    db.add(models.AuditLog(
        user_id=admin.id, action="create_role",
        detail=f"{admin.username} a créé le rôle '{name}'"
    ))
    db.commit()
    return {"message": "Rôle créé", "name": name}

@router.delete("/roles/{name}")
def delete_role(name: str, admin=Depends(require_admin), db: Session = Depends(get_db)):
    role = db.query(models.Role).filter(models.Role.name == name).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rôle introuvable")
    if role.is_system:
        raise HTTPException(status_code=403, detail="Ce rôle est protégé et ne peut pas être supprimé")
    users_count = db.query(models.User).filter(models.User.role == name).count()
    if users_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Impossible : {users_count} utilisateur(s) ont encore ce rôle. Réassignez-les d'abord."
        )
    db.query(models.Permission).filter(models.Permission.role == name).delete()
    db.add(models.AuditLog(
        user_id=admin.id, action="delete_role",
        detail=f"{admin.username} a supprimé le rôle '{name}'"
    ))
    db.delete(role)
    db.commit()
    return {"message": "Rôle supprimé"}

# ============ USERS ============

@router.get("/users")
def list_users(_admin=Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return [
        {
            "id": u.id, "username": u.username, "email": u.email, "role": u.role,
            "must_change_password": u.must_change_password,
            "is_super_admin": _is_super_admin(u),
        }
        for u in users
    ]

@router.post("/users")
def create_user(data: UserCreate, admin=Depends(require_admin), db: Session = Depends(get_db)):
    username = data.username.strip()
    if not re.match(r"^[A-Za-z0-9._-]+$", username):
        raise HTTPException(status_code=400, detail="Identifiant invalide : lettres, chiffres, . _ -")
    if username.lower() == SUPER_ADMIN_USERNAME:
        raise HTTPException(status_code=400, detail=f"Le nom '{SUPER_ADMIN_USERNAME}' est réservé")
    if db.query(models.User).filter(models.User.username == username).first():
        raise HTTPException(status_code=400, detail="Cet identifiant est déjà pris")
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    if not db.query(models.Role).filter(models.Role.name == data.role).first():
        raise HTTPException(status_code=400, detail="Rôle inexistant")

    provided = (data.password or "").strip()
    if provided:
        if len(provided) < 8:
            raise HTTPException(status_code=400, detail="Le mot de passe doit faire au moins 8 caractères")
        plain_password = provided
        generated = False
    else:
        plain_password = _generate_password()
        generated = True

    user = models.User(
        username=username, email=data.email,
        password=auth.hash_password(plain_password),
        role=data.role, must_change_password=True,
    )
    db.add(user)
    db.flush()
    db.add(models.AuditLog(
        user_id=admin.id, action="create_user",
        detail=f"{admin.username} a créé l'utilisateur '{username}' (rôle={data.role}, email={data.email})",
    ))
    db.commit()
    db.refresh(user)

    return {
        "id": user.id, "username": user.username, "email": user.email, "role": user.role,
        "generated_password": plain_password if generated else None,
    }

@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin=Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if _is_super_admin(user):
        raise HTTPException(status_code=403, detail=f"L'utilisateur '{SUPER_ADMIN_USERNAME}' est protégé")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous supprimer vous-même")
    if user.role == "admin":
        other_admins = db.query(models.User).filter(
            models.User.role == "admin", models.User.id != user.id,
        ).count()
        if other_admins == 0:
            raise HTTPException(status_code=400, detail="Impossible de supprimer le dernier administrateur")
    db.add(models.AuditLog(
        user_id=admin.id, action="delete_user",
        detail=f"{admin.username} a supprimé '{user.username}'",
    ))
    db.delete(user)
    db.commit()
    return {"message": "Utilisateur supprimé"}

@router.put("/users/{user_id}/role")
def update_user_role(user_id: int, data: UserRoleUpdate, admin=Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if _is_super_admin(user):
        raise HTTPException(status_code=403, detail=f"Le rôle de '{SUPER_ADMIN_USERNAME}' est verrouillé")
    if not db.query(models.Role).filter(models.Role.name == data.role).first():
        raise HTTPException(status_code=400, detail="Rôle inexistant")
    if user.id == admin.id and user.role == "admin" and data.role != "admin":
        other_admins = db.query(models.User).filter(
            models.User.role == "admin", models.User.id != user.id,
        ).count()
        if other_admins == 0:
            raise HTTPException(status_code=400, detail="Vous êtes le dernier admin, changement refusé")
    old_role = user.role
    user.role = data.role
    db.add(models.AuditLog(
        user_id=admin.id, action="update_user_role",
        detail=f"{admin.username} a changé le rôle de '{user.username}' : {old_role} → {data.role}",
    ))
    db.commit()
    return {"message": "Rôle mis à jour", "user_id": user.id, "role": user.role}

@router.put("/users/{user_id}/email")
def update_user_email(user_id: int, data: UserEmailUpdate, admin=Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    existing = db.query(models.User).filter(
        models.User.email == data.email, models.User.id != user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    old_email = user.email
    user.email = data.email
    db.add(models.AuditLog(
        user_id=admin.id, action="update_user_email",
        detail=f"{admin.username} a modifié l'email de '{user.username}' : {old_email} → {data.email}",
    ))
    db.commit()
    return {"message": "Email mis à jour", "email": user.email}

@router.post("/users/{user_id}/reset-password")
def admin_reset_password(user_id: int, admin=Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if _is_super_admin(user) and user.id != admin.id:
        raise HTTPException(status_code=403, detail=f"Seul '{SUPER_ADMIN_USERNAME}' peut réinitialiser son propre mot de passe")
    new_password = _generate_password()
    user.password = auth.hash_password(new_password)
    user.must_change_password = True
    db.add(models.AuditLog(
        user_id=admin.id, action="admin_reset_password",
        detail=f"{admin.username} a réinitialisé le mot de passe de '{user.username}'",
    ))
    db.commit()
    return {"username": user.username, "generated_password": new_password}

# ============ PERMISSIONS ============

@router.get("/permissions")
def get_permissions(_admin=Depends(require_admin), db: Session = Depends(get_db)):
    perms = db.query(models.Permission).all()
    return [{"app_id": p.app_id, "role": p.role} for p in perms]

@router.post("/permissions")
def add_permission(app_id: int, role: str, admin=Depends(require_admin), db: Session = Depends(get_db)):
    if not db.query(models.Role).filter(models.Role.name == role).first():
        raise HTTPException(status_code=400, detail="Rôle inexistant")
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=400, detail="App inexistante")
    existing = db.query(models.Permission).filter(
        models.Permission.app_id == app_id,
        models.Permission.role == role
    ).first()
    if existing:
        return {"message": "Permission déjà existante"}
    db.add(models.Permission(app_id=app_id, role=role))
    db.add(models.AuditLog(
        user_id=admin.id, action="grant_permission",
        detail=f"{admin.username} a donné accès à '{app.name}' au rôle '{role}'"
    ))
    db.commit()
    return {"message": "Permission ajoutée"}

@router.delete("/permissions")
def remove_permission(app_id: int, role: str, admin=Depends(require_admin), db: Session = Depends(get_db)):
    perm = db.query(models.Permission).filter(
        models.Permission.app_id == app_id,
        models.Permission.role == role
    ).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission introuvable")
    app = db.query(models.App).filter(models.App.id == app_id).first()
    app_name = app.name if app else f"app#{app_id}"
    db.delete(perm)
    db.add(models.AuditLog(
        user_id=admin.id, action="revoke_permission",
        detail=f"{admin.username} a retiré l'accès à '{app_name}' du rôle '{role}'"
    ))
    db.commit()
    return {"message": "Permission supprimée"}

# ============ AUDIT ============

@router.get("/audit")
def get_audit(_admin=Depends(require_admin), db: Session = Depends(get_db)):
    # Jointure manuelle avec users pour afficher le username
    logs = (
        db.query(models.AuditLog, models.User.username)
        .outerjoin(models.User, models.AuditLog.user_id == models.User.id)
        .order_by(models.AuditLog.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "user_id": log.user_id,
            "username": username or f"user#{log.user_id}" if log.user_id else "—",
            "action": log.action,
            "detail": log.detail,
            "date": str(log.created_at),
        }
        for log, username in logs
    ]
