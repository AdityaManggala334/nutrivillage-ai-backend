"""Model profil keluarga & anggota keluarga.

Mengacu SKPL V4 Final:
- Tabel 6.4 `profiles` — profil keluarga user (1:1 dengan users)
- Tabel 6.5 `family_members` — data tiap anggota keluarga
Plus ekstensi website: `name`, `gender`, `age_group` pada anggota keluarga.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import ActivityLevel, AgeGroup, Gender, enum_column


class FamilyProfile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    daily_budget: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    adults_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    children_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    toddlers_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    elderly_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # Kolom turunan (generated) sesuai SKPL: total anggota keluarga.
    family_count: Mapped[int] = mapped_column(
        Integer,
        Computed(
            "adults_count + children_count + toddlers_count + elderly_count",
            persisted=True,
        ),
        nullable=False,
    )
    region_id: Mapped[int | None] = mapped_column(
        ForeignKey("regions.id", ondelete="SET NULL"), nullable=True
    )
    preferences: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    avoided_ingredients: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Ekstensi website: sakelar notifikasi pengguna (FR-21).
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="1"
    )
    onboarded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FamilyProfile user_id={self.user_id} family_count={self.family_count}>"


class FamilyMember(Base):
    __tablename__ = "family_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Ekstensi website: nama anggota.
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    # Ekstensi website: kelompok usia & jenis kelamin.
    age_group: Mapped[AgeGroup | None] = mapped_column(
        enum_column(AgeGroup, "age_group"), nullable=True
    )
    gender: Mapped[Gender | None] = mapped_column(
        enum_column(Gender, "gender"), nullable=True
    )
    weight_kg: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    activity_level: Mapped[ActivityLevel] = mapped_column(
        enum_column(ActivityLevel, "activity_level"),
        nullable=False,
        server_default="sedang",
    )
    # SKPL: VARCHAR(255). Nilai ganda disimpan dipisah koma.
    allergies: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FamilyMember id={self.id} user_id={self.user_id} age={self.age}>"
