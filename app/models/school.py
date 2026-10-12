"""Model tabel `schools` — sekolah yang dikelola seorang petugas SPPG MBG.

Satu petugas (`sppg_officers`) dapat mengelola banyak sekolah (relasi 1:N).
Setiap sekolah memiliki beberapa kelompok penerima manfaat
(`beneficiary_groups`).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.beneficiary_group import BeneficiaryGroup
    from app.models.sppg import SppgOfficer


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sppg_officer_id: Mapped[int] = mapped_column(
        ForeignKey("sppg_officers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    npsn: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    officer: Mapped["SppgOfficer"] = relationship(back_populates="schools")
    groups: Mapped[list["BeneficiaryGroup"]] = relationship(
        back_populates="school",
        cascade="all, delete-orphan",
        order_by="BeneficiaryGroup.id",
    )

    @property
    def officer_name(self) -> str | None:
        """Nama petugas pemilik (untuk tampilan admin)."""
        officer = self.officer
        return officer.user.name if officer and officer.user else None

    def __repr__(self) -> str:  # pragma: no cover - bantu debugging
        return f"<School id={self.id} name={self.name!r}>"
