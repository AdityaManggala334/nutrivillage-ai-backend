"""Pengosongan data aplikasi (baris), tanpa menyentuh skema.

Dipakai oleh `scripts/reset_data.py` (CLI) dan `scripts/init_db.py`
(saklar env `RESET_DATA`).

Yang dipertahankan:
- `users` berperan admin      -> panel admin tetap bisa dibuka
- `sppg_officers` milik admin
- `system_config`             -> bobot skoring SAW (tanpa form admin)
- `regions`                   -> acuan wilayah (dropdown & komoditas lokal)
- `budget_policies`           -> kerangka kebijakan (angka masih NULL)
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Tabel yang tidak boleh dikosongkan.
KEEP_TABLES = {"system_config", "budget_policies", "regions", "users", "sppg_officers"}

DELETE_OFFICERS_SQL = (
    "DELETE FROM sppg_officers "
    "WHERE user_id NOT IN (SELECT id FROM users WHERE role = 'admin')"
)
DELETE_NON_ADMIN_USERS_SQL = "DELETE FROM users WHERE role <> 'admin'"


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar_one())


def table_names_to_clear(all_tables: Iterable[str]) -> list[str]:
    """Urutan anak-ke-induk agar aman untuk mesin yang menegakkan FK."""
    names = [name for name in all_tables if name not in KEEP_TABLES]
    return names


def reset_data(engine: Engine, tables: list[str], *, assume_yes: bool) -> int:
    """Hapus seluruh baris pada `tables` + akun non-admin. Mengembalikan total."""
    if not assume_yes:
        preview = ", ".join(tables)
        answer = input(
            f"Siap mengosongkan {len(tables)} tabel?\n  {preview}\n\n"
            "Ketik 'ya' untuk melanjutkan: "
        )
        if answer.strip().lower() not in {"ya", "y", "yes"}:
            print("[reset] dibatalkan.")
            return 0

    total = 0
    with engine.connect() as conn:
        # Matikan pemeriksaan FK sementara (MySQL lokal); TiDB menoleransi.
        try:
            conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        except Exception:  # noqa: BLE001
            pass

        for table in tables:
            count = _count(engine, table)
            conn.execute(text(f"DELETE FROM `{table}`"))
            if count:
                print(f"[reset] {table}: {count} baris dihapus")
                total += count

        for statement in (DELETE_OFFICERS_SQL, DELETE_NON_ADMIN_USERS_SQL):
            result = conn.execute(text(statement))
            if result.rowcount:
                print(f"[reset] akun non-admin: {result.rowcount} baris dihapus")
                total += result.rowcount

        conn.commit()
        try:
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        except Exception:  # noqa: BLE001
            pass

    print(f"[reset] selesai — {total} baris dihapus.")
    print("[reset] dipertahankan: admin, system_config, regions, budget_policies.")
    return total
