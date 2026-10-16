"""Skema Pydantic untuk konten publik & keamanan pangan.

Mencakup artikel gizi (FR-03), notifikasi (FR-21), dan informasi keamanan
pangan yang diverifikasi admin (FR-29).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ArticleCategory,
    FoodSafetyVerification,
    NotificationKind,
)


# --------------------------------------------------------------------------
# Artikel gizi
# --------------------------------------------------------------------------
class ArticleBase(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    excerpt: str = Field(min_length=3, max_length=255)
    category: ArticleCategory
    read_minutes: int = Field(default=3, ge=1, le=120)
    body: list[str] = Field(default_factory=list)


class ArticleCreate(ArticleBase):
    code: str | None = Field(default=None, max_length=64)


class ArticleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    excerpt: str | None = Field(default=None, min_length=3, max_length=255)
    category: ArticleCategory | None = None
    read_minutes: int | None = Field(default=None, ge=1, le=120)
    body: list[str] | None = None


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str | None = None
    title: str
    excerpt: str
    category: ArticleCategory
    read_minutes: int
    body: list[str]
    created_at: datetime


# --------------------------------------------------------------------------
# Notifikasi
# --------------------------------------------------------------------------
class NotificationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    message: str = Field(min_length=3, max_length=500)
    kind: NotificationKind = NotificationKind.INFO
    user_id: int | None = None
    code: str | None = Field(default=None, max_length=64)


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    title: str
    message: str
    kind: NotificationKind
    read: bool
    created_at: datetime


# --------------------------------------------------------------------------
# Informasi keamanan pangan
# --------------------------------------------------------------------------
class FoodSafetyBase(BaseModel):
    topic: str = Field(min_length=2, max_length=100)
    risk_type: str = Field(min_length=2, max_length=100)
    hazard: str = Field(min_length=3)
    handling: str = Field(min_length=3)
    source: str = Field(min_length=2, max_length=150)
    verification: FoodSafetyVerification = FoodSafetyVerification.PENDING


class FoodSafetyCreate(FoodSafetyBase):
    code: str | None = Field(default=None, max_length=64)


class FoodSafetyUpdate(BaseModel):
    topic: str | None = Field(default=None, min_length=2, max_length=100)
    risk_type: str | None = Field(default=None, min_length=2, max_length=100)
    hazard: str | None = Field(default=None, min_length=3)
    handling: str | None = Field(default=None, min_length=3)
    source: str | None = Field(default=None, min_length=2, max_length=150)
    verification: FoodSafetyVerification | None = None


class FoodSafetyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str | None = None
    topic: str
    risk_type: str
    hazard: str
    handling: str
    source: str
    verification: FoodSafetyVerification
