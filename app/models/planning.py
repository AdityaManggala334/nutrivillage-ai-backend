"""Model rekomendasi (SAW), meal planner, shopping list, favorit, config.

Mengacu SKPL V4 Final:
- Tabel 6.16 recommendations, 6.17 recommendation_items
- Tabel 6.18 shopping_lists, 6.19 shopping_list_items
- Tabel 6.21 llm_explanations
- Tabel 6.22 system_config (bobot skoring)
- Tabel 6.23 favorites, 6.24 meal_plans
Plus ekstensi website: `week_id`/`note` pada meal planner, `meal_plan_id`
pada shopping list.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import DayOfWeek, MealType, enum_column


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    budget: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    family_count: Mapped[int] = mapped_column(Integer, nullable=False)
    region_id: Mapped[int | None] = mapped_column(
        ForeignKey("regions.id", ondelete="SET NULL"), nullable=True
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="completed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    items: Mapped[list["RecommendationItem"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan", lazy="selectin"
    )


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    score_nutrition: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    score_budget: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    score_seasonal: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    score_local: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    score_total: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    estimated_cost: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")

    recommendation: Mapped["Recommendation"] = relationship(back_populates="items")


class LlmExplanation(Base):
    __tablename__ = "llm_explanations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recommendation_id: Mapped[int | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=True
    )
    explanation_text: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Ekstensi website: daftar belanja hasil generate dari Meal Planner.
    meal_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("meal_plans.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(
        String(150), nullable=False, server_default="Belanja hari ini"
    )
    total_estimate: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    items: Mapped[list["ShoppingListItem"]] = relationship(
        back_populates="shopping_list", cascade="all, delete-orphan", lazy="selectin"
    )


class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    list_id: Mapped[int] = mapped_column(
        ForeignKey("shopping_lists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, server_default="1")
    unit: Mapped[str] = mapped_column(String(20), nullable=False, server_default="kg")
    estimated_price: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    checked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")

    shopping_list: Mapped["ShoppingList"] = relationship(back_populates="items")


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class MealPlan(Base):
    __tablename__ = "meal_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )
    day_of_week: Mapped[DayOfWeek] = mapped_column(
        enum_column(DayOfWeek, "day_of_week"), nullable=False
    )
    meal_type: Mapped[MealType] = mapped_column(
        enum_column(MealType, "meal_type"), nullable=False
    )
    # --- Ekstensi website ---
    week_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class SystemConfig(Base):
    """Konfigurasi sistem — bobot skoring SAW (dikelola admin)."""

    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    config_value: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
