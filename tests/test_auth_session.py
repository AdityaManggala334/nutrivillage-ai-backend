"""Uji sesi dua-token + pembatas laju login (perbaikan K-01, T-01, T-02).

Menjalankan app FastAPI penuh di atas SQLite sementara, tanpa MySQL.
"""

from __future__ import annotations

import os
import tempfile

import pytest

DB_PATH = os.path.join(tempfile.gettempdir(), "nv_test_auth.db")
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["ENVIRONMENT"] = "development"
os.environ["SEED_DEMO_ACCOUNTS"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

BEBERES = {"content_type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def _skema():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    # Tabel sesi + users dibuat dari metadata (termasuk refresh_tokens).
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


def _daftar(client: TestClient, email: str, password: str = "rahasia123"):
    r = client.post(
        "/api/v1/auth/register",
        json={"name": "Uji Sesi", "email": email, "password": password, "role": "user"},
        headers=BEBERES,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_register_mengembalikan_refresh_token(client):
    sesi = _daftar(client, "sesi-a@example.com")
    assert sesi["token"]
    assert sesi["refresh_token"] and len(sesi["refresh_token"]) >= 32
    assert sesi["refresh_expires_in"] > 0


def test_refresh_merotasi_dan_menolak_token_lama(client):
    sesi = _daftar(client, "sesi-b@example.com")
    r = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": sesi["refresh_token"]}
    )
    assert r.status_code == 200, r.text
    baru = r.json()
    assert baru["refresh_token"] != sesi["refresh_token"]

    # Token lama tidak bisa dipakai dua kali (deteksi pencurian).
    ulang = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": sesi["refresh_token"]}
    )
    assert ulang.status_code == 401


def test_me_memakai_access_token_baru(client):
    sesi = _daftar(client, "sesi-c@example.com")
    r = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": sesi["refresh_token"]}
    )
    token = r.json()["token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "sesi-c@example.com"


def test_logout_all_mencabut_access_token(client):
    sesi = _daftar(client, "sesi-d@example.com")
    r = client.post(
        "/api/v1/auth/logout",
        json={"all_devices": True},
        headers={"Authorization": f"Bearer {sesi['token']}"},
    )
    assert r.status_code == 200, r.text
    ditolak = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {sesi['token']}"}
    )
    assert ditolak.status_code == 401

    masuk_lagi = client.post(
        "/api/v1/auth/login",
        json={"email": "sesi-d@example.com", "password": "rahasia123"},
    )
    assert masuk_lagi.status_code == 200


def test_akun_nonaktif_ditolak_oleh_token_yang_masih_hidup(client):
    """T-01: `is_active` harus diperiksa pada setiap request, bukan hanya login."""
    sesi = _daftar(client, "sesi-e@example.com")
    from sqlalchemy.orm import Session  # noqa: F401

    from app.db.session import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "sesi-e@example.com").one()
        user.is_active = False
        db.commit()
    finally:
        db.close()

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {sesi['token']}"})
    assert r.status_code == 403


def test_pemakaian_ulang_refresh_token_mematikan_access_token(client):
    """Deteksi pencurian: token lama dipakai lagi -> access token hasil rotasi ikut mati."""
    sesi = _daftar(client, "sesi-g@example.com")
    baru = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": sesi["refresh_token"]}
    ).json()

    # Pemakaian ulang token lama = sinyal pencurian.
    ulang = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": sesi["refresh_token"]}
    )
    assert ulang.status_code == 401

    ditolak = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {baru['token']}"}
    )
    assert ditolak.status_code == 401


def test_login_dibatasi_per_email(client):
    """K-01: percobaan sandi salah tidak bisa tanpa batas."""
    _daftar(client, "sesi-f@example.com")
    kode = set()
    for _ in range(12):
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "sesi-f@example.com", "password": "salah12345"},
        )
        kode.add(r.status_code)
    assert 429 in kode, kode


def test_kuota_rekomendasi_berlaku_walau_tanpa_next(client):
    """T-04: kuota FR-35 harus hidup di backend, bukan hanya di proxy web."""
    from app.core.ratelimit import consume

    kunci = "gen:generate:ip:10.0.0.99"
    hasil = [consume(kunci, limit=5, window_seconds=3600).allowed for _ in range(6)]
    assert hasil == [True] * 5 + [False]
