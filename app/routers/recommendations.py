"""Router rekomendasi paket makan (FR-07 s.d. FR-11).

Mesin dijalankan dari data di basis data, jadi hasil endpoint ini selalu sama
dengan angka yang ditampilkan dasbor admin. Hasil dihitung lalu disimpan ke
`recommendations` + `recommendation_items` supaya dapat ditelusuri dan dijelaskan
LLM setelahnya.

Mode akses: boleh tanpa login (tamu di halaman Explore), tetapi riwayat hanya
tersimpan bila token penguna disertakan.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_optional_user, require_roles
from app.core.ratelimit import client_ip, consume
from app.db.session import get_db
from app.models.catalog import Region
from app.models.family import FamilyProfile
from app.models.history import HistoryEntry
from app.models.enums import HistoryKind
from app.models.planning import Recommendation, RecommendationItem, SystemConfig
from app.models.user import User, UserRole
from app.schemas.recommendation import (
    DaftarBelanja, ProfilKeluargaIn, ProfilSekolahIn, RekomendasiRespons,
    RencanaKeluarga, RencanaSppg,
)
from app.services import recommender
from app.services.engine_data import bangun_snapshot, hitung_gizi_semua_menu

router = APIRouter(prefix="/recommendations", tags=["rekomendasi"])

AdminDep = Depends(require_roles(UserRole.ADMIN))

#: Kuota generate (FR-35) dipindah ke backend agar berlaku untuk web maupun
#: aplikasi mobile. Sebelumnya hanya ada di lapisan Next.js sehingga bisa
#: dilewati dengan memanggil FastAPI langsung.
GENERATE_PER_HOUR = 5


def pengguna_opsional(user: User | None = Depends(get_optional_user)) -> User | None:
    """Pemakai dengan token sah; None untuk mode tanpa login."""
    return user


def kuota_generate(
    request: Request, user: User | None, *, aksi: str = "generate", limit: int = GENERATE_PER_HOUR
) -> None:
    """Batasi perhitungan rekomendasi per akun (tamu: per IP pengirim)."""
    kunci = (
        f"gen:{aksi}:user:{user.id}" if user else f"gen:{aksi}:ip:{client_ip(request)}"
    )
    hasil = consume(kunci, limit=limit, window_seconds=3600)
    if not hasil.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Kuota {aksi} {limit}x per jam sudah terpakai. Coba lagi nanti."
            ),
            headers={"Retry-After": str(hasil.retry_after)},
        )


def _lengkap_rencana(db: Session, profil: ProfilKeluargaIn, mode: str) -> dict:
    if mode not in ('hidangan', 'komponen'):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="mode harus 'hidangan' atau 'komponen'.")
    snapshot = bangun_snapshot(db, profil.region)
    if snapshot['jumlah_menu'] == 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Belum ada data menu/bahan. Jalankan import dataset NutriVillage.')
    hasil = recommender.rekomendasi_keluarga(db, profil, mode=mode)
    _simpan(db, profil, hasil)
    return hasil


def _simpan(db: Session, profil: ProfilKeluargaIn, hasil: dict) -> None:
    """Simpan hasil sebagai riwayat rekomendasi (deterministik dari data saat itu)."""
    if hasil.get('status') != 'ok':
        return
    region = db.query(Region).filter(Region.name == profil.region).one_or_none()
    row = Recommendation(
        user_id=None, budget=profil.daily_budget, family_count=len(profil.members),
        region_id=region.id if region else None, month=date.today().month,
        status='completed')
    db.add(row)
    db.flush()
    rank = 0
    untuk = hasil.get('waktu_makan') or []
    for w in untuk:
        for item in w.get('paket') or []:
            rank += 1
            db.add(RecommendationItem(
                recommendation_id=row.id, recipe_id=item['recipe_id'],
                score_nutrition=item['score_nutrition'], score_budget=item['score_budget'],
                score_seasonal=item['score_seasonal'], score_local=item['score_local'],
                score_total=item['score_total'], estimated_cost=item['biaya'],
                rank=rank, is_selected=(rank == 1)))
    db.commit()


@router.get("/meta", tags=["rekomendasi"])
def meta(db: Session = Depends(get_db)) -> dict:
    """Sumber data yang sedang dipakai mesin + bobot SAW dari konfigurasi admin."""
    snapshot = bangun_snapshot(db)
    bobot = {c.config_key: float(c.config_value) for c in db.query(SystemConfig)}
    return {
        'jumlah_menu': snapshot['jumlah_menu'],
        'jumlah_bahan': len(snapshot.get('bahan') or {}),
        'bobot_saw': bobot,
        'bobot_dipakai': snapshot['bobot'],
        'bahan_tanpa_harga': snapshot['bahan_tanpa_harga'],
        'catatan_bobot': ('bobot di system_config dinormalkan ulang bila '
                          'jumlahnya bukan 1,0'),
    }


@router.post("/keluarga", response_model=RekomendasiRespons)
def rekomendasi_keluarga(
    payload: ProfilKeluargaIn,
    request: Request,
    mode: str = 'hidangan',
    db: Session = Depends(get_db),
    user: User | None = Depends(pengguna_opsional),
) -> RekomendasiRespons:
    """Paket makan keluarga untuk seluruh waktu makan sesuai frekuensi."""
    kuota_generate(request, user)
    hasil = _lengkap_rencana(db, payload, mode)
    rencana = RencanaKeluarga(**hasil)
    belanja = (recommender.belanja_keluarga(db, payload, hasil)
               if hasil.get('status') == 'ok' else None)
    if user is not None and hasil.get('status') == 'ok':
        _riwayat(db, user, hasil)
    return RekomendasiRespons(keluarga=rencana, belanja=belanja,
                              sumber_data=meta(db))


@router.post("/sppg", response_model=RekomendasiRespons)
def rekomendasi_sppg(
    payload: ProfilSekolahIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(pengguna_opsional),
) -> RekomendasiRespons:
    """Paket MBG per kelompok penerima manfaat, dengan anggaran BGN per tingkat."""
    kuota_generate(request, user)
    snapshot = bangun_snapshot(db, payload.region)
    if snapshot['jumlah_menu'] == 0:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail='Belum ada data menu/bahan. Import dataset dulu.')
    hasil = recommender.rekomendasi_sppg(db, payload)
    return RekomendasiRespons(sppg=RencanaSppg(**hasil), sumber_data=meta(db))


@router.post("/belanja", response_model=DaftarBelanja)
def belanja(
    payload: ProfilKeluargaIn,
    request: Request,
    mode: str = 'hidangan',
    db: Session = Depends(get_db),
    user: User | None = Depends(pengguna_opsional),
) -> DaftarBelanja:
    """Daftar belanja bahan mentah, diskalakan faktor porsi bukan jumlah kepala."""
    # Bucket sendiri: satu aksi pengguna bisa memanggil /keluarga lalu /belanja.
    kuota_generate(request, user, aksi="belanja", limit=20)
    hasil = _lengkap_rencana(db, payload, mode)
    return recommender.belanja_keluarga(db, payload, hasil)


@router.post("/hitung-gizi-menu", tags=["rekomendasi"])
def segarkan_gizi_menu(db: Session = Depends(get_db), _: User = AdminDep) -> dict:
    """Hitung ulang gizi per menu dari data bahan.

    Dipakai setelah admin mengoreksi gizi/alergen/BDD dalam jumlah besar, karena
    gizi menu bersifat turunan dan tidak dapat diedit langsung.
    """
    return {'menu_diperbarui': hitung_gizi_semua_menu(db)}


def _riwayat(db: Session, user: User, hasil: dict) -> None:
    """Simpan menu pilihan pertama ke riwayat penguna (FR-04)."""
    waktu = hasil.get('waktu_makan') or []
    if not waktu or not waktu[0].get('paket'):
        return
    db.add(HistoryEntry(user_id=user.id, kind=HistoryKind.RECOMMENDATION,
                        recipe_id=waktu[0]['paket'][0]['recipe_id'],
                        note=f"{waktu[0]['waktu']} · {len(waktu)} waktu makan"))
    db.commit()
