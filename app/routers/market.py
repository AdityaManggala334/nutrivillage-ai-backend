"""Router harga pangan & monitoring scraper (khusus admin) — FR-23, FR-31.

Semua data disimpan di tabel `prices`, `price_verifications`, `price_history`
(append-only), dan `scraper_runs`. Tidak ada data tiruan di memori.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.catalog import Ingredient
from app.models.enums import (
    PriceStatus,
    PriceVerificationStatus,
    ScraperStatus,
)
from app.models.price import Price, PriceHistory, PriceVerification, ScraperRun
from app.models.recipe import Recipe
from app.models.user import User, UserRole
from app.schemas.market import (
    AdminStatsOut,
    PriceCreate,
    PriceOut,
    PriceUpdate,
    PriceVerifyRequest,
    ScraperRunCreate,
    ScraperRunOut,
)

router = APIRouter(prefix="/admin", tags=["admin-market"])

AdminDep = Depends(require_roles(UserRole.ADMIN))


def _get_or_404(db: Session, model, obj_id: int, label: str):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} tidak ditemukan."
        )
    return obj


def _to_out(price: Price, ingredient_name: str = "") -> PriceOut:
    return PriceOut(
        id=price.id,
        ingredient_id=price.ingredient_id,
        ingredient_name=ingredient_name,
        region_id=price.region_id,
        price=float(price.price),
        unit=price.unit,
        recorded_date=price.recorded_date,
        source_type=price.source_type,
        source=price.source,
        status=price.status,
        created_at=price.created_at,
    )


def _append_history(
    db: Session,
    price: Price,
    *,
    action: str,
    changed_by: int | None,
) -> None:
    db.add(
        PriceHistory(
            price_id=price.id,
            ingredient_id=price.ingredient_id,
            region_id=price.region_id,
            price=price.price,
            unit=price.unit,
            recorded_date=price.recorded_date,
            source=price.source,
            source_type=price.source_type,
            status=price.status.value,
            action=action,
            changed_by=changed_by,
        )
    )


# --------------------------------------------------------------------------
# Harga
# --------------------------------------------------------------------------
@router.get("/prices", response_model=list[PriceOut], dependencies=[AdminDep])
def list_prices(db: Session = Depends(get_db)) -> list[PriceOut]:
    rows = (
        db.query(Price, Ingredient.name)
        .join(Ingredient, Ingredient.id == Price.ingredient_id, isouter=True)
        .order_by(Price.recorded_date.desc(), Price.id.desc())
        .all()
    )
    return [_to_out(price, name or "-") for price, name in rows]


@router.post(
    "/prices",
    response_model=PriceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminDep],
)
def create_price(
    payload: PriceCreate,
    db: Session = Depends(get_db),
    admin: User = AdminDep,
) -> PriceOut:
    ingredient = _get_or_404(db, Ingredient, payload.ingredient_id, "Bahan")
    price = Price(
        ingredient_id=ingredient.id,
        region_id=payload.region_id,
        price=payload.price,
        unit=payload.unit,
        recorded_date=payload.recorded_date or date.today(),
        source_type=payload.source_type,
        source=payload.source,
        status=payload.status,
    )
    db.add(price)
    db.flush()
    _append_history(db, price, action="new", changed_by=admin.id)
    db.commit()
    db.refresh(price)
    return _to_out(price, ingredient.name)


@router.patch("/prices/{price_id}", response_model=PriceOut, dependencies=[AdminDep])
def update_price(
    price_id: int,
    payload: PriceUpdate,
    db: Session = Depends(get_db),
    admin: User = AdminDep,
) -> PriceOut:
    price = _get_or_404(db, Price, price_id, "Data harga")
    data = payload.model_dump(exclude_unset=True)
    changed_status = "status" in data and data["status"] != price.status
    for key, value in data.items():
        setattr(price, key, value)
    if changed_status:
        _append_history(db, price, action="changed", changed_by=admin.id)
    db.commit()
    db.refresh(price)
    name = db.get(Ingredient, price.ingredient_id)
    return _to_out(price, name.name if name else "-")


@router.post(
    "/prices/{price_id}/verify",
    response_model=PriceOut,
    dependencies=[AdminDep],
)
def verify_price(
    price_id: int,
    payload: PriceVerifyRequest,
    db: Session = Depends(get_db),
    admin: User = AdminDep,
) -> PriceOut:
    """FR-23: admin menyetujui/menolak data harga sebelum dipakai engine."""
    price = _get_or_404(db, Price, price_id, "Data harga")
    if payload.status == PriceStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Verifikasi harus berstatus approved atau rejected.",
        )

    price.status = payload.status
    db.add(
        PriceVerification(
            price_id=price.id,
            admin_id=admin.id,
            status=(
                PriceVerificationStatus.APPROVED
                if payload.status == PriceStatus.APPROVED
                else PriceVerificationStatus.REJECTED
            ),
            note=payload.note,
        )
    )
    db.flush()
    _append_history(db, price, action="changed", changed_by=admin.id)
    db.commit()
    db.refresh(price)
    name = db.get(Ingredient, price.ingredient_id)
    return _to_out(price, name.name if name else "-")


@router.delete(
    "/prices/{price_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminDep],
)
def delete_price(price_id: int, db: Session = Depends(get_db)) -> None:
    price = _get_or_404(db, Price, price_id, "Data harga")
    db.delete(price)
    db.commit()


# --------------------------------------------------------------------------
# Log scraper
# --------------------------------------------------------------------------
@router.get("/scraper-runs", response_model=list[ScraperRunOut], dependencies=[AdminDep])
def list_scraper_runs(db: Session = Depends(get_db)) -> list[ScraperRun]:
    return db.query(ScraperRun).order_by(ScraperRun.id.desc()).limit(50).all()


@router.post(
    "/scraper-runs",
    response_model=ScraperRunOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminDep],
)
def create_scraper_run(
    payload: ScraperRunCreate, db: Session = Depends(get_db)
) -> ScraperRun:
    now = datetime.now()
    run = ScraperRun(
        source=payload.source,
        started_at=now,
        finished_at=now,
        status=payload.status,
        items_count=payload.items_count,
        error_message=payload.error_message,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# --------------------------------------------------------------------------
# Statistik dashboard admin
# --------------------------------------------------------------------------
@router.get("/stats", response_model=AdminStatsOut, dependencies=[AdminDep])
def admin_stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    return AdminStatsOut(
        ingredients=db.query(Ingredient).count(),
        recipes=db.query(Recipe).count(),
        pending_prices=db.query(Price).filter(Price.status == PriceStatus.PENDING).count(),
        approved_prices=db.query(Price).filter(Price.status == PriceStatus.APPROVED).count(),
        users=db.query(User).count(),
        scraper_failures=db.query(ScraperRun).filter(ScraperRun.status == ScraperStatus.FAILED).count(),
    )
