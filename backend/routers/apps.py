from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models

router = APIRouter(prefix="/api")

@router.get("/favorites")
def get_favorites(current_user=Depends(), db: Session = Depends(get_db)):
    favs = db.query(models.Favorite).filter(
        models.Favorite.user_id == current_user.id
    ).all()
    return [f.app_id for f in favs]

@router.post("/favorites/{app_id}")
def add_favorite(app_id: int, current_user=Depends(), db: Session = Depends(get_db)):
    existing = db.query(models.Favorite).filter(
        models.Favorite.user_id == current_user.id,
        models.Favorite.app_id == app_id
    ).first()
    if existing:
        return {"message": "Déjà en favori"}
    db.add(models.Favorite(user_id=current_user.id, app_id=app_id))
    db.commit()
    return {"message": "Ajouté aux favoris"}

@router.delete("/favorites/{app_id}")
def remove_favorite(app_id: int, current_user=Depends(), db: Session = Depends(get_db)):
    fav = db.query(models.Favorite).filter(
        models.Favorite.user_id == current_user.id,
        models.Favorite.app_id == app_id
    ).first()
    if not fav:
        raise HTTPException(status_code=404, detail="Favori introuvable")
    db.delete(fav)
    db.commit()
    return {"message": "Retiré des favoris"}