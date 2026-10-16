"""Router akun halaman Profil (FR-02): data diri, notifikasi, ganti password.

Tersimpan di tabel `users` (nama, telepon) dan `profiles`
(`notifications_enabled`). Email tidak dapat diubah karena dipakai untuk login.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.family import FamilyProfile
from app.models.user import User
from app.schemas.auth import (
    AccountOut,
    AccountUpdateRequest,
    PasswordChangeRequest,
)

router = APIRouter(prefix="/account", tags=["account"])


def _to_out(user: User, profile: FamilyProfile | None) -> AccountOut:
    return AccountOut(
        id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        created_at=user.created_at,
        notifications_enabled=(
            bool(profile.notifications_enabled) if profile is not None else True
        ),
    )


def _get_profile(db: Session, user: User) -> FamilyProfile | None:
    profile = db.get(FamilyProfile, user.id)
    if profile is not None:
        return profile

    # Belum ada profil keluarga (mis. pengguna belum selesai onboarding).
    # Baris kerangka dibuat agar preferensi notifikasi tetap tersimpan.
    # `onboarded` tetap False sehingga alur onboarding tidak terganggu.
    profile = FamilyProfile(user_id=user.id, daily_budget=0, onboarded=False)
    db.add(profile)
    db.flush()
    return profile


@router.get("", response_model=AccountOut)
def get_account(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AccountOut:
    return _to_out(user, db.get(FamilyProfile, user.id))


@router.patch("", response_model=AccountOut)
def update_account(
    payload: AccountUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AccountOut:
    data = payload.model_dump(exclude_unset=True)

    if "name" in data:
        user.name = (data["name"] or "").strip()

    if "phone" in data:
        # Sudah divalidasi & dinormalkan oleh AccountUpdateRequest
        # (opsional, 10-15 digit); nilai kosong berarti menghapus nomor.
        user.phone = data["phone"] or None

    if "notifications_enabled" in data:
        profile = _get_profile(db, user)
        profile.notifications_enabled = bool(data["notifications_enabled"])

    db.commit()
    db.refresh(user)
    return _to_out(user, db.get(FamilyProfile, user.id))


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password lama tidak sesuai.",
        )
    user.password_hash = hash_password(payload.new_password)
    db.commit()
