"""Model konten publik & notifikasi & informasi keamanan pangan.

Tidak ada di PDM SKPL V4, ditambahkan sesuai kebutuhan website:
artikel gizi (FR-03), notifikasi (FR-21), dan informasi keamanan pangan.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import (
    ArticleCategory,
    FoodSafetyVerification,
    NotificationKind,
    enum_column,
)


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    excerpt: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[ArticleCategory] = mapped_column(
        enum_column(ArticleCategory, "article_category"), nullable=False
    )
    read_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    body: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    # NULL = notifikasi global untuk semua pengguna.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[NotificationKind] = mapped_column(
        enum_column(NotificationKind, "notification_kind"), nullable=False, server_default="info"
    )
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class FoodSafetyInfo(Base):
    __tablename__ = "food_safety_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_type: Mapped[str] = mapped_column(String(100), nullable=False)
    hazard: Mapped[str] = mapped_column(Text, nullable=False)
    handling: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(150), nullable=False)
    verification: Mapped[FoodSafetyVerification] = mapped_column(
        enum_column(FoodSafetyVerification, "food_safety_verification"),
        nullable=False,
        server_default="pending",
    )
