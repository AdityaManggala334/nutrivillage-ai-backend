"""Router autentikasi: registrasi, login, logout, dan profil sesi (FR-01)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.crud.users import get_sppg_by_nip, get_user_by_email
from app.db.session import get_db
from app.models.sppg import SppgOfficer
from app.models.user import User, UserRole
from app.schemas.auth import AuthSession, LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_session(user: User) -> AuthSession:
    token = create_access_token(
        user_id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.value,
        created_at=user.created_at,
    )
    return AuthSession(user=UserOut.model_validate(user), token=token)


@router.post("/register", response_model=AuthSession, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthSession:
    """Registrasi masyarakat umum atau petugas SPPG MBG, lalu simpan ke MySQL."""
    email = payload.email.strip().lower()
    if get_user_by_email(db, email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email sudah terdaftar. Silakan login.",
        )

    user = User(
        name=payload.name.strip(),
        email=email,
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
    return _build_session(user)


@router.post("/login", response_model=AuthSession)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthSession:
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
    return _build_session(user)


@router.post("/logout")
def logout() -> dict[str, bool]:
    """JWT bersifat stateless; logout cukup menghapus cookie di sisi klien."""
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
