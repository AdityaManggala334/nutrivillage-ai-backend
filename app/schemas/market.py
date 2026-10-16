"""Skema Pydantic untuk harga pangan & monitoring scraper (FR-23, FR-31)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    PriceSourceType,
    PriceStatus,
    ScraperStatus,
)


# --------------------------------------------------------------------------
# Harga pangan
# --------------------------------------------------------------------------
class PriceCreate(BaseModel):
    ingredient_id: int
    price: float = Field(gt=0)
    unit: str = Field(default="kg", max_length=20)
    recorded_date: date | None = None
    source_type: PriceSourceType = PriceSourceType.MANUAL
    source: str = Field(min_length=2, max_length=150)
    region_id: int | None = None
    status: PriceStatus = PriceStatus.PENDING


class PriceUpdate(BaseModel):
    price: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=20)
    source: str | None = Field(default=None, min_length=2, max_length=150)
    status: PriceStatus | None = None


class PriceVerifyRequest(BaseModel):
    status: PriceStatus
    note: str | None = Field(default=None, max_length=255)


class PriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ingredient_id: int
    ingredient_name: str = ""
    region_id: int | None = None
    price: float
    unit: str
    recorded_date: date
    source_type: PriceSourceType
    source: str
    status: PriceStatus
    created_at: datetime


# --------------------------------------------------------------------------
# Log scraper
# --------------------------------------------------------------------------
class ScraperRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: ScraperStatus
    items_count: int
    error_message: str | None = None


class ScraperRunCreate(BaseModel):
    source: str = Field(min_length=2, max_length=150)
    status: ScraperStatus = ScraperStatus.SUCCESS
    items_count: int = Field(default=0, ge=0)
    error_message: str | None = None


# --------------------------------------------------------------------------
# Statistik dashboard admin (dihitung dari database)
# --------------------------------------------------------------------------
class AdminStatsOut(BaseModel):
    ingredients: int = 0
    recipes: int = 0
    pending_prices: int = 0
    approved_prices: int = 0
    users: int = 0
    scraper_failures: int = 0
