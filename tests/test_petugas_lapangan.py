"""Uji peran Petugas Lapangan: otorisasi, kepemilikan, dan larangan ACC sendiri.

Memakai SQLite sementara; tidak menyentuh MySQL proyek.
"""

from __future__ import annotations

import os
import tempfile

import pytest

DB_PATH = os.path.join(tempfile.gettempdir(), "nv_test_lapangan.db")
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["SEED_DEMO_ACCOUNTS"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import Base, engine  # noqa: E402
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


def _daftar(client, email, nama="Uji", role="user"):
    r = client.post(
        "/api/v1/auth/register",
        json={"name": nama, "email": email, "password": SANDI, "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _login(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": SANDI})
    assert r.status_code == 200, r.text
    return r.json()


def _admin(client):
    from app.core.security import hash_password

    from app.db.session import SessionLocal
    from app.models.user import User, UserRole

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "admin.uji@contoh.id").first()
        if existing is None:
            db.add(
                User(
                    name="Admin Uji",
                    email="admin.uji@contoh.id",
                    password_hash=hash_password(SANDI),
                    role=UserRole.ADMIN,
                )
            )
            db.commit()
    finally:
        db.close()
    return _login(client, "admin.uji@contoh.id")


def _bahan(client):
    """Satu bahan untuk pengujian; dibuat lewat API admin bila database kosong."""
    h = {"Authorization": f"Bearer {_admin(client)['token']}"}
    ada = client.get("/api/v1/admin/ingredients", headers=h).json()
    if ada:
        return int(ada[0]["id"])
    buat = client.post(
        "/api/v1/admin/ingredients",
        headers=h,
        json={
            "code": "bahan-uji",
            "name": "Uji",
            "category": "Sayur",
            "unit": "kg",
            "is_local": True,
            "is_in_season": True,
        },
    )
    assert buat.status_code == 201, buat.text
    return int(buat.json()["id"])


def test_registrasi_tidak_bisa_memilih_peran_lapangan(client):
    """S-1: peran lapangan hanya bisa diberikan admin, tidak bisa dipilih sendiri."""
    r = client.post(
        "/api/v1/auth/register",
        json={"name": "Coba", "email": "coba@contoh.com", "password": SANDI,
              "role": "petugas_lapangan"},
    )
    assert r.status_code == 422, r.text


