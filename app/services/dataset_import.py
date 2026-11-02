"""Impor dataset NutriVillage ke basis data yang dipakai admin & mesin.

Dipakai dua jalur, satu implementasi:

* `scripts/import_nutrivillage_dataset.py` — pengisian awal / development.
* `POST /api/v1/admin/import` — unggah CSV oleh admin di dasbor.

Identitas baris memakai `code` dari CSV (B001 untuk bahan, M001 untuk menu),
sehingga mengunggah file yang sama dua kali memperbarui data, bukan menduplikasi.
Semua baris divalidasi sebelum ditulis; baris bermasalah dilaporkan per nomor
baris dan tidak menghentikan sisanya.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import (
    Ingredient, LocalAvailability, NutritionFact, Region, SeasonalAvailability,
)
from app.models.enums import (
    IngredientCategory, LocalLevel, MbgSlot, PriceSourceType, PriceStatus,
    RecipeCategory, SeasonalStatus,
)
from app.models.price import Price
from app.models.recipe import Recipe, RecipeIngredient
from app.models.planning import SystemConfig
from app.models.standard import AnthropometryStandard, NutritionStandard

# Kolom gizi yang disimpan sebagai kolom nyata (dibaca mesin). Sisanya masuk
# NutritionFact.details supaya data TKPI tidak hilang tanpa menambah 20 kolom.
KOLOH_MESIN = {'kalori_kcal': 'calories', 'protein_g': 'protein',
               'karbohidrat_g': 'carbs', 'lemak_total_g': 'fat', 'serat_g': 'fiber',
               'gula_g': 'sugar_g', 'natrium_mg': 'sodium_mg', 'kalsium_mg': 'calcium_mg',
               'besi_mg': 'iron_mg', 'vitamin_c_mg': 'vitamin_c_mg',
               'bdd_percent': 'bdd_percent'}

# Vitamin A: prioritas hasil hitung RAE, lalu retinol asli TKPI.
GIZI_LAIN = {
    'vitamin_a_rae_mcg': 'vitamin_a_mcg',
}

KATEGORI_KE_BAHAN = {
    'serealia': IngredientCategory.POKOK, 'umbi': IngredientCategory.POKOK,
    'daging': IngredientCategory.PROTEIN, 'telur': IngredientCategory.PROTEIN,
    'ikan': IngredientCategory.PROTEIN, 'kacang': IngredientCategory.PROTEIN,
    'sayur': IngredientCategory.SAYUR, 'buah': IngredientCategory.BUAH,
    'susu': IngredientCategory.SUSU, 'bumbu': IngredientCategory.BUMBU,
}
KATEGORI_KE_SLOT = {
    'serealia': MbgSlot.POKOK, 'umbi': MbgSlot.POKOK,
    'daging': MbgSlot.HEWANI, 'telur': MbgSlot.HEWANI, 'ikan': MbgSlot.HEWANI,
    'kacang': MbgSlot.NABATI, 'sayur': MbgSlot.SAYUR, 'buah': MbgSlot.BUAH,
    'susu': MbgSlot.SUSU,
}
KATEGORI_MENU_KE_RESEP = {
    'olahan_nasi': RecipeCategory.MAKANAN_UTAMA, 'pokok_nasi': RecipeCategory.MAKANAN_UTAMA,
    'pokok_umbi': RecipeCategory.MAKANAN_UTAMA, 'berkuah': RecipeCategory.BERKUAH,
    'sate_panggang': RecipeCategory.LAUK, 'botok_pepes': RecipeCategory.LAUK,
    'lauk_hewani': RecipeCategory.LAUK, 'lauk_nabati': RecipeCategory.LAUK,
    'sayur_tumis': RecipeCategory.SAYUR, 'sayur_kuah': RecipeCategory.SAYUR,
    'lalapan': RecipeCategory.SAYUR, 'buah_segar': RecipeCategory.CAMILAN,
    'susu_cair': RecipeCategory.MINUMAN,
}
STATUS_HARGA_KE_LOKAL = {
    'lokal_madiun': LocalLevel.ABUNDANT, 'survei_lapangan_madiun': LocalLevel.ABUNDANT,
    'jatim': LocalLevel.AVAILABLE, 'survei_lapangan_jatim': LocalLevel.AVAILABLE,
    'retail_regional': LocalLevel.LIMITED, 'survei_lapangan': LocalLevel.AVAILABLE,
}
PROVINSI_BAKU = 'Jawa Timur'


class DatasetTidakValid(ValueError):
    """Berkas yang diunggah bukan dataset NutriVillage yang lengkap."""



@dataclass
class HasilImpor:
    dibuat: dict = field(default_factory=dict)
    diperbarui: dict = field(default_factory=dict)
    error: list[dict] = field(default_factory=list)

    def ringkas(self) -> dict:
        return {'dibuat': self.dibuat, 'diperbarui': self.diperbarui,
                'jumlah_error': len(self.error), 'error': self.error[:50]}


def _normal(x):
    x = unicodedata.normalize('NFKD', str(x or '')).lower()
    x = re.sub(r'\([^)]*\)', ' ', x)
    x = re.sub(r'[^a-z0-9 ]', ' ', x)
    return re.sub(r'\s+', ' ', x).strip()


def _angka(x, baku=None):
    s = str(x if x is not None else '').strip().replace(',', '')
    if not s or s.lower() in ('nan', 'none', '-'):
        return baku
    try:
        return float(s)
    except ValueError:
        return baku


def _tanggal(x):
    for pola in ('%Y-%m-%d', '%m-%d-%y', '%d-%m-%Y'):
        try:
            return datetime.strptime(str(x).strip(), pola).date()
        except (ValueError, TypeError):
            continue
    return date.today()


def _baris(teks):
    return list(csv.DictReader(io.StringIO(teks.lstrip(''))))


def _pisah(teks):
    return [t.strip().lower() for t in str(teks or '').split(';') if t.strip()]


#: Berkas yang dikenali mesin. 08/09/11 hanya dipakai notebook, jadi diabaikan.
BERKAS_TERKENAL = ('01_menu_komponen', '02_bahan_gizi', '03_resep_komponen',
                   '04_harga_pangan', '05_akg', '06_musim_pangan',
                   '07_alergen_bahan', '10_antropometri_zscore')


def kenali(nama_berkas: str) -> str | None:
    kunci = (nama_berkas or '').split('/')[-1].replace(' ', '_')
    for logis in BERKAS_TERKENAL:
        if kunci.startswith(logis[:8]):
            return logis
    return None


def baca_berkas(berkas) -> dict[str, str]:
    """Terima file unggahan FastAPI -> {nama_logis: isi teks}."""
    keluaran = {}
    for item in berkas:
        logis = kenali(item.filename)
        if logis is None:
            continue
        isi = item.file.read()
        if isinstance(isi, bytes):
            isi = isi.decode('utf-8-sig', errors='replace')
        keluaran[logis] = isi
    return keluaran


async def impor_berkas(db: Session, berkas, region_nama: str = 'Kabupaten Madiun',
                       dry_run: bool = False) -> dict:
    """Versi asinkron untuk endpoint FastAPI (berkas masih di-disks async)."""
    terbaca = {}
    for item in berkas:
        logis = kenali(item.filename)
        if logis is None:
            continue
        isi = await item.read()
        terbaca[logis] = isi.decode('utf-8-sig', errors='replace') if isinstance(isi, bytes) else isi
    return impor_teks(db, terbaca, region_nama=region_nama, dry_run=dry_run)


# ------------------------------------------------------------------ writer
def _region(db: Session, nama: str) -> Region:
    r = db.scalar(select(Region).where(Region.name == nama))
    if r is None:
        r = Region(name=nama, province=PROVINSI_BAKU)
        db.add(r)
        db.flush()
    return r


def _registry_bahan(gizi_rows, resep_rows, harga_rows) -> dict:
    """Kumpulkan bahan yang benar-benar dipakai, bukan seluruh TKPI.

    1.959 baris `02_bahan_gizi.csv` adalah pustaka komposisi, bukan daftar bahan
    aplikasi. Bahan aplikasi = bahan yang muncul di resep atau punya harga.
    Kuncinya `bahan_id` (B001), dan tiap bahan menunjuk satu baris gizi.
    """
    by_id = {r.get('gizi_id', ''): r for r in gizi_rows}
    by_name = {}
    for r in gizi_rows:
        by_name.setdefault(_normal(r.get('nama_bahan')), r)

    keluaran: dict[str, dict] = {}

    def isi(kode, nama, gizi_id=None):
        if not kode:
            return
        entri = keluaran.setdefault(kode, {'nama': nama, 'gizi': None})
        if nama and not entri.get('nama'):
            entri['nama'] = nama
        if gizi_id and entri['gizi'] is None:
            entri['gizi'] = by_id.get(gizi_id)
        elif entri['gizi'] is None and nama:
            entri['gizi'] = by_name.get(_normal(nama))

    for r in harga_rows:
        isi((r.get('bahan_id') or '').strip(), (r.get('nama_bahan') or '').strip())
    for r in resep_rows:
        isi((r.get('bahan_id') or '').strip(), (r.get('nama_bahan') or '').strip(),
            (r.get('gizi_id') or '').strip())
    for kode, entri in keluaran.items():
        if entri['gizi'] is None and entri['nama']:
            entri['gizi'] = by_name.get(_normal(entri['nama']))
    return keluaran


def _siapkan_bahan(db: Session, registry, alergen_rows, hasil: HasilImpor):
    """Upsert Ingredient + NutritionFact dari registry bahan terpakai."""
    alergen_oleh_nama = {}
    for r in alergen_rows:
        alergen_oleh_nama[_normal(r.get('nama_bahan'))] = [
            a for a in _pisah(r.get('alergen')) if a]

    ada = {i.code: i for i in db.scalars(select(Ingredient)) if i.code}
    for kode, entri in sorted(registry.items()):
        nama = (entri.get('nama') or '').strip()
        if not nama:
            hasil.error.append({'berkas': '04_harga_pangan', 'baris': 0,
                                'kolom': 'nama_bahan',
                                'pesan': f'bahan {kode} tanpa nama'})
            continue
        g = entri.get('gizi') or {}
        kategori = (g.get('kategori_bahan') or '').strip()
        ins = ada.get(kode)
        if ins is None:
            ins = Ingredient(code=kode, name=nama[:100],
                             category=KATEGORI_KE_BAHAN.get(
                                 kategori, IngredientCategory.LAINNYA),
                             unit='kg')
            db.add(ins)
            hasil.dibuat['bahan'] = hasil.dibuat.get('bahan', 0) + 1
        else:
            ins.name = nama[:100]
            hasil.diperbarui['bahan'] = hasil.diperbarui.get('bahan', 0) + 1
        ins.mbg_slot = KATEGORI_KE_SLOT.get(kategori)
        ins.allergens = alergen_oleh_nama.get(_normal(nama), [])
        db.flush()

        nz = db.scalar(select(NutritionFact).where(NutritionFact.ingredient_id == ins.id))
        baru = nz is None
        nz = nz or NutritionFact(ingredient_id=ins.id)
        for sumber, tujuan in KOLOH_MESIN.items():
            baku = 100.0 if sumber == 'bdd_percent' else 0.0
            setattr(nz, tujuan, _angka(g.get(sumber), baku) or baku)
        for sumber, tujuan in GIZI_LAIN.items():
            setattr(nz, tujuan, _angka(g.get(sumber), 0.0))
        nz.details = {k: v for k, v in g.items()
                      if k not in ('gizi_id', 'nama_bahan', 'nama_normal',
                                   'kategori_bahan', 'asal_data', 'bahan_id',
                                   'vitamin_a_rae_mcg') and str(v).strip()}
        nz.source = (g.get('asal_data') or 'TKPI Kemenkes RI')[:100]
        db.add(nz)
        if baru:
            hasil.dibuat['gizi'] = hasil.dibuat.get('gizi', 0) + 1
        else:
            hasil.diperbarui['gizi'] = hasil.diperbarui.get('gizi', 0) + 1
    return {i.code: i for i in db.scalars(select(Ingredient)) if i.code}


def _siapkan_harga(db, harga_rows, bahan, region, hasil):
    existing = {}
    for p in db.scalars(select(Price).where(Price.region_id == region.id)):
        existing[p.ingredient_id] = p
    for i, r in enumerate(harga_rows, start=2):
        ins = bahan.get((r.get('bahan_id') or '').strip())
        harga = _angka(r.get('harga_per_kg'))
        if ins is None:
            hasil.error.append({'berkas': '04_harga_pangan', 'baris': i,
                                'kolom': 'bahan_id',
                                'pesan': f"bahan {r.get('bahan_id')} tidak dikenal"})
            continue
        if harga is None or harga < 0:
            hasil.error.append({'berkas': '04_harga_pangan', 'baris': i,
                                'kolom': 'harga_per_kg', 'pesan': 'harga tidak valid'})
            continue
        if harga == 0:
            continue
        lama = existing.get(ins.id)
        sama = (lama is not None and float(lama.price) == harga)
        if sama:
            continue
        db.add(Price(ingredient_id=ins.id, region_id=region.id, price=harga,
                     unit=(r.get('satuan') or 'kg')[:20],
                     recorded_date=_tanggal(r.get('tanggal_data')),
                     source_type=PriceSourceType.MANUAL,
                     source=(r.get('sumber') or r.get('status_verifikasi')
                             or 'impor dataset')[:150],
                     status=PriceStatus.APPROVED))
        key = 'harga'
        if lama:
            hasil.diperbarui[key] = hasil.diperbarui.get(key, 0) + 1
        else:
            hasil.dibuat[key] = hasil.dibuat.get(key, 0) + 1


def _siapkan_menu(db, menu_rows, gizi_rows, resep_rows, bahan, hasil):
    by_menu = {}
    for r in resep_rows:
        by_menu.setdefault(r['menu_id'], []).append(r)
    ada = {c: c for c in db.scalars(select(Recipe.code))}
    for i, r in enumerate(menu_rows, start=2):
        kode = (r.get('menu_id') or '').strip()
        nama = (r.get('nama_menu') or '').strip()
        if not kode or not nama:
            hasil.error.append({'berkas': '01_menu_komponen', 'baris': i,
                                'kolom': 'menu_id/nama_menu', 'pesan': 'kosong'})
            continue
        resep = db.scalar(select(Recipe).where(Recipe.code == kode))
        baru = resep is None
        resep = resep or Recipe(code=kode)
        resep.name = nama[:100]
        resep.category = KATEGORI_MENU_KE_RESEP.get(r.get('kategori'),
                                                    RecipeCategory.MAKANAN_UTAMA)
        resep.meal_kind = 'hidangan' if r.get('tipe') == 'hidangan' else 'komponen'
        resep.servings = 4 if resep.meal_kind == 'hidangan' else 1
        resep.description = (r.get('deskripsi') or '')[:2000] or None
        resep.is_local = bool(resep.meal_kind == 'komponen') or True
        db.add(resep)
        if baru:
            hasil.dibuat['menu'] = hasil.dibuat.get('menu', 0) + 1
        else:
            hasil.diperbarui['menu'] = hasil.diperbarui.get('menu', 0) + 1
        db.flush()

        for j, x in enumerate(by_menu.get(kode, [])):
            ins = bahan.get((x.get('bahan_id') or '').strip())
            gram = _angka(x.get('jumlah_g'))
            if ins is None or not gram or gram <= 0:
                hasil.error.append({'berkas': '03_resep_komponen',
                                    'kolom': 'bahan_id/jumlah_g',
                                    'pesan': f"{kode}: baris {j + 1} tidak lengkap"})
                continue
            lama = db.scalar(select(RecipeIngredient).where(
                RecipeIngredient.recipe_id == resep.id,
                RecipeIngredient.ingredient_id == ins.id))
            if lama is None:
                db.add(RecipeIngredient(recipe_id=resep.id, ingredient_id=ins.id,
                                        name=(x.get('nama_bahan') or ins.name)[:100],
                                        quantity=gram, unit='g'))
            else:
                lama.quantity = gram
                lama.name = (x.get('nama_bahan') or ins.name)[:100]



def _siapkan_musim(db, musim_rows, bahan, hasil):
    for i, r in enumerate(musim_rows, start=2):
        nama = (r.get('nama_bahan') or '').strip()
        ins = next((b for b in bahan.values() if _normal(b.name) == _normal(nama)), None)
        if ins is None:
            continue
        bulan = [int(x) for x in str(r.get('bulan_musim') or '').split(';')
                 if x.strip().isdigit()]
        ada = {s.month: s for s in db.scalars(
            select(SeasonalAvailability).where(SeasonalAvailability.ingredient_id == ins.id))}
        for m in range(1, 13):
            status = (SeasonalStatus.IN_SEASON if m in bulan
                      else SeasonalStatus.OFF_SEASON)
            if m in ada:
                if ada[m].status != status:
                    ada[m].status = status
                continue
            db.add(SeasonalAvailability(ingredient_id=ins.id, month=m, status=status))
            hasil.dibuat['musim'] = hasil.dibuat.get('musim', 0) + 1


def _siapkan_lokal(db, harga_rows, bahan, region, hasil):
    for r in harga_rows:
        ins = bahan.get((r.get('bahan_id') or '').strip())
        if ins is None:
            continue
        catatan = str(r.get('catatan') or '')
        status = ''
        for kunci, level in STATUS_HARGA_KE_LOKAL.items():
            if kunci in (str(r.get('wilayah') or '') + catatan).lower():
                status = level
                break
        if status is None or not status:
            continue
        lama = db.scalar(select(LocalAvailability).where(
            LocalAvailability.ingredient_id == ins.id,
            LocalAvailability.region_id == region.id))
        if lama is None:
            db.add(LocalAvailability(ingredient_id=ins.id, region_id=region.id,
                                     level=status, source=(r.get('sumber') or '')[:150]))
            hasil.dibuat['lokal'] = hasil.dibuat.get('lokal', 0) + 1
            lama = db.scalar(select(LocalAvailability).where(
                LocalAvailability.ingredient_id == ins.id))
        if lama is not None:
            lama.level = status
        ins.is_local = status != LocalLevel.LIMITED


BOBOT_BAKU = {'weight_nutrition': 0.40, 'weight_budget': 0.30,
              'weight_seasonal': 0.15, 'weight_local': 0.15}


def _siapkan_bobot(db: Session) -> None:
    """Pastikan bobot SAW ada di konfigurasi sistem agar admin dapat menyetelnya."""
    ada = {c.config_key for c in db.scalars(select(SystemConfig))}
    for kunci, nilai in BOBOT_BAKU.items():
        if kunci not in ada:
            db.add(SystemConfig(config_key=kunci, config_value=str(nilai)))


def _siapkan_akg(db, rows, hasil):
    ada = {(s.age_group, s.sex, s.physiology): s for s in db.scalars(select(NutritionStandard))}
    for i, r in enumerate(rows, start=2):
        key = ((r.get('kelompok_umur') or '').strip(),
               (r.get('jenis_kelamin') or 'Semua').strip(),
               (r.get('status_fisiologis') or 'Normal').strip())
        if not key[0]:
            hasil.error.append({'berkas': '05_akg', 'baris': i,
                                'kolom': 'kelompok_umur', 'pesan': 'kosong'})
            continue
        s = ada.get(key)
        baru = s is None
        s = s or NutritionStandard(code=(r.get('id_akg') or key[0])[:16],
                                   age_group=key[0], sex=key[1], physiology=key[2])
        s.energy_kcal = _angka(r.get('energi_kcal'), 0)
        s.protein_g = _angka(r.get('protein_g'), 0)
        s.fat_g = _angka(r.get('lemak_total_g'), 0)
        s.carb_g = _angka(r.get('karbohidrat_g'), 0)
        s.fiber_g = _angka(r.get('serat_g'), 0)
        s.calcium_mg = _angka(r.get('kalsium_mg'), 0)
        s.iron_mg = _angka(r.get('besi_mg'), 0)
        s.vitamin_a_mcg = _angka(r.get('vitamin_a_re'), 0)
        s.vitamin_c_mg = _angka(r.get('vitamin_c_mg'), 0)
        s.sodium_mg = _angka(r.get('natrium_mg'), 0)
        s.weight_kg = _angka(r.get('berat_badan_kg'))
        s.height_cm = _angka(r.get('tinggi_badan_cm'))
        db.add(s)
        k = 'akg'
        if baru:
            hasil.dibuat[k] = hasil.dibuat.get(k, 0) + 1
        else:
            hasil.diperbarui[k] = hasil.diperbarui.get(k, 0) + 1


def _siapkan_anthro(db, rows, hasil):
    ada = {(a.index_name, a.sex, float(a.age_month)): a
           for a in db.scalars(select(AnthropometryStandard))}
    for i, r in enumerate(rows, start=2):
        index = (r.get('indeks') or '').strip()
        sex = (r.get('gender') or '').strip()
        if index not in ('BB/U', 'PB/U', 'TB/U', 'BB/PB', 'BB/TB', 'IMT/U') or sex not in ('L', 'P'):
            hasil.error.append({'berkas': '10_antropometri', 'baris': i,
                                'kolom': 'indeks/gender',
                                'pesan': f'{index}/{sex} tidak dikenal'})
            continue
        if str(r.get('satuan_umur')) == 'tahun_bulan':
            bulan = int(_angka(r.get('tahun'), 0) * 12 + _angka(r.get('bulan'), 0))
        elif str(r.get('satuan_umur')) == 'bulan':
            bulan = int(_angka(r.get('x'), 0))
        else:
            continue                      # indeks berbasis cm, bukan umur
        nilai = [_angka(r.get(k), 0.0) for k in
                 ('minus3sd', 'minus2sd', 'minus1sd', 'median', 'plus1sd',
                  'plus2sd', 'plus3sd')]
        s = ada.get((index, sex, float(bulan)))
        baru = s is None
        s = s or AnthropometryStandard(index_name=index, sex=sex, age_month=bulan)
        s.minus3sd, s.minus2sd, s.minus1sd, s.median = nilai[0], nilai[1], nilai[2], nilai[3]
        s.plus1sd, s.plus2sd, s.plus3sd = nilai[4], nilai[5], nilai[6]
        db.add(s)
        if baru:
            hasil.dibuat['antropometri'] = hasil.dibuat.get('antropometri', 0) + 1


def impor_teks(db: Session, isi: dict[str, str], region_nama: str = 'Kabupaten Madiun',
               dry_run: bool = False) -> dict:
    """Terima isi CSV mentah per berkas lalu tulis ke basis data.

    ``isi`` berisi teks CSV (hasil baca berkas atau unggahan), dengan kunci nama
    logis seperti ``02_bahan_gizi``. Berkas yang tidak dikenal diabaikan.
    """
    hasil = HasilImpor()
    if '01_menu_komponen' not in isi or '02_bahan_gizi' not in isi:
        raise DatasetTidakValid(
            'Dataset wajib memuat 01_menu_komponen.csv dan 02_bahan_gizi.csv')
    for logis, teks in isi.items():
        if not str(teks).strip():
            hasil.error.append({'berkas': logis, 'baris': 0, 'kolom': '-',
                                'pesan': 'berkas kosong'})

    region = _region(db, region_nama or 'Kabupaten Madiun')
    gizi_rows = _baris(isi.get('02_bahan_gizi', ''))
    harga_rows = _baris(isi.get('04_harga_pangan', ''))
    resep_rows = _baris(isi.get('03_resep_komponen', ''))
    registry = _registry_bahan(gizi_rows, resep_rows, harga_rows)
    bahan = _siapkan_bahan(db, registry, _baris(isi.get('07_alergen_bahan', '')), hasil)
    _siapkan_menu(db, _baris(isi.get('01_menu_komponen', '')), gizi_rows,
                  resep_rows, bahan, hasil)
    _siapkan_harga(db, harga_rows, bahan, region, hasil)
    _siapkan_musim(db, _baris(isi.get('06_musim_pangan', '')), bahan, hasil)
    _siapkan_lokal(db, harga_rows, bahan, region, hasil)
    _siapkan_bobot(db)
    _siapkan_akg(db, _baris(isi.get('05_akg', '')), hasil)
    _siapkan_anthro(db, _baris(isi.get('10_antropometri_zscore', '')), hasil)

    db.flush()
    laporan = hasil.ringkas()
    if dry_run:
        db.rollback()
        laporan['dry_run'] = True
        laporan['catatan'] = 'pratinjau: tidak ada yang ditulis'
    else:
        db.commit()
        # Gizi menu adalah turunan bahan; tanpa ini halaman menu menampilkan
        # angka lama (atau kosong) walau mesin sudah memakai angka baru.
        from app.services.engine_data import hitung_gizi_semua_menu

        laporan['gizi_menu_dihitung'] = hitung_gizi_semua_menu(db)
    laporan['jumlah_menu'] = db.query(Recipe).count()
    laporan['jumlah_bahan'] = db.query(Ingredient).count()
    return laporan
