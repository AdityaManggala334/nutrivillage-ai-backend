"""Operasi data pengguna (SQLAlchemy)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.school import School
from app.models.sppg import SppgOfficer
from app.models.user import User, UserRole


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_sppg_by_nip(db: Session, nip: str) -> SppgOfficer | None:
    return db.scalar(select(SppgOfficer).where(SppgOfficer.nip == nip.strip()))


def count_users(db: Session) -> int:
    return int(db.scalar(select(func.count(User.id))) or 0)


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())


def count_schools_for_officer(db: Session, officer_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(School.id)).where(School.sppg_officer_id == officer_id)
        )
        or 0
    )


def create_user(
    db: Session,
    *,
    name: str,
    email: str,
    password_hash: str,
    role: UserRole,
    is_active: bool = True,
    officer: dict | None = None,
) -> User:
    user = User(
        name=name.strip(),
        email=email.strip().lower(),
        password_hash=password_hash,
        role=role,
        is_active=is_active,
    )
    if officer is not None:
        user.sppg_officer = SppgOfficer(**officer)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user: User,
    *,
    name: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    officer: dict | None = None,
) -> User:
    if name is not None:
        user.name = name.strip()
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    if officer is not None:
        if user.sppg_officer is None:
            user.sppg_officer = SppgOfficer(**officer)
        else:
            for field, value in officer.items():
                if value is not None:
                    setattr(user.sppg_officer, field, value)
    db.commit()
    db.refresh(user)
    return user
