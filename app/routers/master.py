"""Router CRUD data master (khusus admin).

Ingredient/bahan, nutrisi, menu/resep, musim, dan komoditas lokal.
Semua endpoint dilindungi RBAC admin.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
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
from app.models.content import FoodSafetyInfo
from app.models.enums import PriceSourceType, PriceStatus
from app.models.price import Price
from app.models.recipe import Recipe, RecipeIngredient, RecipeNutrition
from app.models.user import User, UserRole
from app.schemas.master import (
    IngredientCreate,
    NutritionGridRow,
    NutritionGridUpdate,
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
def list_ingredients(db: Session = Depends(get_db), _: User = AdminDep) -> list[IngredientOut]:
    items = db.query(Ingredient).order_by(Ingredient.name).all()
    # Satu query agregat untuk seluruh bahan, bukan satu query per baris.
    counts = dict(
        db.query(
            RecipeIngredient.ingredient_id,
            func.count(func.distinct(RecipeIngredient.recipe_id)),
        )
        .filter(RecipeIngredient.ingredient_id.isnot(None))
        .group_by(RecipeIngredient.ingredient_id)
        .all()
    )
    hasil = []
    for item in items:
        row = IngredientOut.model_validate(item)
        row.used_in_menus = counts.get(item.id, 0)
        hasil.append(row)
    return hasil


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
    dipakai = (
        db.query(func.count(func.distinct(RecipeIngredient.recipe_id)))
        .filter(RecipeIngredient.ingredient_id == item_id)
        .scalar()
        or 0
    )
    if dipakai > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Bahan dipakai di {dipakai} menu. Hapus bahan ini dari komposisi "
                "menu terlebih dahulu sebelum menghapusnya."
            ),
        )
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
    data = payload.model_dump(
        exclude_unset=True,
        exclude={"ingredients", "nutrition", "food_safety_ids"},
    )
    for key, value in data.items():
        setattr(recipe, key, value)

    ingredients = getattr(payload, "ingredients", None)
    if ingredients is not None:
        # Hapus dulu komposisi lama dan flush, agar unique (recipe_id, ingredient_id)
        # tidak bentrok saat baris baru dengan bahan yang sama disisipkan.
        if recipe.id is not None:
            db.query(RecipeIngredient).filter(
                RecipeIngredient.recipe_id == recipe.id
            ).delete(synchronize_session=False)
            db.flush()
            db.expire(recipe, ["ingredients"])
        for line in ingredients:
            recipe.ingredients.append(RecipeIngredient(**line.model_dump()))

    food_safety_ids = getattr(payload, "food_safety_ids", None)
    if food_safety_ids is not None:
        recipe.food_safety = (
            db.query(FoodSafetyInfo)
            .filter(FoodSafetyInfo.id.in_(food_safety_ids))
            .all()
            if food_safety_ids
            else []
        )

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
    from app.services.engine_data import hitung_gizi_semua_menu

    hitung_gizi_semua_menu(db)
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
    from app.services.engine_data import hitung_gizi_semua_menu

    hitung_gizi_semua_menu(db)
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


# --------------------------------------------------------------------------
# Tabel gabungan: bahan + gizi + harga (halaman admin "Nutrisi")
# --------------------------------------------------------------------------
@router.get("/nutrition-grid", response_model=list[NutritionGridRow])
def nutrition_grid(db: Session = Depends(get_db), _: User = AdminDep) -> list[NutritionGridRow]:
    """Semua bahan dengan gizi, harga terakhir, dan jumlah menu yang memakainya.

    Satu permintaan agar halaman admin tidak perlu menggabungkan tiga endpoint
    dan tetap konsisten saat diedit.
    """
    gizi = {n.ingredient_id: n for n in db.query(NutritionFact)}
    harga: dict[int, Price] = {}
    for p in db.query(Price).order_by(Price.recorded_date.desc(), Price.id.desc()):
        harga.setdefault(p.ingredient_id, p)
    dipakai: dict[int, int] = {}
    for (ingredient_id,) in db.query(RecipeIngredient.ingredient_id).distinct():
        dipakai[ingredient_id] = (
            db.query(RecipeIngredient)
            .filter(RecipeIngredient.ingredient_id == ingredient_id)
            .count()
        )
    rows = []
    for ins in db.query(Ingredient).order_by(Ingredient.name):
        nz = gizi.get(ins.id)
        p = harga.get(ins.id)
        rows.append(NutritionGridRow(
            ingredient_id=ins.id, code=ins.code, name=ins.name,
            category=ins.category.value if ins.category else '',
            unit=ins.unit, mbg_slot=ins.mbg_slot.value if ins.mbg_slot else None,
            allergens=list(ins.allergens or []), is_local=bool(ins.is_local),
            used_in_menus=dipakai.get(ins.id, 0),
            price_per_kg=float(p.price) if p else None,
            price_source=p.source if p else None,
            price_status=p.status.value if p else None,
            nutrition=NutritionFactIn.model_validate(nz) if nz else None,
        ))
    return rows


@router.patch("/nutrition-grid/{ingredient_id}", response_model=NutritionGridRow)
def update_nutrition_grid(
    ingredient_id: int,
    payload: NutritionGridUpdate,
    db: Session = Depends(get_db),
    _: User = AdminDep,
) -> NutritionGridRow:
    """Simpan koreksi admin, lalu hitung ulang gizi menu yang memakai bahan ini.

    Gizi menu bersifat turunan; tanpa hitung ulang, angka di halaman menu akan
    berbeda dengan angka yang dipakai mesin.
    """
    ins = _get_or_404(db, Ingredient, ingredient_id, "Bahan")
    for key, value in payload.model_dump(exclude_unset=True,
                                         exclude={'nutrition', 'price_per_kg'}).items():
        setattr(ins, key, value)
    if payload.nutrition is not None:
        fact = (db.query(NutritionFact)
                .filter(NutritionFact.ingredient_id == ingredient_id).one_or_none())
        if fact is None:
            fact = NutritionFact(ingredient_id=ingredient_id)
            db.add(fact)
        for key, value in payload.nutrition.model_dump().items():
            setattr(fact, key, value)
    if payload.price_per_kg is not None:
        terakhir = (db.query(Price).filter(Price.ingredient_id == ingredient_id)
                    .order_by(Price.recorded_date.desc(), Price.id.desc()).first())
        if terakhir is None or float(terakhir.price) != payload.price_per_kg:
            db.add(Price(
                ingredient_id=ingredient_id, region_id=None,
                price=payload.price_per_kg, unit='kg',
                recorded_date=date.today(), source_type=PriceSourceType.MANUAL,
                source='koreksi admin', status=PriceStatus.APPROVED))
    db.commit()
    from app.services.engine_data import hitung_gizi_semua_menu

    hitung_gizi_semua_menu(db)
    baris = next(r for r in nutrition_grid(db) if r.ingredient_id == ingredient_id)
    return baris
