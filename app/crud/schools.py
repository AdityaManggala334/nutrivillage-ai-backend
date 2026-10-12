"""Operasi data sekolah, kelompok penerima manfaat, & kebijakan anggaran."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.beneficiary_group import BeneficiaryGroup
from app.models.budget_policy import BudgetPolicy
from app.models.school import School
from app.models.sppg import SppgOfficer
from app.schemas.school import (
    BeneficiaryGroupCreate,
    BeneficiaryGroupUpdate,
    SchoolCreate,
    SchoolUpdate,
)


def get_officer_by_user_id(db: Session, user_id: int) -> SppgOfficer | None:
    return db.scalar(select(SppgOfficer).where(SppgOfficer.user_id == user_id))


def list_schools(db: Session, officer_id: int | None = None) -> list[School]:
    statement = (
        select(School).options(selectinload(School.groups)).order_by(School.name)
    )
    if officer_id is not None:
        statement = statement.where(School.sppg_officer_id == officer_id)
    return list(db.scalars(statement).all())


def get_school(db: Session, school_id: int) -> School | None:
    return db.scalar(
        select(School)
        .options(selectinload(School.groups))
        .where(School.id == school_id)
    )


def _build_group(payload: BeneficiaryGroupCreate) -> BeneficiaryGroup:
    return BeneficiaryGroup(
        level=payload.level,
        label=(payload.label or "").strip() or None,
        student_count=payload.student_count,
        budget_per_portion=payload.budget_per_portion,
    )


def create_school(db: Session, officer_id: int, payload: SchoolCreate) -> School:
    school = School(
        sppg_officer_id=officer_id,
        name=payload.name.strip(),
        npsn=(payload.npsn or "").strip() or None,
        address=(payload.address or "").strip() or None,
        region=payload.region.strip(),
        is_active=payload.is_active,
    )
    for group in payload.groups:
        school.groups.append(_build_group(group))
    db.add(school)
    db.commit()
    db.refresh(school)
    return school


def update_school(db: Session, school: School, payload: SchoolUpdate) -> School:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(school, field, value)
    db.commit()
    db.refresh(school)
    return school


def delete_school(db: Session, school: School) -> None:
    db.delete(school)
    db.commit()


def get_group(db: Session, school_id: int, group_id: int) -> BeneficiaryGroup | None:
    return db.scalar(
        select(BeneficiaryGroup).where(
            BeneficiaryGroup.id == group_id,
            BeneficiaryGroup.school_id == school_id,
        )
    )


def list_groups(db: Session, school_id: int) -> list[BeneficiaryGroup]:
    return list(
        db.scalars(
            select(BeneficiaryGroup)
            .where(BeneficiaryGroup.school_id == school_id)
            .order_by(BeneficiaryGroup.id)
        ).all()
    )


def create_group(
    db: Session, school: School, payload: BeneficiaryGroupCreate
) -> BeneficiaryGroup:
    group = _build_group(payload)
    group.school_id = school.id
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def update_group(
    db: Session, group: BeneficiaryGroup, payload: BeneficiaryGroupUpdate
) -> BeneficiaryGroup:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(group, field, value)
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, group: BeneficiaryGroup) -> None:
    db.delete(group)
    db.commit()


def list_budget_policies(db: Session) -> list[BudgetPolicy]:
    return list(db.scalars(select(BudgetPolicy).order_by(BudgetPolicy.scope)).all())


def get_budget_policy(db: Session, policy_id: int) -> BudgetPolicy | None:
    return db.get(BudgetPolicy, policy_id)


def update_budget_policy(db: Session, policy: BudgetPolicy, payload) -> BudgetPolicy:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(policy, field, value)
    db.commit()
    db.refresh(policy)
    return policy
