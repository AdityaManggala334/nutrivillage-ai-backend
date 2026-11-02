"""Acuan gizi nasional yang dapat disunting admin.

Dua tabel rujukan yang sebelumnya hanya hidup di notebook:

* ``nutrition_standards`` — AKG Permenkes 28/2019 (target energi/protein/mikro
  dan tinggi-berat acuan per kelompok umur & jenis kelamin).
* ``anthropometry_standards`` — titik z-score Permenkes 2/2020, dipakai untuk
  menilai status gizi anak (stunting/gizi kurang/wasting).

Keduanya bersifat acuan, bukan transaksi: mesin rekomendasi membacanya setiap
kali menjalankan hitungan, sehingga koreksi admin langsung terasa pada
rekomendasi berikutnya.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class NutritionStandard(Base):
    """Satu baris = satu kelompok AKG (Tabel acuan Permenkes 28/2019)."""

    __tablename__ = "nutrition_standards"
    __table_args__ = (
        UniqueConstraint("age_group", "sex", "physiology", name="uq_nutrition_standard"),
        Index("ix_nutrition_standard_lookup", "age_group", "sex"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    age_group: Mapped[str] = mapped_column(String(30), nullable=False)
    sex: Mapped[str] = mapped_column(String(12), nullable=False, server_default="Semua")
    physiology: Mapped[str] = mapped_column(String(20), nullable=False, server_default="Normal")
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    energy_kcal: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False)
    protein_g: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False)
    fat_g: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False, server_default="0")
    carb_g: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False, server_default="0")
    fiber_g: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False, server_default="0")
    calcium_mg: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, server_default="0")
    iron_mg: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False, server_default="0")
    vitamin_a_mcg: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, server_default="0")
    vitamin_c_mg: Mapped[float] = mapped_column(Numeric(6, 1), nullable=False, server_default="0")
    sodium_mg: Mapped[float] = mapped_column(Numeric(8, 1), nullable=False, server_default="0")
    source: Mapped[str] = mapped_column(
        String(150), nullable=False, server_default="Permenkes 28/2019"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NutritionStandard {self.code} {self.age_group}/{self.sex}>"


class AnthropometryStandard(Base):
    """Titik z-score antropometri anak (Permenkes 2/2020).

    Satu baris = satu umur (bulan) untuk kombinasi indeks & jenis kelamin,
    berisi nilai pada -3 SD s.d. +3 SD. Mesin menghitung z-score dengan
    interpolasi linear antar titik ini.
    """

    __tablename__ = "anthropometry_standards"
    __table_args__ = (
        UniqueConstraint("index_name", "sex", "age_month", name="uq_anthro_point"),
        Index("ix_anthro_lookup", "index_name", "sex", "age_month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index_name: Mapped[str] = mapped_column(String(10), nullable=False)
    sex: Mapped[str] = mapped_column(String(2), nullable=False)
    age_month: Mapped[int] = mapped_column(Numeric(6, 1), nullable=False)
    minus3sd: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    minus2sd: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    minus1sd: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    median: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    plus1sd: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    plus2sd: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    plus3sd: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    source: Mapped[str] = mapped_column(
        String(150), nullable=False, server_default="Permenkes 2/2020"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AnthropometryStandard {self.index_name}/{self.sex} {self.age_month}bln>"
