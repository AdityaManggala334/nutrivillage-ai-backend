"""Router CRUD data master (khusus admin).

Ingredient/bahan, nutrisi, menu/resep, musim, dan komoditas lokal.
Semua endpoint dilindungi RBAC admin.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.catalog import (
    Ingredient,
    LocalAvailability,
    NutritionFact,
    Region,
    SeasonalAvailability,
)
from app.models.recipe import Recipe, RecipeIngredient, RecipeNutrition
from app.models.user import User, UserRole
from app.schemas.master import (
    IngredientCreate,
    IngredientOut,
    IngredientUpdate,
    LocalCreate,
    LocalOut,
    LocalUpdate,
    NutritionFactIn,
    NutritionFactOut,
    RecipeCreate,
    RecipeOut,
    RecipeUpdate,
    RegionOut,
    SeasonalCreate,
    SeasonalOut,
    SeasonalUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin-master"])

AdminDep = Depends(require_roles(UserRole.ADMIN))


def _get_or_404(db: Session, model, obj_id: int, label: str):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} tidak ditemukan.")
    return obj


# --------------------------------------------------------------------------
# Wilayah (untuk dropdown)
# --------------------------------------------------------------------------
@router.get("/regions", response_model=list[RegionOut])
def list_regions(db: Session = Depends(get_db), _: User = AdminDep) -> list[Region]:
    return db.query(Region).order_by(Region.name).all()


# --------------------------------------------------------------------------
# Bahan pangan
# --------------------------------------------------------------------------
@router.get("/ingredients", response_model=list[IngredientOut])
def list_ingredients(db: Session = Depends(get_db), _: User = AdminDep) -> list[Ingredient]:
    return db.query(Ingredient).order_by(Ingredient.name).all()


@router.post("/ingredients", response_model=IngredientOut, status_code=status.HTTP_201_CREATED)
def create_ingredient(
    payload: IngredientCreate, db: Session = Depends(get_db), _: User = AdminDep
) -> Ingredient:
    item = Ingredient(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/ingredients/{item_id}", response_model=IngredientOut)
def update_ingredient(
    item_id: int,
    payload: IngredientUpdate,
    db: Session = Depends(get_db),
    _: User = AdminDep,
) -> Ingredient:
    item = _get_or_404(db, Ingredient, item_id, "Bahan")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/ingredients/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ingredient(item_id: int, db: Session = Depends(get_db), _: User = AdminDep) -> None:
    item = _get_or_404(db, Ingredient, item_id, "Bahan")
    db.delete(item)
    db.commit()


# --------------------------------------------------------------------------
# Nutrisi bahan (upsert per bahan)
# --------------------------------------------------------------------------
@router.get("/nutrition", response_model=list[NutritionFactOut])
def list_nutrition(db: Session = Depends(get_db), _: User = AdminDep) -> list[NutritionFact]:
    return db.query(NutritionFact).order_by(NutritionFact.ingredient_id).all()


@router.put("/nutrition/{ingredient_id}", response_model=NutritionFactOut)
def upsert_nutrition(
    ingredient_id: int,
    payload: NutritionFactIn,
    db: Session = Depends(get_db),
    _: User = AdminDep,
) -> NutritionFact:
    _get_or_404(db, Ingredient, ingredient_id, "Bahan")
    fact = (
        db.query(NutritionFact)
        .filter(NutritionFact.ingredient_id == ingredient_id)
        .one_or_none()
    )
    if fact is None:
        fact = NutritionFact(ingredient_id=ingredient_id)
        db.add(fact)
    for key, value in payload.model_dump().items():
        setattr(fact, key, value)
    db.commit()
    db.refresh(fact)
    return fact


@router.delete("/nutrition/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_nutrition(ingredient_id: int, db: Session = Depends(get_db), _: User = AdminDep) -> None:
    fact = (
        db.query(NutritionFact)
        .filter(NutritionFact.ingredient_id == ingredient_id)
        .one_or_none()
    )
    if fact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data nutrisi tidak ditemukan.")
    db.delete(fact)
    db.commit()


# --------------------------------------------------------------------------
# Menu / resep
# --------------------------------------------------------------------------
def _replace_recipe_children(db: Session, recipe: Recipe, payload: RecipeUpdate | RecipeCreate) -> None:
    data = payload.model_dump(exclude_unset=True, exclude={"ingredients", "nutrition"})
    for key, value in data.items():
        setattr(recipe, key, value)

    ingredients = getattr(payload, "ingredients", None)
    if ingredients is not None:
        recipe.ingredients.clear()
        for line in ingredients:
            recipe.ingredients.append(RecipeIngredient(**line.model_dump()))

    nutrition = getattr(payload, "nutrition", None)
    if nutrition is not None:
        if recipe.nutrition is None:
            recipe.nutrition = RecipeNutrition(recipe_id=recipe.id)
        for key, value in nutrition.model_dump().items():
            setattr(recipe.nutrition, key, value)


@router.get("/recipes", response_model=list[RecipeOut])
def list_recipes(db: Session = Depends(get_db), _: User = AdminDep) -> list[Recipe]:
    return db.query(Recipe).order_by(Recipe.name).all()


@router.get("/recipes/{item_id}", response_model=RecipeOut)
def get_recipe(item_id: int, db: Session = Depends(get_db), _: User = AdminDep) -> Recipe:
    return _get_or_404(db, Recipe, item_id, "Menu")


@router.post("/recipes", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
def create_recipe(
    payload: RecipeCreate, db: Session = Depends(get_db), _: User = AdminDep
) -> Recipe:
    recipe = Recipe()
    _replace_recipe_children(db, recipe, payload)
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


@router.patch("/recipes/{item_id}", response_model=RecipeOut)
def update_recipe(
    item_id: int,
    payload: RecipeUpdate,
    db: Session = Depends(get_db),
    _: User = AdminDep,
) -> Recipe:
    recipe = _get_or_404(db, Recipe, item_id, "Menu")
    _replace_recipe_children(db, recipe, payload)
    db.commit()
    db.refresh(recipe)
    return recipe


@router.delete("/recipes/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(item_id: int, db: Session = Depends(get_db), _: User = AdminDep) -> None:
    recipe = _get_or_404(db, Recipe, item_id, "Menu")
    db.delete(recipe)
    db.commit()


# --------------------------------------------------------------------------
# Musim
# --------------------------------------------------------------------------
@router.get("/seasons", response_model=list[SeasonalOut])
def list_seasons(db: Session = Depends(get_db), _: User = AdminDep) -> list[SeasonalAvailability]:
    return (
        db.query(SeasonalAvailability)
        .order_by(SeasonalAvailability.ingredient_id, SeasonalAvailability.month)
        .all()
    )


@router.post("/seasons", response_model=SeasonalOut, status_code=status.HTTP_201_CREATED)
def create_season(
    payload: SeasonalCreate, db: Session = Depends(get_db), _: User = AdminDep
) -> SeasonalAvailability:
    _get_or_404(db, Ingredient, payload.ingredient_id, "Bahan")
    exists = (
        db.query(SeasonalAvailability)
        .filter(
            SeasonalAvailability.ingredient_id == payload.ingredient_id,
            SeasonalAvailability.month == payload.month,
        )
        .one_or_none()
    )
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Data musim untuk bahan & bulan ini sudah ada.",
        )
    item = SeasonalAvailability(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/seasons/{item_id}", response_model=SeasonalOut)
def update_season(
    item_id: int,
    payload: SeasonalUpdate,
    db: Session = Depends(get_db),
    _: User = AdminDep,
) -> SeasonalAvailability:
    item = _get_or_404(db, SeasonalAvailability, item_id, "Data musim")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/seasons/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_season(item_id: int, db: Session = Depends(get_db), _: User = AdminDep) -> None:
    item = _get_or_404(db, SeasonalAvailability, item_id, "Data musim")
    db.delete(item)
    db.commit()


# --------------------------------------------------------------------------
# Komoditas lokal
# --------------------------------------------------------------------------
@router.get("/local", response_model=list[LocalOut])
def list_local(db: Session = Depends(get_db), _: User = AdminDep) -> list[LocalAvailability]:
    return (
        db.query(LocalAvailability)
        .order_by(LocalAvailability.ingredient_id)
        .all()
    )


@router.post("/local", response_model=LocalOut, status_code=status.HTTP_201_CREATED)
def create_local(
    payload: LocalCreate, db: Session = Depends(get_db), _: User = AdminDep
) -> LocalAvailability:
    _get_or_404(db, Ingredient, payload.ingredient_id, "Bahan")
    _get_or_404(db, Region, payload.region_id, "Wilayah")
    exists = (
        db.query(LocalAvailability)
        .filter(
            LocalAvailability.ingredient_id == payload.ingredient_id,
            LocalAvailability.region_id == payload.region_id,
        )
        .one_or_none()
    )
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Komoditas lokal untuk bahan & wilayah ini sudah ada.",
        )
    item = LocalAvailability(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/local/{item_id}", response_model=LocalOut)
def update_local(
    item_id: int,
    payload: LocalUpdate,
    db: Session = Depends(get_db),
    _: User = AdminDep,
) -> LocalAvailability:
    item = _get_or_404(db, LocalAvailability, item_id, "Komoditas lokal")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/local/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_local(item_id: int, db: Session = Depends(get_db), _: User = AdminDep) -> None:
    item = _get_or_404(db, LocalAvailability, item_id, "Komoditas lokal")
    db.delete(item)
    db.commit()
