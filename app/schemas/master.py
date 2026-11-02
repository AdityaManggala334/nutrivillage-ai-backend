"""Skema Pydantic untuk CRUD data master admin.

Mencakup: bahan pangan (ingredients), nutrisi (nutrition_facts),
menu/resep (recipes + komposisi + gizi), musim (seasonal_availability),
dan komoditas lokal (local_availability).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    IngredientCategory,
    LocalLevel,
    MbgSlot,
    RecipeCategory,
    SeasonalStatus,
)


# --------------------------------------------------------------------------
# Wilayah
# --------------------------------------------------------------------------
class RegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    province: str


# --------------------------------------------------------------------------
# Bahan pangan
# --------------------------------------------------------------------------
class IngredientBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: IngredientCategory
    unit: str = Field(default="kg", max_length=20)
    description: str | None = None
    is_local: bool = False
    is_in_season: bool = False
    # Slot MBG yang diisi bahan ini. Mesin memakai ini untuk menentukan komponen
    # apa yang sudah terpenuhi oleh satu sajian.
    mbg_slot: MbgSlot | None = None
    # Daftar alergen, mis. ["kedelai"]. Mesin membuang menu yang memuat alergen
    # milik pengguna, jadi daftar ini harus diisi dengan benar.
    allergens: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("allergens", mode="before")
    @classmethod
    def _empty_allergens(cls, value: object) -> object:
        return [] if value is None else value


class IngredientCreate(IngredientBase):
    pass


class IngredientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: IngredientCategory | None = None
    unit: str | None = Field(default=None, max_length=20)
    description: str | None = None
    is_local: bool | None = None
    is_in_season: bool | None = None
    mbg_slot: MbgSlot | None = None
    allergens: list[str] | None = Field(default=None, max_length=10)


class IngredientOut(IngredientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Jumlah menu yang memakai bahan ini; dipakai admin sebelum menghapus.
    used_in_menus: int = 0
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# Nutrisi bahan
# --------------------------------------------------------------------------
# Gizi yang dihitung mesin rekomendasi. Bedanya dengan `details`: kolom di bawah
# ini mengubah hasil rekomendasi, `details` tidak.


class NutritionFactIn(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    calories: float = Field(default=0, ge=0)
    protein: float = Field(default=0, ge=0)
    carbs: float = Field(default=0, ge=0)
    fat: float = Field(default=0, ge=0)
    fiber: float = Field(default=0, ge=0)
    # Bagian Dapat Dimakan (%). Mesin membagi gram bersih dengan angka ini untuk
    # mendapat berat yang harus dibeli; isi 0 dianggap 100.
    bdd_percent: float = Field(default=100, gt=0, le=100)
    calcium_mg: float = Field(default=0, ge=0)
    iron_mg: float = Field(default=0, ge=0)
    vitamin_a_mcg: float = Field(default=0, ge=0)
    vitamin_c_mg: float = Field(default=0, ge=0)
    sugar_g: float = Field(default=0, ge=0)
    sodium_mg: float = Field(default=0, ge=0)
    details: dict = Field(default_factory=dict)
    source: str = Field(default="TKPI Kemenkes RI", max_length=100)


class NutritionFactOut(NutritionFactIn):
    model_config = ConfigDict(from_attributes=True)

    ingredient_id: int


# --------------------------------------------------------------------------
# Menu / resep
# --------------------------------------------------------------------------
class RecipeIngredientIn(BaseModel):
    ingredient_id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    quantity: float = Field(gt=0)
    unit: str = Field(default="kg", max_length=20)
    estimated_price: float = Field(default=0, ge=0)
    is_pantry: bool = False
    note: str | None = Field(default=None, max_length=100)


class RecipeIngredientOut(RecipeIngredientIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


class RecipeNutritionIn(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    calories: float = Field(default=0, ge=0)
    protein: float = Field(default=0, ge=0)
    carbohydrates: float = Field(default=0, ge=0)
    fat: float = Field(default=0, ge=0)
    fiber: float = Field(default=0, ge=0)


class RecipeBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: RecipeCategory = RecipeCategory.MAKANAN_UTAMA
    description: str | None = None
    servings: int = Field(default=4, ge=1, le=100)
    cooking_time_min: int = Field(default=30, ge=1, le=600)
    steps: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    image_url: str | None = Field(default=None, max_length=255)
    image_file_id: str | None = Field(default=None, max_length=120)
    image_key: str | None = Field(default=None, max_length=50)
    image_alt: str | None = Field(default=None, max_length=255)
    is_local: bool = False
    in_season: bool = False
    is_vegetarian: bool = False
    estimated_cost: float = Field(default=0, ge=0)
    meal_kind: Literal['hidangan', 'komponen'] = 'komponen'


class RecipeCreate(RecipeBase):
    ingredients: list[RecipeIngredientIn] = Field(default_factory=list)
    nutrition: RecipeNutritionIn | None = None
    food_safety_ids: list[int] = Field(default_factory=list)


class RecipeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: RecipeCategory | None = None
    description: str | None = None
    servings: int | None = Field(default=None, ge=1, le=100)
    cooking_time_min: int | None = Field(default=None, ge=1, le=600)
    steps: list[str] | None = None
    tags: list[str] | None = None
    image_url: str | None = Field(default=None, max_length=255)
    image_file_id: str | None = Field(default=None, max_length=120)
    image_key: str | None = Field(default=None, max_length=50)
    image_alt: str | None = Field(default=None, max_length=255)
    is_local: bool | None = None
    in_season: bool | None = None
    is_vegetarian: bool | None = None
    estimated_cost: float | None = Field(default=None, ge=0)
    meal_kind: Literal['hidangan', 'komponen'] | None = None
    ingredients: list[RecipeIngredientIn] | None = None
    nutrition: RecipeNutritionIn | None = None
    food_safety_ids: list[int] | None = None


class RecipeFoodSafetyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic: str
    verification: str


class RecipeOut(RecipeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nutrition: RecipeNutritionIn | None = None
    ingredients: list[RecipeIngredientOut] = Field(default_factory=list)
    food_safety: list[RecipeFoodSafetyOut] = Field(default_factory=list)
    price_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# Musim
# --------------------------------------------------------------------------
class SeasonalBase(BaseModel):
    ingredient_id: int
    month: int = Field(ge=1, le=12)
    status: SeasonalStatus = SeasonalStatus.IN_SEASON


class SeasonalCreate(SeasonalBase):
    pass


class SeasonalUpdate(BaseModel):
    ingredient_id: int | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    status: SeasonalStatus | None = None


class SeasonalOut(SeasonalBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# --------------------------------------------------------------------------
# Komoditas lokal
# --------------------------------------------------------------------------
class LocalBase(BaseModel):
    ingredient_id: int
    region_id: int
    level: LocalLevel = LocalLevel.AVAILABLE
    source: str | None = Field(default=None, max_length=150)


class LocalCreate(LocalBase):
    pass


class LocalUpdate(BaseModel):
    ingredient_id: int | None = None
    region_id: int | None = None
    level: LocalLevel | None = None
    source: str | None = Field(default=None, max_length=150)


class LocalOut(LocalBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# --------------------------------------------------------------------------
# Tabel gabungan bahan + gizi + harga untuk dasbor admin
# --------------------------------------------------------------------------
class NutritionGridRow(BaseModel):
    """Satu baris tabel admin: bahan, gizinya, harga, dan pemakaian di menu."""

    ingredient_id: int
    code: str | None = None
    name: str
    category: str
    unit: str
    mbg_slot: str | None = None
    allergens: list[str] = Field(default_factory=list)
    is_local: bool = False
    used_in_menus: int = 0
    price_per_kg: float | None = None
    price_source: str | None = None
    price_status: str | None = None
    nutrition: NutritionFactIn | None = None


class NutritionGridUpdate(BaseModel):
    """Simpan satu baris: identitas bahan, gizi, dan harga sekaligus."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: IngredientCategory | None = None
    unit: str | None = Field(default=None, max_length=20)
    mbg_slot: MbgSlot | None = None
    allergens: list[str] | None = Field(default=None, max_length=10)
    nutrition: NutritionFactIn | None = None
    price_per_kg: float | None = Field(default=None, gt=0, le=10_000_000)
