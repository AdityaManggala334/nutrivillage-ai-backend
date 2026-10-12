"""Skema Pydantic untuk riwayat & favorit (FR-04)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import HistoryKind
from app.schemas.master import RecipeOut


class HistoryCreate(BaseModel):
    recipe_id: int
    kind: HistoryKind = HistoryKind.RECOMMENDATION
    note: str = Field(default="", max_length=255)


class HistoryFavoriteIn(BaseModel):
    favorite: bool


class HistoryEntryOut(BaseModel):
    id: int
    kind: HistoryKind
    note: str
    saved_at: datetime
    favorite: bool
    recipe: RecipeOut | None = None
