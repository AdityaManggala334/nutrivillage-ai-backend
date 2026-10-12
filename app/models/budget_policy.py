"""Model tabel `budget_policies` — batas anggaran bahan pangan per porsi.

Nilai anggaran disimpan sebagai konfigurasi yang dapat diperbarui admin.
`amount_per_portion` boleh NULL: kondisi ini berarti batas anggaran **belum
dikonfigurasi/diverifikasi**, sehingga UI menampilkan status tersebut alih-alih
mengarang angka.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BudgetPolicy(Base):
    __tablename__ = "budget_policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Cakupan kebijakan: "global" atau "level:<beneficiary_level>".
    scope: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    amount_per_portion: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    def __repr__(self) -> str:  # pragma: no cover - bantu debugging
        return f"<BudgetPolicy scope={self.scope!r} amount={self.amount_per_portion}>"
