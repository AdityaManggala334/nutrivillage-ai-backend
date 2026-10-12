"""Skema Pydantic untuk sekolah & kelompok penerima manfaat (FR-11)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.beneficiary_group import BeneficiaryLevel


class BeneficiaryGroupBase(BaseModel):
    level: BeneficiaryLevel
    label: str | None = Field(default=None, max_length=100)
    student_count: int = Field(ge=0, le=100_000)
    budget_per_portion: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _require_label_for_lainnya(self) -> "BeneficiaryGroupBase":
        if self.level == BeneficiaryLevel.LAINNYA and not (self.label or "").strip():
            raise ValueError("Label wajib diisi untuk kelompok 'lainnya'.")
        return self


class BeneficiaryGroupCreate(BeneficiaryGroupBase):
    pass


class BeneficiaryGroupUpdate(BaseModel):
    level: BeneficiaryLevel | None = None
    label: str | None = Field(default=None, max_length=100)
    student_count: int | None = Field(default=None, ge=0, le=100_000)
    budget_per_portion: float | None = Field(default=None, ge=0)


class BeneficiaryGroupOut(BeneficiaryGroupBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int


class SchoolBase(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    npsn: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=255)
    region: str = Field(min_length=3, max_length=100)
    is_active: bool = True


class SchoolCreate(SchoolBase):
    groups: list[BeneficiaryGroupCreate] = Field(default_factory=list)


class SchoolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=150)
    npsn: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=255)
    region: str | None = Field(default=None, min_length=3, max_length=100)
    is_active: bool | None = None


class SchoolOut(SchoolBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sppg_officer_id: int
    officer_name: str | None = None
    groups: list[BeneficiaryGroupOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
