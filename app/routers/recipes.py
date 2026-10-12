"""Router publik katalog resep (FR-10).

Endpoint terbuka (tanpa autentikasi) — mendukung "Lihat Menu Tanpa Daftar".
CRUD admin untuk resep ada di `app/routers/master.py` (`/admin/recipes`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.recipe import Recipe
from app.schemas.master import RecipeOut

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("", response_model=list[RecipeOut])
def list_recipes(db: Session = Depends(get_db)) -> list[Recipe]:
    return db.query(Recipe).order_by(Recipe.name).all()


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resep tidak ditemukan.")
    return recipe
