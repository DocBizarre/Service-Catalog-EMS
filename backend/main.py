from fastapi import FastAPI, Depends, HTTPException, status, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional
import models, auth
from database import engine, get_db
import models as m
from routers import apps as apps_router
from routers import admin as admin_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Service Catalog EMS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(apps_router.router)
app.include_router(admin_router.router)

# -- Dépendance : récupérer l'utilisateur connecté depuis le cookie
def get_current_user(token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="Non connecté")
    payload = auth.decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Session expirée")
    user = db.query(m.User).filter(m.User.id == payload.get("user_id")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user

# -- Login
@app.post("/api/login")
def login(response: Response, username: str, password: str, db: Session = Depends(get_db)):
    user = auth.authenticate_user(db, username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    token = auth.create_token({"user_id": user.id, "role": user.role})
    response.set_cookie("token", token, httponly=True, max_age=28800)
    db.add(m.AuditLog(user_id=user.id, action="login", detail="Connexion réussie"))
    db.commit()
    return {"username": user.username, "role": user.role}

# -- Logout
@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("token")
    return {"message": "Déconnecté"}

# -- Profil utilisateur connecté
@app.get("/api/me")
def me(current_user=Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}

# -- Apps accessibles selon le rôle (filtrage côté serveur)
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