"""Router data pengguna: statistik & manajemen akun oleh admin."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.security import hash_password, utcnow
from app.crud.users import (
    count_schools_for_officer,
    count_users,
    create_user,
    get_sppg_by_nip,
    get_user_by_email,
    get_user_by_id,
    list_users,
    update_user,
)
from app.db.session import get_db
from app.models.session import RefreshToken
from app.models.user import User, UserRole
from app.schemas.auth import UserCreateRequest, UserListItem, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["users"])


def _to_item(db: Session, user: User) -> UserListItem:
    officer = user.sppg_officer
    schools = count_schools_for_officer(db, officer.id) if officer else 0
    return UserListItem(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        sppg_officer=officer,
        schools_count=schools,
    )


@router.get("/count")
def users_count(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> dict[str, int]:
    return {"count": count_users(db)}


@router.get("", response_model=list[UserListItem])
def list_all(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> list[UserListItem]:
    return [_to_item(db, user) for user in list_users(db)]


@router.post("", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
def create(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> UserListItem:
    email = payload.email.strip().lower()
    if get_user_by_email(db, email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email sudah terdaftar.",
        )

    officer: dict | None = None
    if payload.role == UserRole.PETUGAS_SPPG:
        nip = (payload.nip or "").strip()
        if get_sppg_by_nip(db, nip) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="NIP petugas SPPG sudah terdaftar.",
            )
        officer = {
            "nip": nip,
            "sppg_unit": (payload.sppg_unit or "").strip(),
            "region": (payload.region or "").strip(),
            "position": (payload.position or "").strip() or None,
        }

    try:
        user = create_user(
            db,
            name=payload.name,
            email=email,
            password_hash=hash_password(payload.password),
            role=payload.role,
            is_active=payload.is_active,
            officer=officer,
        )
    except Exception as exc:  # pragma: no cover - integritas DB
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gagal menyimpan akun. Data mungkin sudah terdaftar.",
        ) from exc

    return _to_item(db, user)


@router.patch("/{user_id}", response_model=UserListItem)
def update(
    user_id: int,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
) -> UserListItem:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pengguna tidak ditemukan.",
        )

    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anda tidak dapat menonaktifkan akun Anda sendiri.",
        )

    officer: dict | None = None
    if payload.role == UserRole.PETUGAS_SPPG:
        nip = (payload.nip or "").strip()
        if not nip:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="NIP wajib diisi untuk peran petugas SPPG.",
            )
        officer = {
            "nip": nip,
            "sppg_unit": (payload.sppg_unit or "").strip(),
            "region": (payload.region or "").strip(),
            "position": (payload.position or "").strip() or None,
        }

    role_lama = user.role

    try:
        user = update_user(
            db,
            user,
            name=payload.name,
            role=payload.role,
            is_active=payload.is_active,
            officer=officer,
        )
    except Exception as exc:  # pragma: no cover - integritas DB
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gagal memperbarui akun. Periksa kembali datanya.",
        ) from exc

    # Peran berubah: bersihkan data yang tidak lagi relevan dan cabut sesi lama
    # supaya perubahan berlaku pada permintaan berikutnya, bukan 8 jam lagi.
    if payload.role is not None and payload.role != role_lama:
        if payload.role != UserRole.PETUGAS_SPPG and user.sppg_officer is not None:
            db.delete(user.sppg_officer)
        user.token_version += 1
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": utcnow()}, synchronize_session=False)
        db.commit()

    return _to_item(db, user)
