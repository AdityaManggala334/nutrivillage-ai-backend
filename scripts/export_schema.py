"""Ekspor DDL skema lengkap ke `db/schema.sql` (dialek MySQL 8).

Dijalankan manual setelah model berubah:

    python scripts/export_schema.py

Catatan: pada runtime, tabel tetap dibuat oleh SQLAlchemy `create_all`
(lihat `scripts/init_db.py`). File ini untuk dokumentasi/referensi.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.models  # noqa: E402,F401  (daftarkan semua tabel ke metadata)
from sqlalchemy.dialects import mysql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from app.db.session import Base  # noqa: E402

_HEADER = """-- NutriVillage AI — Skema Basis Data (MySQL 8 / TiDB)
--
-- DIHASILKAN OTOMATIS dari model SQLAlchemy (scripts/export_schema.py).
-- Jangan diedit manual; ubah model di app/models/ lalu jalankan ulang skrip.
--
-- Sumber acuan: SKPL V4 Final (PDM Tabel 6.3-6.24) + ekstensi aplikasi web.
"""


def main() -> None:
    dialect = mysql.dialect()
    chunks: list[str] = [_HEADER]
    for table in Base.metadata.sorted_tables:
        chunks.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
        for index in table.indexes:
            chunks.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";")

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "schema.sql"
    )
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write("\n\n".join(chunks) + "\n")
    print(f"[schema] ditulis: {out_path} ({len(Base.metadata.tables)} tabel)")


if __name__ == "__main__":
    main()
