from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
import models

router = APIRouter(prefix="/api/admin")

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

def require_admin(current_user):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")

# -- Lister toutes les apps (sans filtre de droits)
@router.get("/apps")
def list_all_apps(db: Session = Depends(get_db)):
    return db.query(models.App).all()

# -- Ajouter une app
@router.post("/apps")
def create_app(data: AppCreate, db: Session = Depends(get_db)):
    app = models.App(**data.model_dump())
    db.add(app)
    db.commit()
    db.refresh(app)
    return app

# -- Modifier une app
@router.put("/apps/{app_id}")
def update_app(app_id: int, data: AppUpdate, db: Session = Depends(get_db)):
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App introuvable")
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(app, key, value)
    db.commit()
    db.refresh(app)
    return app

# -- Supprimer une app
@router.delete("/apps/{app_id}")
def delete_app(app_id: int, db: Session = Depends(get_db)):
    app = db.query(models.App).filter(models.App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App introuvable")
    db.delete(app)
    db.commit()
    return {"message": "App supprimée"}

# -- Lire la matrice des droits
@router.get("/permissions")
def get_permissions(db: Session = Depends(get_db)):
    perms = db.query(models.Permission).all()
    return [{"app_id": p.app_id, "role": p.role} for p in perms]

# -- Ajouter un droit
@router.post("/permissions")
def add_permission(app_id: int, role: str, db: Session = Depends(get_db)):
    if role not in ("admin", "manager", "collab"):
        raise HTTPException(status_code=400, detail="Rôle invalide")
    existing = db.query(models.Permission).filter(
        models.Permission.app_id == app_id,
        models.Permission.role == role
    ).first()
    if existing:
        return {"message": "Permission déjà existante"}
    db.add(models.Permission(app_id=app_id, role=role))
    db.commit()
    return {"message": "Permission ajoutée"}

# -- Supprimer un droit
@router.delete("/permissions")
def remove_permission(app_id: int, role: str, db: Session = Depends(get_db)):
    perm = db.query(models.Permission).filter(
        models.Permission.app_id == app_id,
        models.Permission.role == role
    ).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission introuvable")
    db.delete(perm)
    db.commit()
    return {"message": "Permission supprimée"}

# -- Lister les utilisateurs
@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return [{"id": u.id, "username": u.username, "role": u.role} for u in users]

# -- Audit log
@router.get("/audit")
def get_audit(db: Session = Depends(get_db)):
    logs = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(50).all()
    return [
        {"user_id": l.user_id, "action": l.action, "detail": l.detail, "date": str(l.created_at)}
        for l in logs
    ]