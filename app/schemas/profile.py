"""Skema Pydantic untuk profil keluarga (FR-02)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActivityLevel, AgeGroup, Gender


class FamilyMemberIn(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    age: int = Field(ge=1, le=120)
    age_group: AgeGroup | None = None
    gender: Gender | None = None
    weight_kg: float = Field(gt=0, le=250)
    activity_level: ActivityLevel = ActivityLevel.SEDANG
    allergies: list[str] = Field(default_factory=list)


class FamilyMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None
    age: int
    age_group: AgeGroup | None = None
    gender: Gender | None = None
    weight_kg: float
    activity_level: ActivityLevel
    allergies: list[str] = Field(default_factory=list)


class FamilyProfileIn(BaseModel):
    daily_budget: float = Field(gt=0)
    region: str = Field(min_length=1, max_length=100)
    preferences: list[str] = Field(default_factory=list)
    avoided_ingredients: list[str] = Field(default_factory=list)
    onboarded: bool = True
    members: list[FamilyMemberIn] = Field(min_length=1)


class FamilyProfileOut(BaseModel):
    user_id: int
    daily_budget: float
    region: str
    preferences: list[str]
    avoided_ingredients: list[str]
    onboarded: bool
    family_count: int
    members: list[FamilyMemberOut]
    updated_at: datetime
