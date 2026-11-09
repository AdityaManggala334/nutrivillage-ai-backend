"""Hashing password (bcrypt) dan JWT (HS256) — FR-01 / NFR-03."""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    """Hash password dengan bcrypt (bukan enkripsi)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    user_id: int,
    name: str,
    email: str,
    role: str,
    created_at: datetime,
    token_version: int = 0,
) -> str:
    """Terbitkan access token JWT.

    Klaim `name`, `email`, `role`, dan `created_at` disertakan agar frontend
    dapat memverifikasi sesi tanpa query basis data (getUserByToken sinkron).
    Klaim `tver` dipakai backend untuk menolak token setelah logout-all atau
    ganti password, tanpa menunggu token kedaluwarsa.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "name": name,
        "email": email,
        "role": role,
        "created_at": created_at.isoformat(),
        "tver": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


def create_refresh_token() -> str:
    """Token acak untuk sesi jangka panjang (dikirim apa adanya ke klien)."""
    return secrets.token_urlsafe(48)


def utcnow() -> datetime:
    """Waktu UTC tanpa `tzinfo`.

    Kolom `DateTime` di proyek ini menyimpan naive UTC, jadi nilai sadar zona
    waktu tidak boleh dibandingkan atau disimpan ke kolom tersebut.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_token(token: str) -> str:
    """Nilai yang disimpan di database; token asli tidak pernah disimpan."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_expiry() -> datetime:
    return utcnow() + timedelta(days=settings.refresh_token_expire_days)
