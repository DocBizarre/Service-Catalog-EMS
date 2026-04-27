from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user
import models

router = APIRouter(prefix="/api")

@router.get("/company")
def get_company_info(_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Retourne toutes les infos société sous forme de dict clé->valeur."""
    rows = db.query(models.CompanyInfo).all()
    return {r.key: r.value for r in rows}

@router.get("/announcements")
def list_announcements(_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Retourne les annonces actives (pour affichage sur la page d'accueil)."""
    items = (
        db.query(models.Announcement, models.User.username)
        .outerjoin(models.User, models.Announcement.author_id == models.User.id)
        .filter(models.Announcement.active == True)
        .order_by(models.Announcement.created_at.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "id": a.id,
            "title": a.title,
            "content": a.content,
            "image": a.image,
            "category": a.category or "Info",
            "featured": a.featured,
            "breaking": a.breaking,
            "author": username,
            "created_at": str(a.created_at),
        }
        for a, username in items
    ]
