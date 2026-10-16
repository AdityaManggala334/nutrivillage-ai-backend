"""Kosongkan data aplikasi (bukan skema) — produksi diisi ulang lewat admin.

    python scripts/reset_data.py --yes

Yang DIHAPUS:
- data katalog   : ingredients, nutrition_facts, recipes (+gizi/komposisi),
                   prices (+verifikasi/histori), seasonal_availability,
                   local_availability, scraper_runs
- konten         : articles, notifications, food_safety_info
- data pengguna  : profiles, family_members, history_entries, favorites,
                   meal_plans, shopping_lists (+items), recommendations
                  (+items, llm_explanations), history_entries
- organisasi     : schools, beneficiary_groups
- seluruh akun TANPA peran admin

Yang DIPERTAHANKAN:
- `users` berperan admin      -> panel admin tetap bisa dibuka
- `system_config`             -> bobot skoring SAW (tidak ada form adminnya)
- `regions`                   -> acuan wilayah untuk dropdown & komoditas lokal
- `budget_policies`           -> kerangka kebijakan (angka masih NULL)
- `sppg_officers` milik admin

Catatan: skrip ini hanya menghapus BARIS. Skema/kolom tetap utuh.

Alternatif tanpa kredensial lokal: set env `RESET_DATA=1` di Render lalu
restart service; `scripts/init_db.py` akan menjalankan pengosongan yang sama.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.models  # noqa: E402,F401  (daftarkan seluruh tabel ke metadata)
from sqlalchemy import text  # noqa: E402

from app.db.reset import reset_data, table_names_to_clear  # noqa: E402
from app.db.session import Base, engine  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Kosongkan data aplikasi NutriVillage AI.")
    parser.add_argument(
        "--yes", "-y", action="store_true", help="lewati konfirmasi interaktif"
    )
    args = parser.parse_args()

    tables = table_names_to_clear(t.name for t in Base.metadata.sorted_tables)
    # sorted_tables = induk -> anak; dibalik agar anak (FK) dihapus lebih dulu.
    reset_data(engine, list(reversed(tables)), assume_yes=args.yes)

    with engine.connect() as conn:
        remaining = int(conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one())
    print(f"[reset] akun tersisa: {remaining} (hanya peran admin).")


if __name__ == "__main__":
    main()
