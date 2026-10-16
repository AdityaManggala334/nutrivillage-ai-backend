"""Router meal planner & daftar belanja — tersimpan di database.

- `meal_plans`          : jadwal menu per pengguna + pekan (FR-26, FR-27, FR-28)
- `shopping_lists`      : satu daftar belanja per pengguna (FR-16, FR-17, FR-29)
- `shopping_list_items` : bahan pada daftar belanja (FR-15)

Daftar belanja di-*generate* dari jadwal (`week_id` → semua resep yang
dijadwalkan) atau digabung dari satu resep (`recipe_id`), lalu disimpan sebagai
baris tabel sehingga status "centang" dan catatan tetap ada antar sesi.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import DayOfWeek, MealType
from app.models.planning import MealPlan, ShoppingList, ShoppingListItem
from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.master import RecipeOut
from app.schemas.planning import (
    MealPlanIn,
    MealPlanOut,
    MealPlanRemovedOut,
    ShoppingGenerateIn,
    ShoppingItemOut,
    ShoppingListOut,
    ShoppingPatchIn,
)

router = APIRouter(tags=["planning"])

_DEFAULT_WEEK = "pekan-ini"
_DEFAULT_LIST_TITLE = "Daftar Belanja Pekan Ini (Senin - Minggu)"

_DAY_ORDER: dict[DayOfWeek, int] = {day: index for index, day in enumerate(DayOfWeek)}
_SLOT_ORDER: dict[MealType, int] = {slot: index for index, slot in enumerate(MealType)}


# --------------------------------------------------------------------- #
# Meal planner (FR-26 s.d. FR-28)                                       #
# --------------------------------------------------------------------- #
def _recipe_map(db: Session, recipe_ids: set[int]) -> dict[int, Recipe]:
    if not recipe_ids:
        return {}
    rows = db.query(Recipe).filter(Recipe.id.in_(recipe_ids)).all()
    return {int(row.id): row for row in rows}


def _meal_out(entry: MealPlan, recipes: dict[int, Recipe]) -> MealPlanOut:
    recipe = recipes.get(int(entry.recipe_id)) if entry.recipe_id else None
    return MealPlanOut(
        id=entry.id,
        week_id=entry.week_id or _DEFAULT_WEEK,
        day=entry.day_of_week,
        slot=entry.meal_type,
        note=entry.note or "",
        recipe=RecipeOut.model_validate(recipe) if recipe is not None else None,
    )


@router.get("/meal-plans", response_model=list[MealPlanOut])
def list_meal_plans(
    week_id: str = _DEFAULT_WEEK,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MealPlanOut]:
    rows = (
        db.query(MealPlan)
        .filter(MealPlan.user_id == user.id, MealPlan.week_id == week_id)
        .all()
    )
    rows.sort(
        key=lambda row: (
            _DAY_ORDER.get(row.day_of_week, 99),
            _SLOT_ORDER.get(row.meal_type, 99),
            row.id,
        )
    )
    recipes = _recipe_map(db, {row.recipe_id for row in rows if row.recipe_id})
    return [_meal_out(row, recipes) for row in rows]


@router.post("/meal-plans", response_model=MealPlanOut, status_code=status.HTTP_201_CREATED)
def assign_meal_plan(
    payload: MealPlanIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MealPlanOut:
    recipe = db.get(Recipe, payload.recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resep tidak ditemukan")

    # Upsert: satu resep per (pengguna, pekan, hari, waktu makan).
    (
        db.query(MealPlan)
        .filter(
            MealPlan.user_id == user.id,
            MealPlan.week_id == payload.week_id,
            MealPlan.day_of_week == payload.day,
            MealPlan.meal_type == payload.slot,
        )
        .delete(synchronize_session=False)
    )

    entry = MealPlan(
        user_id=user.id,
        recipe_id=recipe.id,
        day_of_week=payload.day,
        meal_type=payload.slot,
        week_id=payload.week_id,
        note=payload.note.strip() or None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _meal_out(entry, {int(recipe.id): recipe})


@router.delete("/meal-plans", response_model=MealPlanRemovedOut)
def remove_meal_plan(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MealPlanRemovedOut:
    entry = db.get(MealPlan, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jadwal tidak ditemukan")
    if entry.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bukan jadwal Anda")
    db.delete(entry)
    db.commit()
    return MealPlanRemovedOut(entry_id=entry_id)


# --------------------------------------------------------------------- #
# Daftar belanja (FR-15, FR-16, FR-17, FR-29)                           #
# --------------------------------------------------------------------- #
def _current_list(db: Session, user: User) -> ShoppingList | None:
    return (
        db.query(ShoppingList)
        .filter(ShoppingList.user_id == user.id)
        .order_by(ShoppingList.id.desc())
        .first()
    )


def _ensure_list(db: Session, user: User) -> ShoppingList:
    existing = _current_list(db, user)
    if existing is not None:
        return existing
    created = ShoppingList(user_id=user.id, title=_DEFAULT_LIST_TITLE, total_estimate=0)
    db.add(created)
    db.flush()
    return created


def _items_out(db: Session, list_id: int) -> list[ShoppingItemOut]:
    rows = (
        db.query(ShoppingListItem)
        .filter(ShoppingListItem.list_id == list_id)
        .order_by(ShoppingListItem.id.asc())
        .all()
    )
    return [
        ShoppingItemOut(
            id=row.id,
            name=row.name,
            quantity=float(row.quantity),
            unit=row.unit,
            estimated_price=float(row.estimated_price),
            checked=bool(row.checked),
        )
        for row in rows
    ]


def _list_out(db: Session, shopping_list: ShoppingList) -> ShoppingListOut:
    items = _items_out(db, shopping_list.id)
    return ShoppingListOut(
        id=shopping_list.id,
        title=shopping_list.title,
        note=shopping_list.notes or "",
        total_estimated_cost=sum(item.estimated_price for item in items),
        generated_at=shopping_list.created_at,
        items=items,
    )


def _aggregate(recipes: list[Recipe]) -> list[tuple[str, str, float, float]]:
    """Jumlahkan bahan per (nama, satuan) seperti pada versi sebelumnya."""
    agg: dict[tuple[str, str], list[float]] = {}
    for recipe in recipes:
        for item in recipe.ingredients:
            quantity = float(item.quantity)
            if quantity <= 0:
                continue
            bucket = agg.setdefault((item.name, item.unit), [0.0, 0.0])
            bucket[0] += quantity
            bucket[1] += float(item.estimated_price)
    return [
        (name, unit, quantity, price)
        for (name, unit), (quantity, price) in agg.items()
    ]


def _week_recipes(db: Session, user: User, week_id: str) -> list[Recipe]:
    entries = (
        db.query(MealPlan)
        .filter(MealPlan.user_id == user.id, MealPlan.week_id == week_id)
        .all()
    )
    recipe_ids = {entry.recipe_id for entry in entries if entry.recipe_id}
    if not recipe_ids:
        return []
    return list(_recipe_map(db, recipe_ids).values())


def _apply_recipes(
    db: Session,
    user: User,
    recipes: list[Recipe],
    *,
    replace: bool,
) -> ShoppingList:
    shopping_list = _ensure_list(db, user)

    if replace:
        for item in list(shopping_list.items):
            db.delete(item)
        shopping_list.notes = None
        shopping_list.title = _DEFAULT_LIST_TITLE
        db.flush()
        existing: dict[tuple[str, str], ShoppingListItem] = {}
    else:
        existing = {(item.name, item.unit): item for item in shopping_list.items}

    for name, unit, quantity, price in _aggregate(recipes):
        found = existing.get((name, unit))
        if found is not None:
            found.quantity = float(found.quantity) + quantity
            found.estimated_price = float(found.estimated_price) + price
        else:
            db.add(
                ShoppingListItem(
                    list_id=shopping_list.id,
                    name=name,
                    unit=unit,
                    quantity=quantity,
                    estimated_price=price,
                    checked=False,
                )
            )

    db.flush()
    shopping_list.total_estimate = sum(
        item.estimated_price
        for item in _items_out(db, shopping_list.id)
    )
    shopping_list.created_at = datetime.now()
    db.commit()
    db.refresh(shopping_list)
    return shopping_list


@router.get("/shopping-list", response_model=ShoppingListOut)
def get_shopping_list(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShoppingListOut:
    shopping_list = _current_list(db, user)
    if shopping_list is None:
        # Belum pernah dibuat → daftar kosong tanpa membuat baris percuma.
        return ShoppingListOut(
            id=0,
            title=_DEFAULT_LIST_TITLE,
            note="",
            total_estimated_cost=0,
            generated_at=datetime.now(),
            items=[],
        )
    return _list_out(db, shopping_list)


@router.post("/shopping-list", response_model=ShoppingListOut, status_code=status.HTTP_201_CREATED)
def generate_shopping_list(
    payload: ShoppingGenerateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShoppingListOut:
    if payload.recipe_id is not None:
        recipe = db.get(Recipe, payload.recipe_id)
        if recipe is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Resep tidak ditemukan"
            )
        shopping_list = _apply_recipes(db, user, [recipe], replace=False)
    elif payload.week_id is not None:
        recipes = _week_recipes(db, user, payload.week_id)
        shopping_list = _apply_recipes(db, user, recipes, replace=True)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Isi week_id atau recipe_id",
        )
    return _list_out(db, shopping_list)


@router.patch("/shopping-list", response_model=ShoppingListOut)
def patch_shopping_list(
    payload: ShoppingPatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShoppingListOut:
    shopping_list = _ensure_list(db, user)

    if payload.item_id is not None:
        item = (
            db.query(ShoppingListItem)
            .filter(
                ShoppingListItem.id == payload.item_id,
                ShoppingListItem.list_id == shopping_list.id,
            )
            .first()
        )
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Bahan tidak ditemukan"
            )
        item.checked = (not item.checked) if payload.checked is None else payload.checked
    elif payload.note is not None:
        shopping_list.notes = payload.note
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Isi item_id atau note",
        )

    db.commit()
    db.refresh(shopping_list)
    return _list_out(db, shopping_list)


@router.delete("/shopping-list", response_model=ShoppingListOut)
def delete_shopping_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShoppingListOut:
    shopping_list = _current_list(db, user)
    if shopping_list is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Daftar belanja belum ada"
        )

    item = (
        db.query(ShoppingListItem)
        .filter(
            ShoppingListItem.id == item_id,
            ShoppingListItem.list_id == shopping_list.id,
        )
        .first()
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bahan tidak ditemukan"
        )

    db.delete(item)
    db.flush()
    shopping_list.total_estimate = sum(
        row.estimated_price for row in _items_out(db, shopping_list.id)
    )
    db.commit()
    db.refresh(shopping_list)
    return _list_out(db, shopping_list)
