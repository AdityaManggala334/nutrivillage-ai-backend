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
from app.services.dataset_import import (
    BERKAS_TERKENAL,
    MAKS_BERKAS_JUMLAH,
    MAKS_BERKAS_MB,
    WILAYAH_DIIZINKAN,
    DatasetTidakValid,
    impor_berkas,
)

router = APIRouter(prefix="/admin/import", tags=["admin-impor"])

AdminDep = Depends(require_roles(UserRole.ADMIN))
MAKS_BYTE = MAKS_BERKAS_MB * 1024 * 1024

PETUNJUK = {
    'berkas_dikenali': list(BERKAS_TERKENAL),
    'cara_pakai': (
        'Unggah sekaligus berkas yang dimulai dengan nomor ini. Berkas 08/09/11 '
        'hanya dipakai notebook dan diabaikan di sini.'),
    'identitas_baris': 'code bahan (B001) dan code menu (M001) dipakai sebagai kunci',
    # Angka ini dibaca layar admin supaya batas yang ditampilkan = batas yang ditegakkan.
    'maks_mb_per_berkas': MAKS_BERKAS_MB,
    'maks_jumlah_berkas': MAKS_BERKAS_JUMLAH,
    'wilayah_dikenali': list(WILAYAH_DIIZINKAN),
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
    if len(berkas) > MAKS_BERKAS_JUMLAH:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f'Maksimal {MAKS_BERKAS_JUMLAH} berkas per unggahan.',
        )
    for item in berkas:
        nama = (item.filename or "").lower()
        if not nama.endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f'Berkas "{item.filename}" bukan CSV.',
            )
        # `size` dilaporkan parser multipart, jadi tidak perlu memuat isi berkas.
        ukuran = item.size or 0
        if ukuran > MAKS_BYTE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f'Berkas "{item.filename}" berukuran {ukuran // (1024 * 1024)} MB; '
                    f'batas {MAKS_BERKAS_MB} MB per berkas.'
                ),
            )
    if region not in WILAYAH_DIIZINKAN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f'Wilayah "{region}" tidak dikenali. Pilihan sah: '
                + ', '.join(WILAYAH_DIIZINKAN) + '.'
            ),
        )
    try:
        laporan = await impor_berkas(db, berkas, region_nama=region,
                                     dry_run=not terapkan)
    except DatasetTidakValid as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if laporan.get('jumlah_error') and not terapkan:
        laporan['tidak_bisa_diterapkan'] = True
        laporan['sebab'] = f"{laporan['jumlah_error']} baris bermasalah, perbaiki dulu"
    laporan['wilayah'] = region
    return laporan
