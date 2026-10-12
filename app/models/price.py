"""Model harga pangan, verifikasi, histori, dan log scraper.

Mengacu SKPL V4 Final Tabel 6.9 (prices), 6.10 (price_verifications),
6.11 (price_history), 6.20 (scraper_runs).

Catatan: `price_history` bersifat append-only (NFR-06) — aplikasi tidak
menyediakan UPDATE/DELETE.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import (
    PriceSourceType,
    PriceStatus,
    PriceVerificationStatus,
    ScraperStatus,
    enum_column,
)


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (
        Index("ix_prices_lookup", "ingredient_id", "region_id", "recorded_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    region_id: Mapped[int | None] = mapped_column(
        ForeignKey("regions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, server_default="kg")
    recorded_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    source_type: Mapped[PriceSourceType] = mapped_column(
        enum_column(PriceSourceType, "price_source_type"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[PriceStatus] = mapped_column(
        enum_column(PriceStatus, "price_status"), nullable=False, server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Price id={self.id} ingredient_id={self.ingredient_id} price={self.price}>"


class PriceVerification(Base):
    __tablename__ = "price_verifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    price_id: Mapped[int] = mapped_column(
        ForeignKey("prices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[PriceVerificationStatus] = mapped_column(
        enum_column(PriceVerificationStatus, "price_verification_status"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class PriceHistory(Base):
    """Histori harga — append-only."""

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    price_id: Mapped[int | None] = mapped_column(
        ForeignKey("prices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    region_id: Mapped[int | None] = mapped_column(
        ForeignKey("regions.id", ondelete="SET NULL"), nullable=True
    )
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, server_default="kg")
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(150), nullable=False)
    source_type: Mapped[PriceSourceType] = mapped_column(
        enum_column(PriceSourceType, "price_history_source_type"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # new / changed / deleted
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class ScraperRun(Base):
    __tablename__ = "scraper_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(150), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[ScraperStatus] = mapped_column(
        enum_column(ScraperStatus, "scraper_status"), nullable=False, server_default="failed"
    )
    items_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ScraperRun id={self.id} status={self.status.value!r}>"
