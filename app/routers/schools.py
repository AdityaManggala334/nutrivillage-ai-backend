"""Router FR-11: pengelolaan sekolah & kelompok penerima manfaat.

Petugas SPPG hanya dapat mengakses sekolah yang menjadi tanggung jawabnya.
Admin dapat melihat seluruh data (verifikasi/referensi), tetapi pengelolaan
operasional tetap milik petugas.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.school import School
from app.models.user import User, UserRole
from app.schemas.budget import BudgetPolicyOut, BudgetPolicyUpdate
from app.schemas.school import (
    BeneficiaryGroupCreate,
    BeneficiaryGroupOut,
    BeneficiaryGroupUpdate,
    SchoolCreate,
    SchoolOut,
    SchoolUpdate,
)
from app import crud

router = APIRouter(tags=["sppg"])


def _require_officer(db: Session, user: User):
    officer = crud.get_officer_by_user_id(db, user.id)
    if officer is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun ini tidak terhubung ke unit SPPG.",
        )
    return officer


def _get_authorized_school(db: Session, user: User, school_id: int) -> School:
    school = crud.get_school(db, school_id)
    if school is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sekolah tidak ditemukan.",
        )
    if user.role == UserRole.ADMIN:
        return school
    officer = _require_officer(db, user)
    if school.sppg_officer_id != officer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak berhak mengakses sekolah ini.",
        )
    return school


@router.get("/schools", response_model=list[SchoolOut])
def list_schools(
    user: User = Depends(require_roles(UserRole.PETUGAS_SPPG, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[School]:
    if user.role == UserRole.ADMIN:
        return crud.list_schools(db)
    officer = _require_officer(db, user)
    return crud.list_schools(db, officer.id)


@router.post(
    "/schools", response_model=SchoolOut, status_code=status.HTTP_201_CREATED
)
def create_school(
    payload: SchoolCreate,
    user: User = Depends(require_roles(UserRole.PETUGAS_SPPG)),
    db: Session = Depends(get_db),
) -> School:
    officer = _require_officer(db, user)
    return crud.create_school(db, officer.id, payload)


@router.get("/schools/{school_id}", response_model=SchoolOut)
def get_school(
    school_id: int,
    user: User = Depends(require_roles(UserRole.PETUGAS_SPPG, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> School:
    return _get_authorized_school(db, user, school_id)


@router.patch("/schools/{school_id}", response_model=SchoolOut)
def update_school(
    school_id: int,
    payload: SchoolUpdate,
    user: User = Depends(require_roles(UserRole.PETUGAS_SPPG)),
    db: Session = Depends(get_db),
) -> School:
    school = _get_authorized_school(db, user, school_id)
    return crud.update_school(db, school, payload)


@router.delete("/schools/{school_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_school(
    school_id: int,
    user: User = Depends(require_roles(UserRole.PETUGAS_SPPG)),
    db: Session = Depends(get_db),
) -> None:
    school = _get_authorized_school(db, user, school_id)
    crud.delete_school(db, school)


@router.get("/schools/{school_id}/groups", response_model=list[BeneficiaryGroupOut])
def list_groups(
    school_id: int,
    user: User = Depends(require_roles(UserRole.PETUGAS_SPPG, UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list:
    _get_authorized_school(db, user, school_id)
    return crud.list_groups(db, school_id)


@router.post(
    "/schools/{school_id}/groups",
    response_model=BeneficiaryGroupOut,
    status_code=status.HTTP_201_CREATED,
)
def create_group(
    school_id: int,
    payload: BeneficiaryGroupCreate,
    user: User = Depends(require_roles(UserRole.PETUGAS_SPPG)),
    db: Session = Depends(get_db),
):
    school = _get_authorized_school(db, user, school_id)
    return crud.create_group(db, school, payload)


@router.patch(
    "/schools/{school_id}/groups/{group_id}", response_model=BeneficiaryGroupOut
)
def update_group(
    school_id: int,
    group_id: int,
    payload: BeneficiaryGroupUpdate,
    user: User = Depends(require_roles(UserRole.PETUGAS_SPPG)),
    db: Session = Depends(get_db),
):
    _get_authorized_school(db, user, school_id)
    group = crud.get_group(db, school_id, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kelompok penerima tidak ditemukan.",
        )
    return crud.update_group(db, group, payload)


@router.delete(
    "/schools/{school_id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_group(
    school_id: int,
    group_id: int,
    user: User = Depends(require_roles(UserRole.PETUGAS_SPPG)),
    db: Session = Depends(get_db),
) -> None:
    _get_authorized_school(db, user, school_id)
    group = crud.get_group(db, school_id, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kelompok penerima tidak ditemukan.",
        )
    crud.delete_group(db, group)


@router.get("/budget-policies", response_model=list[BudgetPolicyOut])
def list_budget_policies(
    _: User = Depends(
        require_roles(UserRole.PETUGAS_SPPG, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
) -> list:
    return crud.list_budget_policies(db)


@router.patch("/budget-policies/{policy_id}", response_model=BudgetPolicyOut)
def update_budget_policy(
    policy_id: int,
    payload: BudgetPolicyUpdate,
    _: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    policy = crud.get_budget_policy(db, policy_id)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kebijakan anggaran tidak ditemukan.",
        )
    return crud.update_budget_policy(db, policy, payload)
