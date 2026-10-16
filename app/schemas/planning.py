"""Skema Pydantic meal planner & daftar belanja (FR-15–FR-17, FR-26–FR-29).

Mengacu SKPL V4 Final: Tabel 6.18 (`shopping_lists`), 6.19
(`shopping_list_items`), dan 6.24 (`meal_plans`). Nama field mengikuti
konvensi API (snake_case) lalu dipetakan ke model frontend di Next.js.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import DayOfWeek, MealType
from app.schemas.master import RecipeOut


class MealPlanIn(BaseModel):
    """Assign / ganti menu pada satu slot jadwal (upsert per hari+waktu)."""

    week_id: str = Field(default="pekan-ini", min_length=1, max_length=50)
    day: DayOfWeek
    slot: MealType
    recipe_id: int = Field(gt=0)
    note: str = Field(default="", max_length=255)


class MealPlanOut(BaseModel):
    id: int
    week_id: str
    day: DayOfWeek
    slot: MealType
    note: str
    recipe: RecipeOut | None = None


class MealPlanRemovedOut(BaseModel):
    entry_id: int


class ShoppingItemOut(BaseModel):
    id: int
    name: str
    quantity: float
    unit: str
    estimated_price: float
    checked: bool


class ShoppingListOut(BaseModel):
    id: int
    title: str
    note: str
    total_estimated_cost: float
    generated_at: datetime
    items: list[ShoppingItemOut] = Field(default_factory=list)


class ShoppingGenerateIn(BaseModel):
    """Buat ulang dari jadwal (`week_id`) ATAU gabung satu resep (`recipe_id`)."""

    week_id: str | None = Field(default=None, max_length=50)
    recipe_id: int | None = None


class ShoppingPatchIn(BaseModel):
    """Centang bahan (`item_id` + `checked`) atau ubah catatan (`note`)."""

    item_id: int | None = None
    checked: bool | None = None
    note: str | None = Field(default=None, max_length=1000)
