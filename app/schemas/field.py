"""Skema input harga lapangan (peran `petugas_lapangan`).

Penting: tidak ada kolom `status` maupun `source_type` di sini. Keduanya
ditetapkan server, sehingga petugas tidak bisa menyetujui catatannya sendiri.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class FieldPriceCreate(BaseModel):
    ingredient_id: int = Field(gt=0)
    price: float = Field(gt=0, le=100_000_000)
    unit: str = Field(default="kg", min_length=1, max_length=20)
    recorded_date: date | None = None
    source: str = Field(min_length=2, max_length=150, description="mis. Pasar Besar Madiun")
    region_id: int | None = Field(default=None, gt=0)


class FieldPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ingredient_id: int
    price: float
    unit: str
    recorded_date: date
    source: str
    status: str
    created_at: datetime
    ingredient_name: str = ""
    region_id: int | None = None
    created_by: int | None = None


class FieldIngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    unit: str
    category: str
