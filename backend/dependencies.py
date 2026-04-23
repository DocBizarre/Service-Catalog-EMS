from fastapi import Depends, HTTPException, Cookie
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
import auth
import models as m

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

def require_admin(current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    return current_user
