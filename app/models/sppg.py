"""Model tabel `sppg_officers` — profil petugas SPPG MBG (1:1 dengan users)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.user import User


class SppgOfficer(Base):
    __tablename__ = "sppg_officers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    nip: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    sppg_unit: Mapped[str] = mapped_column(String(150), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    user: Mapped["User"] = relationship(back_populates="sppg_officer")
    schools: Mapped[list["School"]] = relationship(
        back_populates="officer",
        cascade="all, delete-orphan",
        order_by="School.id",
    )

    def __repr__(self) -> str:  # pragma: no cover - bantu debugging
        return f"<SppgOfficer id={self.id} nip={self.nip!r} unit={self.sppg_unit!r}>"
