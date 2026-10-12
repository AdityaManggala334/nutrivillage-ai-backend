"""Model wilayah, bahan pangan, gizi, dan ketersediaan.

Mengacu SKPL V4 Final Tabel 6.6 (regions), 6.7 (ingredients),
6.8 (nutrition_facts), 6.14 (seasonal_availability), 6.15 (local_availability).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import IngredientCategory, LocalLevel, SeasonalStatus, enum_column

if TYPE_CHECKING:
    from app.models.recipe import RecipeIngredient


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    province: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="Jawa Timur"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Region id={self.id} name={self.name!r}>"


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Kode asli dari frontend (mis. "bahan-beras") untuk pencocokan seed.
    code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[IngredientCategory] = mapped_column(
        enum_column(IngredientCategory, "ingredient_category"), nullable=False
    )
    unit: Mapped[str] = mapped_column(String(20), nullable=False, server_default="kg")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Ekstensi website: penanda pangan lokal & musim (dipakai admin & Explore).
    is_local: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    is_in_season: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    nutrition: Mapped["NutritionFact | None"] = relationship(
        back_populates="ingredient", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Ingredient id={self.id} name={self.name!r}>"


class NutritionFact(Base):
    """Kandungan gizi per 100 g bahan (master TKPI Kemenkes RI)."""

    __tablename__ = "nutrition_facts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    calories: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, server_default="0")
    protein: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, server_default="0")
    carbs: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, server_default="0")
    fat: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, server_default="0")
    fiber: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, server_default="0")
    source: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="TKPI Kemenkes RI"
    )

    ingredient: Mapped["Ingredient"] = relationship(back_populates="nutrition")


class SeasonalAvailability(Base):
    __tablename__ = "seasonal_availability"
    __table_args__ = (UniqueConstraint("ingredient_id", "month", name="uq_seasonal_ingredient_month"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SeasonalStatus] = mapped_column(
        enum_column(SeasonalStatus, "seasonal_status"),
        nullable=False,
        server_default="in_season",
    )


class LocalAvailability(Base):
    __tablename__ = "local_availability"
    __table_args__ = (UniqueConstraint("ingredient_id", "region_id", name="uq_local_ingredient_region"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[LocalLevel] = mapped_column(
        enum_column(LocalLevel, "local_level"), nullable=False, server_default="available"
    )
    source: Mapped[str | None] = mapped_column(String(150), nullable=True)
