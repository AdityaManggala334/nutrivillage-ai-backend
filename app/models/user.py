"""Model tabel `users` — akun pengguna, petugas SPPG, admin, dan tamu."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.sppg import SppgOfficer


class UserRole(str, Enum):
    """Peran (RBAC).

    - user          : masyarakat umum (pengguna akhir).
    - petugas_sppg  : petugas SPPG MBG (Makan Bergizi Gratis).
    - admin         : pengelola data master & verifikasi harga.
    - guest         : akses terbatas tanpa registrasi.
    """

    USER = "user"
    PETUGAS_SPPG = "petugas_sppg"
    ADMIN = "admin"
    GUEST = "guest"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(
        String(150), nullable=False, unique=True, index=True
    )
    # Ekstensi website: nomor telepon kontak pengguna (opsional).
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=UserRole.USER,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    sppg_officer: Mapped["SppgOfficer | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - bantu debugging
        return f"<User id={self.id} email={self.email!r} role={self.role.value!r}>"
