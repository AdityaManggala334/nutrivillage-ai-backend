"""Skema Pydantic untuk CRUD data master admin.

Mencakup: bahan pangan (ingredients), nutrisi (nutrition_facts),
menu/resep (recipes + komposisi + gizi), musim (seasonal_availability),
dan komoditas lokal (local_availability).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    IngredientCategory,
    LocalLevel,
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


class IngredientCreate(IngredientBase):
    pass


class IngredientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: IngredientCategory | None = None
    unit: str | None = Field(default=None, max_length=20)
    description: str | None = None
    is_local: bool | None = None
    is_in_season: bool | None = None


class IngredientOut(IngredientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# Nutrisi bahan
# --------------------------------------------------------------------------
class NutritionFactIn(BaseModel):
    calories: float = Field(default=0, ge=0)
    protein: float = Field(default=0, ge=0)
    carbs: float = Field(default=0, ge=0)
    fat: float = Field(default=0, ge=0)
    fiber: float = Field(default=0, ge=0)
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
    image_key: str | None = Field(default=None, max_length=50)
    image_alt: str | None = Field(default=None, max_length=255)
    is_local: bool = False
    in_season: bool = False
    is_vegetarian: bool = False
    estimated_cost: float = Field(default=0, ge=0)


class RecipeCreate(RecipeBase):
    ingredients: list[RecipeIngredientIn] = Field(default_factory=list)
    nutrition: RecipeNutritionIn | None = None


class RecipeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: RecipeCategory | None = None
    description: str | None = None
    servings: int | None = Field(default=None, ge=1, le=100)
    cooking_time_min: int | None = Field(default=None, ge=1, le=600)
    steps: list[str] | None = None
    tags: list[str] | None = None
    image_key: str | None = Field(default=None, max_length=50)
    image_alt: str | None = Field(default=None, max_length=255)
    is_local: bool | None = None
    in_season: bool | None = None
    is_vegetarian: bool | None = None
    estimated_cost: float | None = Field(default=None, ge=0)
    ingredients: list[RecipeIngredientIn] | None = None
    nutrition: RecipeNutritionIn | None = None


class RecipeOut(RecipeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nutrition: RecipeNutritionIn | None = None
    ingredients: list[RecipeIngredientOut] = Field(default_factory=list)
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
