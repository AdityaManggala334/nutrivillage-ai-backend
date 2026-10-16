"""Inisialisasi database NutriVillage AI + seed akun demo.

Jalankan dari folder `backend/`:

    python scripts/init_db.py

Skrip akan:
1. Membuat database `nutri_village_ai` (utf8mb4) bila belum ada.
2. Membuat seluruh tabel (SQLAlchemy `create_all`).
3. Menyisipkan akun demo, kebijakan anggaran (belum dikonfigurasi), dan
   contoh sekolah untuk petugas SPPG — idempoten.
"""

from __future__ import annotations

import os
import sys

# Pastikan paket `app` dapat diimpor saat skrip dijalankan langsung.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.seed_catalog import seed_catalog, seed_reference  # noqa: E402
from app.db.session import Base, SessionLocal, build_connect_args, engine  # noqa: E402
from app.models.beneficiary_group import BeneficiaryGroup, BeneficiaryLevel  # noqa: E402
from app.models.budget_policy import BudgetPolicy  # noqa: E402
from app.models.school import School  # noqa: E402
from app.models.sppg import SppgOfficer  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402


def create_database_if_missing() -> None:
    if settings.skip_create_database:
        print("[db] SKIP_CREATE_DATABASE aktif — database dikelola provider.")
        return
    url = make_url(settings.database_url)
    connection = pymysql.connect(
        host=url.host or "127.0.0.1",
        port=url.port or 3306,
        user=url.username or "root",
        password=url.password or "",
        charset="utf8mb4",
        autocommit=True,
        **build_connect_args(),
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{url.database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()
    print(f"[db] database siap: {url.database}")


def _ensure_user(
    db,
    *,
    email: str,
    name: str,
    password: str,
    role: UserRole,
    officer: dict | None = None,
) -> None:
    existing = db.query(User).filter(User.email == email).one_or_none()
    if existing is not None:
        print(f"[seed] dilewati (sudah ada): {email}")
        return
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    if officer:
        user.sppg_officer = SppgOfficer(**officer)
    db.add(user)
    db.commit()
    print(f"[seed] dibuat: {email} ({role.value})")


def seed_demo_users() -> None:
    db = SessionLocal()
    try:
        _ensure_user(
            db,
            email="keluarga@nutrivillage.id",
            name="Keluarga Madiun",
            password="nutrivillage",
            role=UserRole.USER,
        )
        _ensure_user(
            db,
            email="admin@nutrivillage.id",
            name="Admin NutriVillage",
            password="admin12345",
            role=UserRole.ADMIN,
        )
        _ensure_user(
            db,
            email="sppg@nutrivillage.id",
            name="Petugas SPPG Madiun",
            password="sppg12345",
            role=UserRole.PETUGAS_SPPG,
            officer={
                "nip": "197801012006041001",
                "sppg_unit": "SPPG Madiun Kota",
                "region": "Kec. Madiun, Kab. Madiun",
                "position": "Koordinator Gizi",
            },
        )
    finally:
        db.close()


def seed_bootstrap_admin() -> None:
    """Akun admin awal dari env (produksi), dibuat hanya bila belum ada."""
    email = settings.bootstrap_admin_email.strip()
    password = settings.bootstrap_admin_password.strip()
    if not email or not password:
        return
    db = SessionLocal()
    try:
        _ensure_user(
            db,
            email=email,
            name=settings.bootstrap_admin_name.strip() or "Administrator",
            password=password,
            role=UserRole.ADMIN,
        )
    finally:
        db.close()


def seed_budget_policies() -> None:
    """Kebijakan anggaran awal — sengaja KOSONG dan belum diverifikasi.

    Aplikasi tidak mengarang angka anggaran. Admin mengisi nilainya setelah
    diverifikasi dengan ketentuan resmi yang berlaku.
    """
    db = SessionLocal()
    try:
        policies = [
            ("global", "Batas anggaran bahan pangan (default)"),
            ("level:sd_1_3", "SD kelas 1-3"),
            ("level:sd_4_6", "SD kelas 4-6"),
            ("level:smp", "SMP"),
            ("level:sma", "SMA"),
        ]
        for scope, label in policies:
            existing = (
                db.query(BudgetPolicy)
                .filter(BudgetPolicy.scope == scope)
                .one_or_none()
            )
            if existing is not None:
                continue
            db.add(
                BudgetPolicy(
                    scope=scope,
                    label=label,
                    amount_per_portion=None,
                    source=None,
                    verified=False,
                )
            )
        db.commit()
        print("[seed] kebijakan anggaran siap (status: belum dikonfigurasi)")
    finally:
        db.close()


def seed_demo_school() -> None:
    """Contoh sekolah untuk akun demo petugas SPPG (idempoten)."""
    db = SessionLocal()
    try:
        officer = (
            db.query(SppgOfficer)
            .filter(SppgOfficer.nip == "197801012006041001")
            .one_or_none()
        )
        if officer is None:
            print("[seed] petugas SPPG demo belum ada, sekolah dilewati")
            return
        if officer.schools:
            print("[seed] sekolah demo sudah ada, dilewati")
            return

        school = School(
            name="SD Negeri 1 Madiun (contoh)",
            npsn="20512345",
            address="Jl. Contoh No. 1",
            region="Kec. Madiun, Kab. Madiun",
            is_active=True,
        )
        school.groups = [
            BeneficiaryGroup(level=BeneficiaryLevel.SD_1_3, student_count=120),
            BeneficiaryGroup(level=BeneficiaryLevel.SD_4_6, student_count=108),
        ]
        officer.schools.append(school)
        db.add(officer)
        db.commit()
        print("[seed] sekolah demo dibuat untuk petugas SPPG")
    finally:
        db.close()


def ensure_schema() -> None:
    """Migrasi non-destruktif untuk kolom yang ditambahkan setelah rilis awal."""
    statements = [
        "ALTER TABLE users ADD COLUMN is_active TINYINT NOT NULL DEFAULT 1",
        # Halaman Profil: nomor HP kontak + sakelar notifikasi (FR-21).
        "ALTER TABLE users ADD COLUMN phone VARCHAR(30) NULL",
        "ALTER TABLE profiles ADD COLUMN notifications_enabled TINYINT NOT NULL DEFAULT 1",
    ]
    with engine.connect() as conn:
        for statement in statements:
            try:
                conn.execute(text(statement))
                conn.commit()
                print(f"[db] migrasi diterapkan: {statement.split('ADD COLUMN ')[-1]}")
            except Exception as exc:  # noqa: BLE001
                message = str(exc).lower()
                if "1060" in message or "duplicate column" in message:
                    continue
                raise
    print("[db] skema terbaru terverifikasi (is_active, phone, notifications_enabled)")


def main() -> None:
    settings.validate_production()
    create_database_if_missing()
    Base.metadata.create_all(bind=engine)
    print("[db] tabel users, sppg_officers, schools, dsb. siap")
    ensure_schema()
    if settings.seed_demo_accounts:
        seed_demo_users()
    else:
        print("[seed] SEED_DEMO_ACCOUNTS nonaktif — akun demo dilewati.")
    seed_bootstrap_admin()
    seed_budget_policies()
    if settings.seed_demo_accounts:
        seed_demo_school()

    # Data acuan (wilayah + bobot SAW) selalu disiapkan karena tidak punya
    # form admin.
    catalog_db = SessionLocal()
    try:
        seed_reference(catalog_db)
        if settings.seed_content:
            seed_catalog(catalog_db)
        else:
            print(
                "[seed] SEED_CONTENT nonaktif — data katalog/konten dilewati. "
                "Isi manual lewat panel admin (atau jalankan reset/isi ulang)."
            )
    finally:
        catalog_db.close()

    if settings.reset_data:
        print(
            "\n"
            "============================================================\n"
            "[reset] RESET_DATA aktif — SELURUH DATA DIHAPUS.\n"
            "Segera kembalikan env RESET_DATA=0 di Render!\n"
            "============================================================"
        )
        import app.models  # noqa: F401  # daftarkan seluruh tabel ke metadata

        from app.db.reset import reset_data, table_names_to_clear

        tables = table_names_to_clear(t.name for t in Base.metadata.sorted_tables)
        reset_data(engine, list(reversed(tables)), assume_yes=True)

    print("[db] selesai.")


if __name__ == "__main__":
    main()
