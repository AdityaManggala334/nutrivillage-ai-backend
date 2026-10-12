"""Skema Pydantic untuk kebijakan anggaran bahan pangan per porsi."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class BudgetPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scope: str
    label: str
    amount_per_portion: float | None
    source: str | None
    verified: bool
    effective_date: date | None


class BudgetPolicyUpdate(BaseModel):
    amount_per_portion: float | None = Field(default=None, ge=0)
    source: str | None = Field(default=None, max_length=255)
    verified: bool | None = None
    effective_date: date | None = None
