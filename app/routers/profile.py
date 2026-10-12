"""Router profil keluarga (FR-02) — tersimpan di tabel `profiles` + `family_members`.

Berlaku untuk pengguna yang terautentikasi. Guest Mode (tanpa akun backend)
belum menyimpan profil permanen.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.catalog import Region
from app.models.enums import AgeGroup, ActivityLevel
from app.models.family import FamilyMember, FamilyProfile
from app.models.user import User
from app.schemas.profile import (
    FamilyMemberIn,
    FamilyMemberOut,
    FamilyProfileIn,
    FamilyProfileOut,
)

router = APIRouter(prefix="/profile", tags=["profile"])

_MAX_ALLERGIES = 255


def _split_allergies(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _join_allergies(items: list[str]) -> str | None:
    if not items:
        return None
    return ", ".join(items)[:_MAX_ALLERGIES]


def _resolve_age_group(age: int, given: AgeGroup | None) -> AgeGroup:
    if given is not None:
        return given
    if age <= 3:
        return AgeGroup.BALITA
    if age <= 12:
        return AgeGroup.ANAK
    if age <= 59:
        return AgeGroup.DEWASA
    return AgeGroup.LANSIA


def _counts(members: list[FamilyMemberIn]) -> dict[str, int]:
    counts = {"balita": 0, "anak": 0, "dewasa": 0, "lansia": 0}
    for member in members:
        group = _resolve_age_group(member.age, member.age_group)
        counts[group.value] += 1
    return counts


def _get_region(db: Session, name: str) -> Region:
    region = (
        db.query(Region)
        .filter(func.lower(Region.name) == name.strip().lower())
        .one_or_none()
    )
    if region is None:
        region = Region(name=name.strip(), province="Jawa Timur")
        db.add(region)
        db.flush()
    return region


def _to_out(db: Session, profile: FamilyProfile) -> FamilyProfileOut:
    region = db.get(Region, profile.region_id) if profile.region_id else None
    members = (
        db.query(FamilyMember)
        .filter(FamilyMember.user_id == profile.user_id)
        .order_by(FamilyMember.id)
        .all()
    )
    return FamilyProfileOut(
        user_id=profile.user_id,
        daily_budget=float(profile.daily_budget),
        region=region.name if region else "",
        preferences=list(profile.preferences or []),
        avoided_ingredients=list(profile.avoided_ingredients or []),
        onboarded=bool(profile.onboarded),
        family_count=int(profile.family_count or 0),
        members=[
            FamilyMemberOut(
                id=m.id,
                name=m.name,
                age=m.age,
                age_group=m.age_group,
                gender=m.gender,
                weight_kg=float(m.weight_kg),
                activity_level=m.activity_level,
                allergies=_split_allergies(m.allergies),
            )
            for m in members
        ],
        updated_at=profile.updated_at,
    )


@router.get("", response_model=FamilyProfileOut | None)
def get_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FamilyProfileOut | None:
    profile = db.get(FamilyProfile, user.id)
    if profile is None:
        return None
    return _to_out(db, profile)


@router.put("", response_model=FamilyProfileOut)
def save_profile(
    payload: FamilyProfileIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FamilyProfileOut:
    region = _get_region(db, payload.region)
    counts = _counts(payload.members)

    profile = db.get(FamilyProfile, user.id)
    if profile is None:
        profile = FamilyProfile(user_id=user.id)
        db.add(profile)

    profile.daily_budget = payload.daily_budget
    profile.region_id = region.id
    profile.preferences = list(payload.preferences)
    profile.avoided_ingredients = list(payload.avoided_ingredients)
    profile.onboarded = payload.onboarded
    profile.adults_count = counts["dewasa"]
    profile.children_count = counts["anak"]
    profile.toddlers_count = counts["balita"]
    profile.elderly_count = counts["lansia"]

    # Ganti seluruh anggota keluarga (cara paling sederhana & konsisten).
    db.query(FamilyMember).filter(FamilyMember.user_id == user.id).delete()
    for member in payload.members:
        db.add(
            FamilyMember(
                user_id=user.id,
                name=(member.name or None),
                age=member.age,
                age_group=_resolve_age_group(member.age, member.age_group),
                gender=member.gender,
                weight_kg=member.weight_kg,
                activity_level=member.activity_level or ActivityLevel.SEDANG,
                allergies=_join_allergies(member.allergies),
            )
        )

    db.commit()
    db.refresh(profile)
    return _to_out(db, profile)
