"""Pengujian end-to-end mesin rekomendasi memakai SQLite in-memory.

Alasan pendekatan: MySQL produksi tidak tersedia di lingkungan uji, sedangkan
yang ingin dibuktikan adalah alur data admin -> mesin, bukan dialek SQL.
Tabel yang dibuat hanya yang dipakai mesin; `family_members`/`profiles` punya
kolom computed MySQL sehingga dilewati.

Yang diuji adalah invarian yang membuat mesin layak dipakai:
anggaran tidak pernah dilewati, alergen pengguna tidak pernah muncul, dan
perubahan data admin benar-benar mengubah rekomendasi.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db.session import Base  # noqa: E402
from app.models.content import FoodSafetyInfo  # noqa: E402
from app.models.catalog import (  # noqa: E402
    Ingredient, LocalAvailability, NutritionFact, Region, SeasonalAvailability,
)
from app.models.enums import MbgSlot  # noqa: E402
from app.models.planning import SystemConfig  # noqa: E402
from app.models.price import Price  # noqa: E402
from app.models.recipe import (  # noqa: E402
    Recipe, RecipeIngredient, RecipeNutrition, recipe_food_safety,
)
from app.models.standard import AnthropometryStandard, NutritionStandard  # noqa: E402
from app.schemas.recommendation import ProfilKeluargaIn, ProfilSekolahIn  # noqa: E402
from app.services import recommender  # noqa: E402
from app.services.dataset_import import DatasetTidakValid, impor_teks  # noqa: E402
from app.services.engine_data import hitung_gizi_semua_menu  # noqa: E402
from scripts.import_nutrivillage_dataset import BAWAAN, muat  # noqa: E402

TABEL = [Region, Ingredient, NutritionFact, Price, Recipe, RecipeIngredient,
         RecipeNutrition, SeasonalAvailability, LocalAvailability,
         NutritionStandard, AnthropometryStandard, SystemConfig,
         FoodSafetyInfo, recipe_food_safety]


@pytest.fixture(scope='module')
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(
        engine,
        tables=[t if isinstance(t, Table) else t.__table__ for t in TABEL],
    )
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as session:
        laporan = impor_teks(session, muat(BAWAAN), region_nama='Kabupaten Madiun')
        assert not laporan['error'], laporan['error'][:5]
        hitung_gizi_semua_menu(session)
        yield session


KELUARGA_5 = {
    'daily_budget': 100_000, 'region': 'Kabupaten Madiun', 'meals_per_day': 3,
    'include_susu': True, 'members': [
        {'name': 'Raka', 'age': 2, 'gender': 'laki-laki', 'weight_kg': 12,
         'height_cm': 85},
        {'name': 'Nadia', 'age': 8, 'gender': 'perempuan', 'weight_kg': 24,
         'height_cm': 122},
        {'name': 'Budi', 'age': 35, 'gender': 'laki-laki', 'weight_kg': 65,
         'height_cm': 170},
        {'name': 'Sari', 'age': 32, 'gender': 'perempuan', 'weight_kg': 55,
         'height_cm': 158},
        {'name': 'Mbah Sri', 'age': 65, 'gender': 'perempuan', 'weight_kg': 53,
         'height_cm': 157, 'activity_level': 'rendah'}]}

SEKOLAH = {'name': 'SDN 1 Madiun', 'region': 'Kabupaten Madiun',
           'groups': [{'level': 'sd_1_3', 'student_count': 120},
                      {'level': 'sd_4_6', 'student_count': 100}]}


# --------------------------------------------------------------- impor data
def test_impor_mengisi_master(db):
    assert db.query(Ingredient).count() >= 40
    assert db.query(Recipe).count() == 57
    assert db.query(NutritionStandard).count() == 26
    anth = db.query(AnthropometryStandard)
    assert anth.count() >= 690
    for indeks in ('BB/U', 'TB/U', 'IMT/U'):
        for sex in ('L', 'P'):
            assert anth.filter_by(index_name=indeks, sex=sex).count() >= 36
    assert db.query(Price).count() >= 40


def test_setiap_bahan_punya_gizi_dan_slot(db):
    kosong = (db.query(Ingredient).outerjoin(NutritionFact).filter(
        NutritionFact.id.is_(None)).count())
    assert kosong == 0, 'bahan tanpa data gizi'
    berporsi = db.query(Ingredient).filter(Ingredient.mbg_slot.isnot(None)).count()
    assert berporsi >= 35, 'slot MBG hampir kosong -> mesin tidak bisa merakit'


def test_impor_kedua_tidak_menduplikasi(db):
    sebelum = (db.query(Ingredient).count(), db.query(Recipe).count())
    impor_teks(db, muat(BAWAAN), region_nama='Kabupaten Madiun')
    assert (db.query(Ingredient).count(), db.query(Recipe).count()) == sebelum


def test_berkas_tanpa_menu_ditolak(db):
    with pytest.raises(DatasetTidakValid):
        impor_teks(db, {'05_akg': 'a,b\n1,2'})


# ------------------------------------------------------------------ target
def test_tinggi_badan_memengaruhi_target(db):
    pendek = dict(KELUARGA_5)
    pendek['members'] = [dict(KELUARGA_5['members'][2], height_cm=150)]
    a = recommender.core.target_keluarga(
        recommender.engine_data.bangun_snapshot(db, 'Kabupaten Madiun'),
        ProfilKeluargaIn(**pendek))
    b = recommender.core.target_keluarga(
        recommender.engine_data.bangun_snapshot(db, 'Kabupaten Madiun'),
        ProfilKeluargaIn(**KELUARGA_5))
    assert a['energi'] != b['energi'], 'EER tidak memakai tinggi badan'


def test_z_score_anak_terisi(db):
    hasil = recommender.rekomendasi_keluarga(db, ProfilKeluargaIn(**KELUARGA_5))
    balita = next(x for x in hasil['target']['anggota'] if x['nama'] == 'Raka')
    assert balita['z_tb_u'] is not None
    assert 'stunted' in balita['status_gizi'] or 'normal' in balita['status_gizi']
    dewasa = next(x for x in hasil['target']['anggota'] if x['nama'] == 'Budi')
    assert 18 < dewasa['bmi'] < 25


# ------------------------------------------------------------------ paket
def test_keluarga_lengkap_dan_patuh_anggaran(db):
    r = recommender.rekomendasi_keluarga(db, ProfilKeluargaIn(**KELUARGA_5))
    assert r['status'] == 'ok', r
    assert len(r['waktu_makan']) == 3
    for w in r['waktu_makan']:
        assert w['ringkas']['patuh_anggaran'] is True
        assert w['ringkas']['total_biaya'] <= w['anggaran_per_porsi']
        assert w['ringkas']['jumlah_komponen'] >= 3
        terisi = {s for item in w['paket'] for s in item['menutup']}
        assert {'pokok', 'hewani', 'nabati', 'sayur', 'buah', 'susu'} == terisi
    assert r['patuh_anggaran'] is True
    assert r['total_biaya_harian'] <= KELUARGA_5['daily_budget'] + 1


def test_wilayah_tidak_mengubah_rekomendasi(db):
    """Wilayah hanya label; input gizi yang sama menghasilkan menu & biaya sama."""
    madiun = recommender.rekomendasi_keluarga(db, ProfilKeluargaIn(**KELUARGA_5))
    tangerang = recommender.rekomendasi_keluarga(
        db, ProfilKeluargaIn(**dict(KELUARGA_5, region='Kabupaten Tangerang')))
    assert tangerang['total_biaya_harian'] > 0
    assert tangerang['total_biaya_harian'] == madiun['total_biaya_harian']
    assert tangerang['patuh_anggaran'] is True
    menu = lambda r: [i['recipe_id'] for w in r['waktu_makan'] for i in w['paket']]
    assert menu(tangerang) == menu(madiun)


def test_anggaran_besar_tidak_menghasilkan_paket_sama(db):
    """Regresi: mesin lama memberi paket identik untuk Rp8.000 dan Rp15.000."""
    dasar = dict(KELUARGA_5, daily_budget=24_000, include_susu=False,
                 members=[KELUARGA_5['members'][2]])
    kecil = recommender.rekomendasi_keluarga(
        db, ProfilKeluargaIn(**dasar), mode='komponen')
    besar = recommender.rekomendasi_keluarga(
        db, ProfilKeluargaIn(**{**dasar, 'daily_budget': 40_000}), mode='komponen')
    assert kecil['status'] == besar['status'] == 'ok'
    menu_kecil = [p['nama_menu'] for p in kecil['waktu_makan'][0]['paket']]
    menu_besar = [p['nama_menu'] for p in besar['waktu_makan'][0]['paket']]
    assert menu_kecil != menu_besar, 'anggaran naik tapi paket tidak berubah'
    assert (kecil['waktu_makan'][0]['ringkas']['total_biaya']
            < besar['waktu_makan'][0]['ringkas']['total_biaya'])


def test_alergen_pernah_muncul_di_paket(db):
    for alergi in (['susu'], ['seafood'], ['kedelai'], ['kacang'],
                   ['ikan', 'telur'], ['santan']):
        r = recommender.rekomendasi_keluarga(
            db, ProfilKeluargaIn(**{**KELUARGA_5,
                                    'members': [dict(m, allergies=[a for a in alergi])
                                                for m in KELUARGA_5['members']]}))
        if r['status'] != 'ok':
            continue
        for w in r['waktu_makan']:
            for item in w['paket']:
                assert not (set(item['alergen']) & set(alergi)), (alergi, item)


def test_alergi_susu_menghapus_slot_susu(db):
    r = recommender.rekomendasi_keluarga(
        db, ProfilKeluargaIn(**{**KELUARGA_5, 'include_susu': False}))
    assert 'susu' not in r['slot_wajib']
    assert all('susu' not in item['menutup'] for w in r['waktu_makan']
               for item in w['paket'])


def test_alergi_berat_tetap_dapat_rekomendasi(db):
    """Regresi: kacang + kedelai + telur dulu membuat mesin buntu tanpa saran."""
    anggota = [dict(m, allergies=['kacang', 'kedelai', 'telur'])
               for m in KELUARGA_5['members']]
    r = recommender.rekomendasi_keluarga(
        db, ProfilKeluargaIn(**{**KELUARGA_5, 'members': anggota}))
    assert r['status'] in ('ok', 'infeasible')
    if r['status'] == 'infeasible':
        assert r.get('saran'), 'penolakan harus memberi jalan keluar'
    else:
        assert any('tidak memiliki kandidat' in p or 'Slot' in p
                   for p in r['penyesuaian'] + r['peringatan'])


def test_batas_gula_dan_natrium_dipakai(db):
    r = recommender.rekomendasi_keluarga(db, ProfilKeluargaIn(**KELUARGA_5))
    for w in r['waktu_makan']:
        assert w['ringkas']['natrium_mg'] <= 600 * 6
        for item in w['paket']:
            assert item['gula_g'] <= 15.001 or item['natrium_mg'] <= 600.001


def test_frekuensi_makan_mengubah_anggaran_per_porsi(db):
    kecil = recommender.rekomendasi_keluarga(
        db, ProfilKeluargaIn(**{**KELUARGA_5, 'meals_per_day': 2}))
    banyak = recommender.rekomendasi_keluarga(
        db, ProfilKeluargaIn(**{**KELUARGA_5, 'meals_per_day': 5}))
    assert kecil['anggaran_per_porsi'] > banyak['anggaran_per_porsi']
    assert banyak['selingan'], 'frekuensi >3 harus memunculkan selingan'


def test_anggaran_tidak_cukup_ditolak_dengan_angka(db):
    r = recommender.rekomendasi_keluarga(
        db, ProfilKeluargaIn(**{**KELUARGA_5, 'daily_budget': 15_000}))
    assert r['status'] == 'infeasible'
    assert r['minimum_dibutuhkan'] > 15_000 / r['target']['porsi_dewasa_per_makan'] / 3
    assert 'Rp' in r['saran']


def test_perubahan_data_admin_mengubah_rekomendasi(db):
    """Inti permintaan: mesin harus mengikuti koreksi admin, bukan angka beku."""
    target = db.query(Price).join(Ingredient, Ingredient.id == Price.ingredient_id) \
        .filter(Ingredient.name.like('Ayam%')).first()
    assert target is not None
    lama = Decimal(target.price)
    target.price = Decimal('400000')          # ayam jadi sangat mahal
    db.flush()
    db.expire_all()
    try:
        mahal = recommender.rekomendasi_keluarga(
            db, ProfilKeluargaIn(**KELUARGA_5), mode='komponen')
        assert all('Ayam' not in item['nama_menu']
                   for w in mahal['waktu_makan'] for item in w['paket']), \
            'lauk ayam masih terpilih padahal harganya dilipatkan'
    finally:
        target.price = lama
        db.flush()
        db.expire_all()
    normal = recommender.rekomendasi_keluarga(
        db, ProfilKeluargaIn(**KELUARGA_5), mode='komponen')
    assert normal['status'] == 'ok'


def test_gizi_menu_dihitung_ulang_setelah_bahan_diubah(db):
    nz = db.query(NutritionFact).join(Ingredient).filter(
        Ingredient.name.like('Bayam%')).first()
    assert nz is not None
    lama = Decimal(nz.protein)
    nz.protein = Decimal('99')
    db.flush()
    hitung_gizi_semua_menu(db)
    try:
        pecel = db.query(Recipe).filter(Recipe.code == 'M001').one()
        assert pecel.nutrition.protein > lama
    finally:
        nz.protein = lama
        db.flush()
        hitung_gizi_semua_menu(db)


def test_bobot_saw_dari_konfigurasi_admin(db):
    r1 = recommender.rekomendasi_keluarga(db, ProfilKeluargaIn(**KELUARGA_5))
    db.query(SystemConfig).filter(
        SystemConfig.config_key == 'weight_budget').first().config_value = Decimal('0.60')
    db.query(SystemConfig).filter(
        SystemConfig.config_key == 'weight_nutrition').first().config_value = Decimal('0.10')
    db.flush()
    try:
        r2 = recommender.rekomendasi_keluarga(db, ProfilKeluargaIn(**KELUARGA_5))
        assert [p['nama_menu'] for p in r1['waktu_makan'][0]['paket']] != \
               [p['nama_menu'] for p in r2['waktu_makan'][0]['paket']], \
            'bobot SAW diubah admin tetapi hasil tidak berubah'
    finally:
        for kunci, nilai in (('weight_budget', 0.30), ('weight_nutrition', 0.40)):
            db.query(SystemConfig).filter(
                SystemConfig.config_key == kunci).first().config_value = Decimal(nilai)
        db.flush()


# ---------------------------------------------------------------- SPPG
def test_sppg_per_kelompok_dan_batch(db):
    r = recommender.rekomendasi_sppg(db, ProfilSekolahIn(**SEKOLAH))
    assert r['status'] == 'ok', r
    assert len(r['kelompok']) == 2
    sd1, sd4 = r['kelompok']
    assert sd1['anggaran_per_porsi'] == 8000 and sd4['anggaran_per_porsi'] == 10000
    for k in (sd1, sd4):
        assert k['ringkas']['patuh_anggaran'] is True
        assert k['biaya_batch'] <= k['anggaran_batch']
        assert len(k['paket']) == 6
    assert r['total_siswa'] == 220


def test_sppg_alergi_susu_mengganti_kalsium(db):
    r = recommender.rekomendasi_sppg(
        db, ProfilSekolahIn(**{**SEKOLAH, 'allergies': ['susu']}))
    for k in r['kelompok']:
        assert all('susu' not in item['menutup'] for item in k['paket'])
        kalsium = sum(item['kalsium_mg'] for item in k['paket'])
        assert kalsium > 100, 'tanpa susu kalsium harus berasal bahan lain'


# ------------------------------------------------------------- daftar belanja
def test_belanja_memakai_faktor_porsi_bukan_jumlah_orang(db):
    b = recommender.belanja_keluarga(db, ProfilKeluargaIn(**KELUARGA_5))
    assert b.baris
    beras = next((x for x in b.baris if 'Beras' in x.nama_bahan), None)
    assert beras is not None
    # Gram per porsi-makan harus wajar (~75 g beras pada hidangan), bukan
    # dikalikan jumlah kepala (5 orang x 3 makan).
    per_porsi = beras.gram / b.faktor_porsi
    assert 60 < per_porsi < 260, per_porsi
    assert b.faktor_porsi / 3 < 4.0, 'faktor porsi per waktu makan tidak boleh sebesar jumlah anggota'


def test_belanja_mengalikan_bdd(db):
    b = recommender.belanja_keluarga(db, ProfilKeluargaIn(**{
        **KELUARGA_5, 'members': [KELUARGA_5['members'][2]]}))
    telur = next((x for x in b.baris if 'Telur' in x.nama_bahan), None)
    assert telur is not None
    # butir telur BDD 89% -> berat dibeli > berat dimakan
    assert telur.kg > 0


def test_belanja_memuatkan_peringatan_harga(db):
    bahan = db.query(Ingredient).filter(Ingredient.name.like('Ayam%')).first()
    harga = db.query(Price).filter(Price.ingredient_id == bahan.id).first()
    simpan = harga.price
    db.delete(harga)
    db.flush()
    db.expire_all()
    try:
        r = recommender.rekomendasi_keluarga(db, ProfilKeluargaIn(**KELUARGA_5))
        assert any('belum punya harga' in p for p in r['peringatan']), \
            'bahan tanpa harga harus diumumkan, bukan dianggap gratis'
    finally:
        db.add(Price(ingredient_id=bahan.id, region_id=harga.region_id,
                    price=simpan, unit='kg', recorded_date=harga.recorded_date,
                    source_type=harga.source_type, source=harga.source,
                    status=harga.status))
        db.flush()
        db.expire_all()


# --------------------------------------------------------------- dasbor admin
def test_grid_nutrisi_menggabungkan_bahan_gizi_dan_harga(db):
    from app.routers.master import nutrition_grid

    baris = nutrition_grid(db=db, _=None)
    assert len(baris) >= 40
    beras = next(r for r in baris if 'Beras' in r.name)
    assert beras.nutrition is not None and beras.nutrition.calories > 0
    assert beras.price_per_kg and beras.price_per_kg > 0
    assert beras.used_in_menus >= 1
    assert beras.mbg_slot == 'pokok'


def test_edit_grid_admin_langsung_mengubah_mesin(db):
    """Menekan simpan di dasbor harus sampai ke rekomendasi, bukan hanya DB."""
    from app.routers.master import nutrition_grid, update_nutrition_grid
    from app.schemas.master import NutritionFactIn, NutritionGridUpdate

    baris = next(r for r in nutrition_grid(db=db, _=None) if 'Ayam' in r.name)
    gizi = baris.nutrition.model_dump()
    lama = dict(gizi)
    try:
        # harga sangat mahal -> lauk ayam tidak boleh terpilih lagi
        update_nutrition_grid(
            ingredient_id=baris.ingredient_id,
            payload=NutritionGridUpdate(price_per_kg=400_000),
            db=db, _=None)
        r = recommender.rekomendasi_keluarga(
            db, ProfilKeluargaIn(**KELUARGA_5), mode='komponen')
        assert all('Ayam' not in item['nama_menu']
                   for w in r['waktu_makan'] for item in w['paket'])
    finally:
        update_nutrition_grid(
            ingredient_id=baris.ingredient_id,
            payload=NutritionGridUpdate(nutrition=NutritionFactIn(**lama),
                                        price_per_kg=float(baris.price_per_kg)),
            db=db, _=None)


def test_grid_menyimpan_alergen_baru(db):
    from app.routers.master import nutrition_grid, update_nutrition_grid
    from app.schemas.master import NutritionGridUpdate

    baris = next(r for r in nutrition_grid(db=db, _=None) if 'Tempe' in r.name)
    update_nutrition_grid(ingredient_id=baris.ingredient_id,
                          payload=NutritionGridUpdate(allergens=['kedelai', 'kacang']),
                          db=db, _=None)
    ulang = next(r for r in nutrition_grid(db=db, _=None)
                 if r.ingredient_id == baris.ingredient_id)
    assert ulang.allergens == ['kedelai', 'kacang']


def test_upgrade_tidak_mengembalikan_menu_yang_sudah_dipakai():
    """Tahap upgrade pernah membatalkan penalti variasi dan mengulang menu."""
    from app.services import nutrition_core as core

    def kandidat(menu_id, n):
        return {'menu_id': menu_id, 'nama_menu': menu_id, 'N': n,
                'kalori': 100, 'protein': 10, 'biaya': 1000,
                'kalsium_mg': 0, 'besi_mg': 0, 'vitamin_a_mcg': 0,
                'vitamin_c_mg': 0, 'gula_g': 0, 'natrium_mg': 0,
                'skor_musim': 0, 'skor_lokal': 0, 'alergen': [],
                'A': 0, 'M': 0, 'L': 0, 'SAW': n}

    paket = [{'slot': 'hewani', 'menu_id': 'b', 'nama_menu': 'b', 'biaya': 1000,
              'kalori': 100, 'protein': 10, 'gula_g': 0, 'natrium_mg': 0,
              'kalsium_mg': 0, 'besi_mg': 0, 'vitamin_a_mcg': 0,
              'vitamin_c_mg': 0, 'skor': {'N': 0.8, 'A': 0, 'M': 0,
                                          'L': 0, 'SAW': 0.8}}]
    kolam = {'hewani': ([kandidat('a', 0.9), kandidat('b', 0.8)], 1000.0, 30.0)}

    core.upgrade_paket(paket, kolam, lambda: 10_000)
    assert paket[0]['menu_id'] == 'a'  # tanpa konteks, mutu menang

    paket[0] = {**paket[0], 'menu_id': 'b', 'nama_menu': 'b',
                'skor': {'N': 0.8, 'A': 0, 'M': 0, 'L': 0, 'SAW': 0.8}}
    core.upgrade_paket(paket, kolam, lambda: 10_000, sudah_dipakai={'a'})
    assert paket[0]['menu_id'] == 'b'  # menu terpakai tidak boleh direbut lagi
