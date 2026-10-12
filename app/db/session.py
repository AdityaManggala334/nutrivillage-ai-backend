"""Engine, session, dan Base SQLAlchemy 2.0 ke MySQL/MariaDB.

Mendukung MySQL lokal (tanpa TLS) maupun database terkelola seperti TiDB Cloud
yang mewajibkan TLS. Konfigurasi TLS diambil dari environment:

    DATABASE_SSL_CA      = ISI file CA (PEM) atau path ke file .pem
    DATABASE_SSL_VERIFY  = "true"/"false" (default true)
"""

from __future__ import annotations

import ssl
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

_CA_TEMP_PATH = Path("/tmp/nutrivillage-db-ca.pem")


def _resolve_ca_path(value: str) -> str:
    """Kembalikan path file CA. Terima isi PEM atau path yang sudah ada."""
    text = value.strip()
    if text.startswith("-----BEGIN"):
        _CA_TEMP_PATH.write_text(text, encoding="utf-8")
        return str(_CA_TEMP_PATH)
    return text


def build_connect_args() -> dict[str, object]:
    """connect_args untuk PyMySQL; menambahkan TLS bila DATABASE_SSL_CA diisi."""
    if not settings.database_ssl_ca.strip():
        return {}

    ca_path = _resolve_ca_path(settings.database_ssl_ca)
    context = ssl.create_default_context(cafile=ca_path)
    if not settings.database_ssl_verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return {"ssl": context}


def create_db_engine() -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=280,
        connect_args=build_connect_args(),
        echo=False,
    )


engine = create_db_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
