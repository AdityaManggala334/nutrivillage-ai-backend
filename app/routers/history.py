"""Router riwayat & favorit (FR-04) — tersimpan di database.

- `history_entries` : daftar riwayat per pengguna.
- `favorites`       : status favorit (toggle).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.history import HistoryEntry
from app.models.planning import Favorite
from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.history import HistoryCreate, HistoryEntryOut, HistoryFavoriteIn
from app.schemas.master import RecipeOut

router = APIRouter(prefix="/history", tags=["history"])


def _favorite_ids(db: Session, user_id: int) -> set[int]:
    rows = db.query(Favorite).filter(Favorite.user_id == user_id).all()
    return {int(row.recipe_id) for row in rows if row.recipe_id is not None}


def _to_out(entry: HistoryEntry, favorite_ids: set[int], recipe: Recipe | None) -> HistoryEntryOut:
    return HistoryEntryOut(
        id=entry.id,
        kind=entry.kind,
        note=entry.note or "",
        saved_at=entry.saved_at,
        favorite=entry.recipe_id in favorite_ids if entry.recipe_id else False,
        recipe=RecipeOut.model_validate(recipe) if recipe is not None else None,
    )


@router.get("", response_model=list[HistoryEntryOut])
def list_history(
    filter: str = "all",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[HistoryEntryOut]:
    favorites = _favorite_ids(db, user.id)
    entries = (
        db.query(HistoryEntry)
        .filter(HistoryEntry.user_id == user.id)
        .order_by(HistoryEntry.saved_at.desc(), HistoryEntry.id.desc())
        .all()
    )

    if filter == "favorite":
        entries = [e for e in entries if e.recipe_id in favorites]
    elif filter == "month":
        now = datetime.now()
        entries = [
            e for e in entries if e.saved_at.month == now.month and e.saved_at.year == now.year
        ]

    recipe_ids = {e.recipe_id for e in entries if e.recipe_id is not None}
    recipes = (
        {r.id: r for r in db.query(Recipe).filter(Recipe.id.in_(recipe_ids)).all()}
        if recipe_ids
        else {}
    )
    return [_to_out(e, favorites, recipes.get(e.recipe_id) if e.recipe_id else None) for e in entries]


@router.post("", response_model=HistoryEntryOut, status_code=status.HTTP_201_CREATED)
def save_history(
    payload: HistoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HistoryEntryOut:
    recipe = db.get(Recipe, payload.recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resep tidak ditemukan.")

    existing = (
        db.query(HistoryEntry)
        .filter(
            HistoryEntry.user_id == user.id,
            HistoryEntry.recipe_id == payload.recipe_id,
            HistoryEntry.kind == payload.kind,
        )
        .one_or_none()
    )
    if existing is None:
        existing = HistoryEntry(
            user_id=user.id,
            kind=payload.kind,
            recipe_id=payload.recipe_id,
            note=(payload.note or None),
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)

    return _to_out(existing, _favorite_ids(db, user.id), recipe)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    entry = (
        db.query(HistoryEntry)
        .filter(HistoryEntry.id == entry_id, HistoryEntry.user_id == user.id)
        .one_or_none()
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Riwayat tidak ditemukan.")
    db.delete(entry)
    db.commit()


@router.patch("/{entry_id}", response_model=HistoryEntryOut)
def toggle_favorite(
    entry_id: int,
    payload: HistoryFavoriteIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HistoryEntryOut:
    entry = (
        db.query(HistoryEntry)
        .filter(HistoryEntry.id == entry_id, HistoryEntry.user_id == user.id)
        .one_or_none()
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Riwayat tidak ditemukan.")
    if entry.recipe_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resep tidak tersedia.")

    favorite = (
        db.query(Favorite)
        .filter(Favorite.user_id == user.id, Favorite.recipe_id == entry.recipe_id)
        .one_or_none()
    )
    if payload.favorite and favorite is None:
        db.add(Favorite(user_id=user.id, recipe_id=entry.recipe_id))
    elif not payload.favorite and favorite is not None:
        db.delete(favorite)
    db.commit()

    recipe = db.get(Recipe, entry.recipe_id)
    return _to_out(entry, _favorite_ids(db, user.id), recipe)
