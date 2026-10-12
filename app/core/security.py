"""Hashing password (bcrypt) dan JWT (HS256) — FR-01 / NFR-03."""

from datetime import datetime, timedelta, timezone

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
) -> str:
    """Terbitkan access token JWT.

    Klaim `name`, `email`, `role`, dan `created_at` disertakan agar frontend
    dapat memverifikasi sesi tanpa query basis data (getUserByToken sinkron).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "name": name,
        "email": email,
        "role": role,
        "created_at": created_at.isoformat(),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