def test_petugas_lapangan_bisa_mengirim_harga(client):
    admin = _admin(client)
    sesi = _daftar(client, "lapangan1@contoh.com")
    token_lapangan = sesi["token"]

    # Admin menaikkan peran.
    h = {"Authorization": f"Bearer {admin['token']}"}
    r = client.patch(
        f"/api/v1/users/{sesi['user']['id']}",
        headers=h,
        json={"role": "petugas_lapangan"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "petugas_lapangan"

    # Login ulang -> langsung punya akses lapangan.
    baru = _login(client, "lapangan1@contoh.com")
    tok = baru["token"]
    id_bahan = _bahan(client)

    r = client.post(
        "/api/v1/field/prices",
        headers={"Authorization": f"Bearer {tok}"},
        json={"ingredient_id": id_bahan, "price": 13500, "unit": "kg",
              "source": "Pasar Besar Madiun"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "pending", "S-2: status harus ditetapkan server"
    assert data["created_by"] == baru["user"]["id"]


def test_masyarakat_biasa_ditolak_di_jalur_lapangan(client):
    sesi = _daftar(client, "warga@contoh.com")
    id_bahan = _bahan(client)
    r = client.post(
        "/api/v1/field/prices",
        headers={"Authorization": f"Bearer {sesi['token']}"},
        json={"ingredient_id": id_bahan, "price": 9000, "unit": "kg", "source": "Pasar"},
    )
    assert r.status_code == 403, r.text


def test_kiriman_petugas_lain_tidak_terlihat(client):
    admin = _admin(client)
    h = {"Authorization": f"Bearer {admin['token']}"}
    a = _daftar(client, "lapanganA@contoh.com")
    b = _daftar(client, "lapanganB@contoh.com")
    for u in (a, b):
        client.patch(f"/api/v1/users/{u['user']['id']}", headers=h,
                     json={"role": "petugas_lapangan"})

    ta = _login(client, "lapanganA@contoh.com")["token"]
    tb = _login(client, "lapanganB@contoh.com")["token"]
    id_bahan = _bahan(client)

    r = client.post(
        "/api/v1/field/prices",
        headers={"Authorization": f"Bearer {ta}"},
        json={"ingredient_id": id_bahan, "price": 12000, "unit": "kg", "source": "Pasar A"},
    )
    assert r.status_code == 201, r.text
    milik_a = r.json()["id"]

    lihat_b = client.get("/api/v1/field/prices", headers={"Authorization": f"Bearer {tb}"}).json()
    assert milik_a not in [x["id"] for x in lihat_b], "S-3: kiriman petugas lain harus tertutup"

    hapus_b = client.delete(f"/api/v1/field/prices/{milik_a}",
                            headers={"Authorization": f"Bearer {tb}"})
    assert hapus_b.status_code == 403, hapus_b.text


def test_sudah_disetujui_tidak_bisa_dihapus_petugas(client):
    admin = _admin(client)
    h = {"Authorization": f"Bearer {admin['token']}"}
    s = _daftar(client, "lapanganC@contoh.com")
    client.patch(f"/api/v1/users/{s['user']['id']}", headers=h,
                 json={"role": "petugas_lapangan"})
    tok = _login(client, "lapanganC@contoh.com")["token"]
    id_bahan = _bahan(client)

    kirim = client.post(
        "/api/v1/field/prices",
        headers={"Authorization": f"Bearer {tok}"},
        json={"ingredient_id": id_bahan, "price": 15000, "unit": "kg", "source": "Pasar C"},
    ).json()
    pid = kirim["id"]

    setujui = client.post(f"/api/v1/admin/prices/{pid}/verify", headers=h,
                          json={"status": "approved", "note": "cocok"})
    assert setujui.status_code == 200, setujui.text

    coba_hapus = client.delete(f"/api/v1/field/prices/{pid}",
                               headers={"Authorization": f"Bearer {tok}"})
    assert coba_hapus.status_code == 409, coba_hapus.text


def test_petugas_bisa_menarik_kirimannya_sendiri(client):
    admin = _admin(client)
    h = {"Authorization": f"Bearer {admin['token']}"}
    s = _daftar(client, "lapanganD@contoh.com")
    client.patch(f"/api/v1/users/{s['user']['id']}", headers=h,
                 json={"role": "petugas_lapangan"})
    tok = _login(client, "lapanganD@contoh.com")["token"]
    id_bahan = _bahan(client)

    kirim = client.post(
        "/api/v1/field/prices",
        headers={"Authorization": f"Bearer {tok}"},
        json={"ingredient_id": id_bahan, "price": 8000, "unit": "kg", "source": "Pasar D"},
    ).json()
    r = client.delete(f"/api/v1/field/prices/{kirim['id']}",
                      headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 204, r.text


def test_perubahan_peran_menghapus_data_sppg_lama(client):
    """Data petugas SPPG tidak boleh tertinggal setelah peran diturunkan."""
    from app.db.session import SessionLocal
    from app.models.sppg import SppgOfficer

    admin = _admin(client)
    h = {"Authorization": f"Bearer {admin['token']}"}
    s = _daftar(client, "sppg-turun@contoh.com")

    # Admin menaikkan peran menjadi petugas SPPG (jalur nyata, bukan ORM).
    naik = client.patch(
        f"/api/v1/users/{s['user']['id']}",
        headers=h,
        json={
            "role": "petugas_sppg",
            "nip": "199912312020011009",
            "sppg_unit": "SPPG Turun",
            "region": "Kabupaten Madiun",
        },
    )
    assert naik.status_code == 200, naik.text
    assert naik.json()["sppg_officer"] is not None

    db = SessionLocal()
    try:
        officer_id = db.query(SppgOfficer).filter(
            SppgOfficer.nip == "199912312020011009"
        ).one().id
    finally:
        db.close()

    turunkan = client.patch(
        f"/api/v1/users/{s['user']['id']}", headers=h, json={"role": "user"}
    )
    assert turunkan.status_code == 200, turunkan.text

    db = SessionLocal()
    try:
        assert db.get(SppgOfficer, officer_id) is None, "sppg_officer lama harus dihapus"
    finally:
        db.close()
