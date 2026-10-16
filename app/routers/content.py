"""Router konten: artikel gizi, notifikasi, dan keamanan pangan (FR-03, FR-21).

Endpoint publik hanya menampilkan konten yang memang layak ditampilkan:
artikel (publik) dan informasi keamanan pangan berstatus `verified`.
Pengelolaan (CRUD + verifikasi) dilindungi RBAC admin.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_optional_user, require_roles
from app.db.session import get_db
from app.models.content import Article, FoodSafetyInfo, Notification
from app.models.enums import FoodSafetyVerification
from app.models.family import FamilyProfile
from app.models.user import User, UserRole
from app.schemas.content import (
    ArticleCreate,
    ArticleOut,
    ArticleUpdate,
    FoodSafetyCreate,
    FoodSafetyOut,
    FoodSafetyUpdate,
    NotificationCreate,
    NotificationOut,
)

router = APIRouter(tags=["content"])

AdminDep = Depends(require_roles(UserRole.ADMIN))


def _get_or_404(db: Session, model, obj_id: int, label: str):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} tidak ditemukan."
        )
    return obj


# --------------------------------------------------------------------------
# Artikel gizi — publik
# --------------------------------------------------------------------------
@router.get("/articles", response_model=list[ArticleOut])
def list_articles(db: Session = Depends(get_db)) -> list[Article]:
    return db.query(Article).order_by(Article.created_at.desc(), Article.id.desc()).all()


@router.get("/articles/{article_id}", response_model=ArticleOut)
def get_article(article_id: int, db: Session = Depends(get_db)) -> Article:
    return _get_or_404(db, Article, article_id, "Artikel")


# --------------------------------------------------------------------------
# Artikel gizi — admin
# --------------------------------------------------------------------------
@router.post(
    "/admin/articles",
    response_model=ArticleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminDep],
)
def create_article(payload: ArticleCreate, db: Session = Depends(get_db)) -> Article:
    if not payload.body:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Isi artikel minimal satu paragraf.",
        )
    if payload.code:
        exists = db.query(Article).filter(Article.code == payload.code).one_or_none()
        if exists is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Kode artikel sudah dipakai."
            )
    article = Article(**payload.model_dump())
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


@router.patch(
    "/admin/articles/{article_id}",
    response_model=ArticleOut,
    dependencies=[AdminDep],
)
def update_article(
    article_id: int, payload: ArticleUpdate, db: Session = Depends(get_db)
) -> Article:
    article = _get_or_404(db, Article, article_id, "Artikel")
    data = payload.model_dump(exclude_unset=True)
    if data.get("body") is not None and len(data["body"]) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Isi artikel minimal satu paragraf.",
        )
    for key, value in data.items():
        setattr(article, key, value)
    db.commit()
    db.refresh(article)
    return article


@router.delete(
    "/admin/articles/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminDep],
)
def delete_article(article_id: int, db: Session = Depends(get_db)) -> None:
    article = _get_or_404(db, Article, article_id, "Artikel")
    db.delete(article)
    db.commit()


# --------------------------------------------------------------------------
# Notifikasi — dibaca pengguna (opsional login) + dikelola admin
# --------------------------------------------------------------------------
@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> list[Notification]:
    query = db.query(Notification)

    if user is None:
        # Tamu: hanya notifikasi global (tanpa pemilik).
        query = query.filter(Notification.user_id.is_(None))
    else:
        profile = db.get(FamilyProfile, user.id)
        if profile is not None and not profile.notifications_enabled:
            # Pengguna mematikan notifikasi di halaman Profil.
            return []
        query = query.filter(
            or_(Notification.user_id.is_(None), Notification.user_id == user.id)
        )

    return query.order_by(Notification.created_at.desc(), Notification.id.desc()).all()


@router.get(
    "/admin/notifications",
    response_model=list[NotificationOut],
    dependencies=[AdminDep],
)
def admin_list_notifications(db: Session = Depends(get_db)) -> list[Notification]:
    return db.query(Notification).order_by(Notification.created_at.desc()).all()


@router.post(
    "/admin/notifications",
    response_model=NotificationOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminDep],
)
def admin_create_notification(
    payload: NotificationCreate, db: Session = Depends(get_db)
) -> Notification:
    item = Notification(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete(
    "/admin/notifications/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminDep],
)
def admin_delete_notification(notification_id: int, db: Session = Depends(get_db)) -> None:
    item = _get_or_404(db, Notification, notification_id, "Notifikasi")
    db.delete(item)
    db.commit()


# --------------------------------------------------------------------------
# Keamanan pangan — publik (hanya terverifikasi) & admin
# --------------------------------------------------------------------------
@router.get("/food-safety", response_model=list[FoodSafetyOut])
def list_verified_food_safety(db: Session = Depends(get_db)) -> list[FoodSafetyInfo]:
    """Entri terverifikasi saja — boleh ditampilkan sebagai fakta ke pengguna."""
    return (
        db.query(FoodSafetyInfo)
        .filter(FoodSafetyInfo.verification == FoodSafetyVerification.VERIFIED)
        .order_by(FoodSafetyInfo.id)
        .all()
    )


@router.get(
    "/admin/food-safety",
    response_model=list[FoodSafetyOut],
    dependencies=[AdminDep],
)
def admin_list_food_safety(db: Session = Depends(get_db)) -> list[FoodSafetyInfo]:
    return db.query(FoodSafetyInfo).order_by(FoodSafetyInfo.id).all()


@router.post(
    "/admin/food-safety",
    response_model=FoodSafetyOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminDep],
)
def admin_create_food_safety(
    payload: FoodSafetyCreate, db: Session = Depends(get_db)
) -> FoodSafetyInfo:
    item = FoodSafetyInfo(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch(
    "/admin/food-safety/{item_id}",
    response_model=FoodSafetyOut,
    dependencies=[AdminDep],
)
def admin_update_food_safety(
    item_id: int, payload: FoodSafetyUpdate, db: Session = Depends(get_db)
) -> FoodSafetyInfo:
    item = _get_or_404(db, FoodSafetyInfo, item_id, "Informasi keamanan pangan")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete(
    "/admin/food-safety/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminDep],
)
def admin_delete_food_safety(item_id: int, db: Session = Depends(get_db)) -> None:
    item = _get_or_404(db, FoodSafetyInfo, item_id, "Informasi keamanan pangan")
    db.delete(item)
    db.commit()
