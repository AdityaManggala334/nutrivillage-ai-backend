"""Model tabel `beneficiary_groups` — kelompok penerima manfaat per sekolah.

Kelompok siswa tidak seragam untuk semua sekolah: sebuah sekolah hanya punya
kelompok yang benar-benar relevan (mis. hanya SD kelas 1–3 dan 4–6).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.school import School


class BeneficiaryLevel(str, Enum):
    """Kategori kelompok penerima manfaat yang didukung kebijakan."""

    SD_1_3 = "sd_1_3"
    SD_4_6 = "sd_4_6"
    SMP = "smp"
    SMA = "sma"
    LAINNYA = "lainnya"


class BeneficiaryGroup(Base):
    __tablename__ = "beneficiary_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level: Mapped[BeneficiaryLevel] = mapped_column(
        SAEnum(
            BeneficiaryLevel,
            name="beneficiary_level",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    # Label khusus dipakai bila level == "lainnya".
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    student_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Batas anggaran bahan pangan per porsi (opsional, belum tentu terverifikasi).
    budget_per_portion: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    school: Mapped["School"] = relationship(back_populates="groups")

    def __repr__(self) -> str:  # pragma: no cover - bantu debugging
        return f"<BeneficiaryGroup id={self.id} level={self.level.value!r} n={self.student_count}>"
