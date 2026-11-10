"""Uji tahan input admin yang tidak konsisten (temuan audit: crash 500).

Skenario: admin membuat resep lewat ORM/API dengan `category` berupa string
polos. Sebelum perbaikan, `bangun_snapshot()` crash
(`'str' object has no attribute 'value'`) dan seluruh endpoint rekomendasi
gagal 500 untuk SEMUA pengguna — bukan hanya admin yang salah input.

Menutup temuan A1-final: satu input yang berbeda tidak boleh mematikan fitur
inti. Semua objek uji dibersihkan di akhir.
"""

from __future__ import annotations

import os
import tempfile
import uuid

import pytest

kode_resep = ["belum-ditetapkan"]

DB_PATH = os.path.join(tempfile.gettempdir(), "nv_test_input_admin.db")
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["SEED_DEMO_ACCOUNTS"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

SANDI = "rahasia123"


@pytest.fixture(scope="module", autouse=True)
def _skema():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    from app.core import ratelimit

    ratelimit.reset()
    with TestClient(app) as c:
        yield c


def _admin_token(client):
    """Pastikan ada akun admin lalu login. Urutan: bootstrap SQL dulu (aman,
    tidak lewat API), lalu login."""
    from app.core.security import hash_password

    from app.db.session import SessionLocal
    from app.models.user import User, UserRole

    db = SessionLocal()
    try:
        ada = (db.query(User)
               .filter(User.email == "admin.uji@contoh.id")
               .one_or_none())
        if ada is None:
            db.add(User(name="Admin Uji", email="admin.uji@contoh.id",
                        password_hash=hash_password(SANDI), role=UserRole.ADMIN))
            db.commit()
        else:
            ada.role = UserRole.ADMIN
            ada.is_active = True
            ada.token_version = 0
            db.commit()
    finally:
        db.close()
    r = client.post("/api/v1/auth/login",
                    json={"email": "admin.uji@contoh.id", "password": SANDI})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _user_token(client):
    r = client.post("/api/v1/auth/register",
                    json={"name": "Uji Input", "email": "input.user@contoh.com",
                          "password": SANDI, "role": "user"})
    return r.json()["token"]


def _buat_bahan(client, token, kode=None):
    from app.models.enums import MbgSlot

    body = {"code": kode or ("bahan-uji-" + uuid.uuid4().hex[:6]),
            "name": "Ubi Ungu Uji", "category": "Pokok", "unit": "kg",
            "is_local": True, "is_in_season": True}
    r = client.post("/api/v1/admin/ingredients", headers={"Authorization": f"Bearer {token}"},
                    json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_resep_dengan_category_string_tidak_membuat_snapshot_crash(client):
    """Akar bug: category string polos + `.value` di bangun_snapshot = 500."""
    global kode_resep
    from app.db.session import SessionLocal
    from app.models.recipe import Recipe
    from app.services.engine_data import bangun_snapshot

    token = _admin_token(client)
    bahan = _buat_bahan(client, token)

    kode = "resep-uji-" + uuid.uuid4().hex[:6]
    kode_resep[0] = kode
    r = client.post("/api/v1/admin/recipes", headers={"Authorization": f"Bearer {token}"},
                    json={"name": "Bubur Ubi Ungu Uji", "category": "Makanan Utama",
                          "servings": 2, "cooking_time_min": 20,
                          "ingredients": [{"ingredient_id": bahan["id"], "name": bahan["name"],
                                           "quantity": 0.5, "unit": "kg",
                                           "estimated_price": 4500}]})
    assert r.status_code == 201, r.text

    # B4 (uji): cari resep uji dengan code yang kita simpan di variabel global.
    db = SessionLocal()
    try:
        from app.models.recipe import Recipe as RecipeModel

        kode_ditarget = kode_resep[0]
        row = (db.query(RecipeModel)
               .filter(RecipeModel.code == kode_ditarget)
               .one_or_none())
        if row is None:
            # Fallback: cari by nama, karena `code` bisa NULL bila admin
            # tidak mengirimkannya (RecipeOut tidak mengekspos code).
            row = (db.query(RecipeModel)
                   .filter(RecipeModel.name == "Bubur Ubi Ungu Uji")
                   .order_by(RecipeModel.id.desc())
                   .first())
        if row is not None:
            row.category = "Makanan Utama"  # string polos, bukan enum
            db.commit()
        else:
            pytest.fail("resep uji tidak ditemukan setelah dibuat")
    finally:
        db.close()

    # Sebelum perbaikan: baris ini melempar AttributeError -> semua endpoint
    # rekomendasi 500. Sesudah: snapshot sukses dan resep tetap dikenali.
    db2 = SessionLocal()
    try:
        snap = bangun_snapshot(db2)
    finally:
        db2.close()

    assert snap["jumlah_menu"] >= 1
    nama = [m["nama_menu"] for m in snap["menu"].values() if "Ubi Ungu" in m["nama_menu"]]
    assert nama, "resep dengan category string harus tetap dikenali snapshot"


def test_engine_memakai_resep_manual_dari_admin(client):
    """Rantai penuh: bahan + resep manual -> masuk paket rekomendasi."""
    from app.db.session import SessionLocal
    from app.services.engine_data import bangun_snapshot

    token = _admin_token(client)
    bahan = _buat_bahan(client, token)
    id_bahan = bahan["id"]

    r = client.post("/api/v1/admin/recipes", headers={"Authorization": f"Bearer {token}"},
                    json={"name": "Bubur Ubi Ungu Uji Dua", "category": "Makanan Utama",
                          "servings": 2, "cooking_time_min": 20,
                          "ingredients": [{"ingredient_id": id_bahan, "name": bahan["name"],
                                           "quantity": 0.5, "unit": "kg",
                                           "estimated_price": 4500}]})
    assert r.status_code == 201, r.text

    # harga approved untuk bahan baru
    h = {"Authorization": f"Bearer {token}"}
    harga = client.post("/api/v1/admin/prices", headers=h,
                        json={"ingredient_id": id_bahan, "price": 9000, "unit": "kg",
                              "source": "input manual admin"}).json()
    client.patch(f"/api/admin/prices/{harga['id']}", headers=h,
                 json={"status": "approved"})

    # engine memakai resep manual (masuk snapshot)
    db = SessionLocal()
    try:
        snap = bangun_snapshot(db)
        muat = [m for m in snap["menu"].values() if "Ubi Ungu" in m["nama_menu"]]
        assert muat, "resep manual harus masuk snapshot"
    finally:
        db.close()

    # rekomendasi berjalan (tidak crash) untuk pengguna biasa.
    # Anggaran 150rb dipakai karena data uji hanya 1 resep baru dengan bahan
    # baru — paket penuh 6 slot per waktu makan butuh banyak kandidat, dan
    # tujuan uji ini adalah memastikan tidak crash + resep manual dikenali.
    token_user = _user_token(client)
    rk = client.post(
        "/api/v1/recommendations/keluarga",
        headers={"Authorization": f"Bearer {token_user}"},
        json={"daily_budget": 250000, "region": "Kabupaten Madiun",
              "members": [{"name": "Ayah", "age": 35, "gender": "laki-laki",
                           "weight_kg": 70, "height_cm": 170,
                           "activity_level": "sedang", "allergies": []}],
              "preferences": ["sayur"], "allergies": [], "meals_per_day": 3,
              "include_susu": True})
    assert rk.status_code == 200, rk.text
    plan = rk.json()["keluarga"]
    # Tidak crash + rekomendasi konsisten: status ok ATAU infeasible yang
    # disertai alasan/peringatan (data uji memang minim kandidat).
    assert plan["status"] in ("ok", "infeasible"), plan
    if plan["status"] == "infeasible":
        assert (plan.get("reason") or plan.get("peringatan")
                or plan.get("minimum_dibutuhkan")), (
            "infeasible harus disertai penjelasan (reason/peringatan/minimum)")
