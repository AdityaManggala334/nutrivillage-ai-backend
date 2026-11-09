"""Input harga lapangan oleh petugas (FR-23 diperluas).

Alur: petugas mencatat harga di pasar -> tersimpan `pending` dengan
`source_type=lapangan` dan `created_by` pengirim -> admin menyetujui lewat
halaman Verifikasi Harga yang sudah ada. Petugas hanya melihat kiriman dirinya
dan tidak bisa menghapus baris yang sudah diputuskan admin.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.ratelimit import client_ip, consume
from app.db.session import get_db
from app.models.catalog import Ingredient
from app.models.enums import PriceSourceType, PriceStatus
from app.models.price import Price
from app.models.user import User, UserRole
from app.schemas.field import FieldIngredientOut, FieldPriceCreate, FieldPriceOut

router = APIRouter(prefix="/field", tags=["field"])

#: Peran yang boleh memakai jalur ini.
_boleh = require_roles(UserRole.PETUGAS_LAPANGAN, UserRole.ADMIN)

#: Kiriman per jam per petugas. Longgar untuk pemakaian wajar, cukup ketat
#: untuk menahan banjir harga palsu.
KIRIM_PER_JAM = 60


def _out(db: Session, harga: Price) -> FieldPriceOut:
    bahan = db.get(Ingredient, harga.ingredient_id)
    return FieldPriceOut(
        id=harga.id,
        ingredient_id=harga.ingredient_id,
        price=float(harga.price),
        unit=harga.unit,
        recorded_date=harga.recorded_date,
        source=harga.source,
        status=harga.status.value,
        created_at=harga.created_at,
        ingredient_name=bahan.name if bahan else "",
        region_id=harga.region_id,
        created_by=harga.created_by,
    )


@router.get("/ingredients", response_model=list[FieldIngredientOut])
def daftar_bahan(
    db: Session = Depends(get_db),
    _: User = Depends(_boleh),
) -> list[Ingredient]:
    """Daftar bahan untuk pemilih input (baca saja)."""
    return db.query(Ingredient).order_by(Ingredient.name).all()


@router.get("/prices", response_model=list[FieldPriceOut])
def daftar_kiriman(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(_boleh),
) -> list[FieldPriceOut]:
    """Kiriman milik petugas ini. Admin melihat semua."""
    query = db.query(Price)
    if user.role != UserRole.ADMIN:
        query = query.filter(Price.created_by == user.id)
    if status_filter in {s.value for s in PriceStatus}:
        query = query.filter(Price.status == status_filter)
    rows = query.order_by(Price.recorded_date.desc(), Price.id.desc()).limit(200).all()
    return [_out(db, row) for row in rows]


@router.post("/prices", response_model=FieldPriceOut, status_code=status.HTTP_201_CREATED)
def kirim_harga(
    payload: FieldPriceCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_boleh),
) -> FieldPriceOut:
    """Catat harga dari lapangan. `status` dan `source_type` ditetapkan server."""
    kuota = consume(
        f"field:user:{user.id}",
        limit=KIRIM_PER_JAM,
        window_seconds=3600,
    )
    if not kuota.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Baru {KIRIM_PER_JAM} kiriman per jam. Coba lagi nanti.",
            headers={"Retry-After": str(kuota.retry_after)},
        )

    bahan = db.get(Ingredient, payload.ingredient_id)
    if bahan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bahan tidak ditemukan."
        )

    harga = Price(
        ingredient_id=bahan.id,
        region_id=payload.region_id,
        price=payload.price,
        unit=payload.unit,
        recorded_date=payload.recorded_date or date.today(),
        source_type=PriceSourceType.LAPANGAN,
        source=payload.source.strip(),
        status=PriceStatus.PENDING,
        created_by=user.id,
    )
    db.add(harga)
    db.commit()
    db.refresh(harga)
    return _out(db, harga)


@router.delete("/prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
def hapus_kiriman(
    price_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_boleh),
) -> None:
    """Tarik kembali kiriman sendiri, selama belum diputuskan admin."""
    harga = db.get(Price, price_id)
    if harga is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Data harga tidak ditemukan."
        )
    if user.role != UserRole.ADMIN and harga.created_by != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Bukan kiriman Anda."
        )
    if harga.status != PriceStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Data yang sudah diverifikasi tidak dapat dihapus.",
        )
    db.delete(harga)
    db.commit()
