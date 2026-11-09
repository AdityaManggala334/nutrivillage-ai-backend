"""Router autentikasi: registrasi, login, refresh, logout, dan profil sesi (FR-01).

Sesi memakai dua token:
- access token JWT (8 jam) untuk otorisasi tiap request;
- refresh token acak yang disimpan sebagai hash di `refresh_tokens` dan
  dirotasi setiap kali dipakai, sehingga bisa dicabut (T-02).
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.ratelimit import client_ip, consume
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    refresh_expiry,
    utcnow,
    verify_password,
)
from app.crud.users import get_sppg_by_nip, get_user_by_email
from app.db.session import get_db
from app.models.session import RefreshToken
from app.models.sppg import SppgOfficer
from app.models.user import User, UserRole
from app.schemas.auth import (
    AuthSession,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Pembatas laju login/registrasi (K-01). Batas per email menahan tebak sandi
# terarah; batas per IP menahan credential stuffing lintas akun.
LOGIN_PER_EMAIL_15MIN = 7
LOGIN_PER_IP_15MIN = 30
REGISTER_PER_IP_HOUR = 10


def _batas_atau_tolak(nama: str, nilai: str, *, limit: int, window: int) -> None:
    hasil = consume(f"auth:{nama}:{nilai}", limit=limit, window_seconds=window)
    if not hasil.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Terlalu banyak percobaan. Tunggu beberapa saat lalu coba lagi.",
            headers={"Retry-After": str(hasil.retry_after)},
        )


def _build_session(db: Session, user: User) -> AuthSession:
    """Terbitkan access token + refresh token baru untuk satu sesi."""
    token = create_access_token(
        user_id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.value,
        created_at=user.created_at,
        token_version=user.token_version,
    )
    raw = create_refresh_token()
    expires = refresh_expiry()
    user.refresh_tokens.append(RefreshToken(token_hash=hash_token(raw), expires_at=expires))
    db.commit()
    return AuthSession(
        user=UserOut.model_validate(user),
        token=token,
        refresh_token=raw,
        refresh_expires_in=int((expires - utcnow()).total_seconds()),
    )


@router.post("/register", response_model=AuthSession, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthSession:
    """Registrasi masyarakat umum atau petugas SPPG MBG, lalu simpan ke MySQL."""
    _batas_atau_tolak("register-ip", client_ip(request), limit=REGISTER_PER_IP_HOUR, window=3600)

    email = payload.email.strip().lower()
    if get_user_by_email(db, email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email sudah terdaftar. Silakan login.",
        )

    user = User(
        name=payload.name.strip(),
        email=email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )

    if payload.role == UserRole.PETUGAS_SPPG:
        nip = (payload.nip or "").strip()
        if get_sppg_by_nip(db, nip) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="NIP petugas SPPG sudah terdaftar.",
            )
        user.sppg_officer = SppgOfficer(
            nip=nip,
            sppg_unit=(payload.sppg_unit or "").strip(),
            region=(payload.region or "").strip(),
            position=(payload.position or "").strip() or None,
        )

    db.add(user)
    try:
        db.commit()
    except Exception as exc:  # pragma: no cover - jaring pengaman integritas DB
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gagal menyimpan akun. Data mungkin sudah terdaftar.",
        ) from exc

    db.refresh(user)
    return _build_session(db, user)


@router.post("/login", response_model=AuthSession)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthSession:
    _batas_atau_tolak(
        "login-ip", client_ip(request), limit=LOGIN_PER_IP_15MIN, window=15 * 60
    )
    _batas_atau_tolak(
        "login-email",
        payload.email.strip().lower(),
        limit=LOGIN_PER_EMAIL_15MIN,
        window=15 * 60,
    )

    user = get_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun ini dinonaktifkan. Hubungi admin.",
        )
    return _build_session(db, user)


@router.post("/refresh", response_model=AuthSession)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> AuthSession:
    """Rotasi refresh token: token lama dicabut, pasangan token baru diterbitkan."""
    row = db.query(RefreshToken).filter(
        RefreshToken.token_hash == hash_token(payload.refresh_token)
    ).one_or_none()

    if row is None or row.revoked_at is not None:
        if row is not None:
            # Token yang sudah dicabut dipakai lagi -> kemungkinan pencurian.
            # Cabut seluruh sesi DAN naikkan token_version, supaya access token
            # yang terlanjur keluar (berlaku 8 jam) ikut mati seketika.
            _cabut_semua(db, row.user_id)
            korban = db.get(User, row.user_id)
            if korban is not None:
                korban.token_version += 1
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi tidak valid. Silakan masuk kembali.",
        )
    if row.expires_at <= utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi sudah kedaluwarsa. Silakan masuk kembali.",
        )

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun tidak aktif.",
        )

    row.revoked_at = utcnow()
    db.commit()
    return _build_session(db, user)


@router.post("/logout")
def logout(
    payload: LogoutRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    """Cabut sesi. `all_devices=true` juga menaikkan token_version sehingga
    access token yang masih berlaku langsung ditolak.
    """
    sekarang = utcnow()
    if payload and payload.all_devices:
        _cabut_semua(db, user.id)
        user.token_version += 1
        db.commit()
    elif payload and payload.refresh_token:
        row = db.query(RefreshToken).filter(
            RefreshToken.token_hash == hash_token(payload.refresh_token)
        ).one_or_none()
        if row is not None:
            row.revoked_at = sekarang
            db.commit()
    return {"ok": True}


def _cabut_semua(db: Session, user_id: int) -> None:
    """Tandai semua refresh token milik pengguna sebagai dicabut."""
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": utcnow()}, synchronize_session=False)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
