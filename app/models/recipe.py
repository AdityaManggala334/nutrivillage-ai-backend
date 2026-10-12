"""Model resep/menu, gizi per resep, dan komposisi bahan.

Mengacu SKPL V4 Final Tabel 6.12 (recipes), 6.13 (recipe_ingredients),
plus ekstensi website: `recipe_nutrition`, biaya, tag, dan atribut tampilan.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import RecipeCategory, enum_column

if TYPE_CHECKING:
    from app.models.catalog import Ingredient


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Kode asli frontend (mis. "resep-nasi-pecel") untuk pencocokan seed.
    code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[RecipeCategory] = mapped_column(
        enum_column(RecipeCategory, "recipe_category"),
        nullable=False,
        server_default="Makanan Utama",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    servings: Mapped[int] = mapped_column(Integer, nullable=False, server_default="4")
    cooking_time_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_vegetarian: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0"
    )
    # --- Ekstensi website ---
    estimated_cost: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    image_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    image_alt: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_local: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    in_season: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    price_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    nutrition: Mapped["RecipeNutrition | None"] = relationship(
        back_populates="recipe", uselist=False, cascade="all, delete-orphan"
    )
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Recipe id={self.id} name={self.name!r}>"


class RecipeNutrition(Base):
    """Kandungan gizi per resep (ekstensi website)."""

    __tablename__ = "recipe_nutrition"

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    calories: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, server_default="0")
    protein: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, server_default="0")
    carbohydrates: Mapped[float] = mapped_column(
        Numeric(8, 1), nullable=False, server_default="0"
    )
    fat: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, server_default="0")
    fiber: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, server_default="0")

    recipe: Mapped["Recipe"] = relationship(back_populates="nutrition")


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredient"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Nama bahan disimpan juga agar tetap terbaca bila ingredient_id NULL.
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, server_default="kg")
    estimated_price: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    is_pantry: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    note: Mapped[str | None] = mapped_column(String(100), nullable=True)

    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")
    ingredient: Mapped["Ingredient | None"] = relationship()
