"""Skema Pydantic untuk mesin rekomendasi (FR-07 s.d. FR-11).

Kontrak input didefinisikan di sini supaya validasi tinggi badan, frekuensi
makan, alergi, dan batas nilai berlaku sama di web, mobile, dan notebook.
Alergen diverifikasi terhadap daftar yang benar-benar ada di tabel
`ingredients.allergens` — nilai tak dikenal ditolak, bukan diabaikan diam-diam
(kalau diabaikan, filter alergi tampak jalan padahal tidak menyaring apa pun).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Gender = Literal['laki-laki', 'perempuan']
Aktivitas = Literal['rendah', 'sedang', 'tinggi']
LevelSiswa = Literal['sd_1_3', 'sd_4_6', 'smp', 'sma', 'lainnya']

#: Alergen yang dikenali mesin. `santan` diturunkan ke `kelapa` oleh mesin.
ALERGEN_DIKENAL = {
    'ikan', 'seafood', 'kacang', 'kedelai', 'gluten', 'telur', 'kelapa', 'susu',
    'santan',
}


class AnggotaIn(BaseModel):
    """Satu anggota keluarga; tinggi badan wajib untuk BMI & energi aktual."""

    name: str = Field(min_length=2, max_length=100)
    age: int = Field(ge=1, le=120)
    gender: Gender
    weight_kg: float = Field(gt=0, le=250)
    height_cm: float = Field(ge=50, le=250)
    activity_level: Aktivitas = 'sedang'
    allergies: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def _cek_alergen(self) -> 'AnggotaIn':
        tak_dikenal = {str(a).strip().lower() for a in self.allergies} - ALERGEN_DIKENAL
        if tak_dikenal:
            raise ValueError(
                'Alergen tidak dikenal: ' + ', '.join(sorted(tak_dikenal))
                + f'. Pilihan yang tersedia: {", ".join(sorted(ALERGEN_DIKENAL))}.'
            )
        return self


class ProfilKeluargaIn(BaseModel):
    daily_budget: float = Field(gt=0, le=50_000_000)
    region: str = Field(min_length=3, max_length=100)
    meals_per_day: int = Field(default=3, ge=1, le=5,
                              description='Frekuensi makan per hari (1-5).')
    include_susu: bool = True
    preferences: list[str] = Field(default_factory=list)
    avoided_ingredients: list[str] = Field(default_factory=list)
    members: list[AnggotaIn] = Field(min_length=1, max_length=20)

    @model_validator(mode='after')
    def _gabungkan_alergen(self) -> 'ProfilKeluargaIn':
        if not any(m.allergies for m in self.members) and self.meals_per_day > 5:
            raise ValueError('Frekuensi makan maksimum 5 kali/hari.')
        return self

    @property
    def alergi(self) -> list[str]:
        return sorted({str(a).strip().lower() for m in self.members for a in m.allergies})


class KelompokSiswaIn(BaseModel):
    level: LevelSiswa
    student_count: int = Field(ge=0, le=100_000)
    budget_per_portion: float | None = Field(default=None, ge=0)


class ProfilSekolahIn(BaseModel):
    """Input petugas SPPG: sekolah binaan + kelompok penerima manfaat."""

    name: str = Field(min_length=3, max_length=150)
    region: str = Field(min_length=3, max_length=100)
    allergies: list[str] = Field(default_factory=list)
    groups: list[KelompokSiswaIn] = Field(min_length=1, max_length=20)

    @model_validator(mode='after')
    def _cek(self) -> 'ProfilSekolahIn':
        tak_dikenal = {str(a).strip().lower() for a in self.allergies} - ALERGEN_DIKENAL
        if tak_dikenal:
            raise ValueError('Alergen tidak dikenal: ' + ', '.join(sorted(tak_dikenal)))
        if sum(g.student_count for g in self.groups) <= 0:
            raise ValueError('Total siswa harus lebih dari 0.')
        return self


# ------------------------------------------------------------------- keluaran
class ItemPaket(BaseModel):
    slot: str
    recipe_id: int
    kode: str = ''
    nama_menu: str
    menutup: list[str] = Field(default_factory=list)
    biaya: float
    kalori: float
    protein: float
    kalsium_mg: float = 0
    besi_mg: float = 0
    vitamin_a_mcg: float = 0
    vitamin_c_mg: float = 0
    gula_g: float = 0
    natrium_mg: float = 0
    alergen: list[str] = Field(default_factory=list)
    score_nutrition: float
    score_budget: float
    score_seasonal: float
    score_local: float
    score_total: float


class RingkasanPaket(BaseModel):
    jumlah_komponen: int
    total_biaya: float
    sisa_anggaran: float
    pemakaian_anggaran: float
    total_kcal: float
    total_protein: float
    pct_kcal: float
    pct_protein: float
    gula_g: float
    natrium_mg: float
    gula_pct_energi: float
    patuh_anggaran: bool
    patuh_ggl: bool


class WaktuMakan(BaseModel):
    waktu: str
    anggaran_per_porsi: float
    paket: list[ItemPaket]
    ringkas: RingkasanPaket


class TargetAnggota(BaseModel):
    nama: str
    umur: int
    gender: str
    kelompok_akg: str
    bb: float
    tb: float
    aktivitas: str
    bmi: float
    status_gizi: str
    energi: float
    energi_akg: float
    protein: float
    dasar: str
    faktor_porsi: float
    z_bb_u: float | None = None
    z_tb_u: float | None = None
    z_imt_u: float | None = None
    alergi: list[str] = Field(default_factory=list)


class RencanaKeluarga(BaseModel):
    status: Literal['ok', 'infeasible']
    slot_wajib: list[str] = Field(default_factory=list)
    target: dict = Field(default_factory=dict)
    anggaran_per_porsi: float = 0
    waktu_makan: list[WaktuMakan] = Field(default_factory=list)
    selingan: list[dict] = Field(default_factory=list)
    total_biaya_harian: float = 0
    anggaran_harian: float = 0
    patuh_anggaran: bool = False
    peringatan: list[str] = Field(default_factory=list)
    penyesuaian: list[str] = Field(default_factory=list)
    variasi: float = 1.0
    alasan: str | None = None
    saran: str | None = None


class RencanaKelompok(BaseModel):
    level: str
    label: str
    siswa: int
    anggaran_per_porsi: float
    target_kcal: float
    target_protein: float
    paket: list[ItemPaket] = Field(default_factory=list)
    ringkas: RingkasanPaket | None = None
    biaya_batch: float = 0
    anggaran_batch: float = 0


class RencanaSppg(BaseModel):
    status: Literal['ok', 'infeasible']
    sekolah: str = ''
    wilayah: str = ''
    total_siswa: int = 0
    total_biaya: float = 0
    alergi: list[str] = Field(default_factory=list)
    kelompok: list[RencanaKelompok] = Field(default_factory=list)
    peringatan: list[str] = Field(default_factory=list)
    alasan: str | None = None
    saran: str | None = None


class DaftarBelanjaBaris(BaseModel):
    ingredient_id: int | None = None
    nama_bahan: str
    gram: float
    kg: float
    biaya: float


class DaftarBelanja(BaseModel):
    label: str
    faktor_porsi: float
    baris: list[DaftarBelanjaBaris] = Field(default_factory=list)
    total_biaya: float = 0
    peringatan: list[str] = Field(default_factory=list)


class RekomendasiRespons(BaseModel):
    model_config = ConfigDict(extra='allow')

    keluarga: RencanaKeluarga | None = None
    sppg: RencanaSppg | None = None
    belanja: DaftarBelanja | None = None
    sumber_data: dict = Field(default_factory=dict)
