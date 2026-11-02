"""Unggah CSV dataset oleh admin (FR-30).

Alur: unggah -> validasi -> pratinjau (``dry_run``) -> terapkan. Identitas baris
memakai ``code`` pada CSV sehingga unggah ulang memperbarui data, bukan menduplikasi.
Setelah data masuk, gizi per menu dihitung ulang dari bahan penyusunnya.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.dataset_import import BERKAS_TERKENAL, DatasetTidakValid, impor_berkas

router = APIRouter(prefix="/admin/import", tags=["admin-impor"])

AdminDep = Depends(require_roles(UserRole.ADMIN))

PETUNJUK = {
    'berkas_dikenali': list(BERKAS_TERKENAL),
    'cara_pakai': (
        'Unggah sekaligus berkas yang dimulai dengan nomor ini. Berkas 08/09/11 '
        'hanya dipakai notebook dan diabaikan di sini.'),
    'identitas_baris': 'code bahan (B001) dan code menu (M001) dipakai sebagai kunci',
}


@router.get("", summary="Petunjuk format impor")
def petunjuk(_: User = AdminDep) -> dict:
    return PETUNJUK


@router.post("", summary="Pratinjau atau terapkan impor CSV")
async def impor(
    berkas: list[UploadFile] = File(..., description='File CSV dataset'),
    region: str = Form('Kabupaten Madiun'),
    terapkan: bool = Form(False, description='False = pratinjau tanpa menulis'),
    db: Session = Depends(get_db),
    _: User = AdminDep,
) -> dict:
    if not berkas:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='Tidak ada berkas yang diunggah.')
    try:
        laporan = await impor_berkas(db, berkas, region_nama=region,
                                     dry_run=not terapkan)
    except DatasetTidakValid as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if laporan.get('jumlah_error') and not terapkan:
        laporan['tidak_bisa_diterapkan'] = True
        laporan['sebab'] = f"{laporan['jumlah_error']} baris bermasalah, perbaiki dulu"
    return laporan
