"""Bangun snapshot data mesin rekomendasi dari basis data.

Inilah satu-satunya tempat mesin rekomendasi membaca tabel. Semua angka yang
dirawat admin — gizi bahan, BDD, alergen, slot MBG, harga, musim, ketersediaan
lokal, acuan AKG, titik z-score, dan bobot SAW — masuk ke perhitungan lewat modul
ini. Admin mengubah data, rekomendasi berikutnya ikut berubah; tidak ada salinan
angka di tempat lain.

Snapshot berbentuk kamus biasa agar `app.services.nutrition_core` tetap dapat
diuji tanpa koneksi basis data.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Ingredient, LocalAvailability, NutritionFact, Region, SeasonalAvailability
from app.models.enums import LocalLevel, PriceStatus, SeasonalStatus
from app.models.planning import SystemConfig
from app.models.price import Price
from app.models.recipe import Recipe, RecipeIngredient
from app.models.standard import AnthropometryStandard, NutritionStandard
from app.services import nutrition_core as core

SKOR_LOKAL = {LocalLevel.ABUNDANT: 1.0, LocalLevel.AVAILABLE: 0.6, LocalLevel.LIMITED: 0.2}
SKOR_LOKAL_BAKU = 0.5
SKOR_MUSIM_BAKU = 0.5

# Satuan -> gram/ml. Bahan cair memakai liter, selain itu kilogram.
#
# Daftar ini dulu tidak memuat satuan pasar yang umum ("1 ikat kangkung",
# "2 buah jagung"). Karena nilai bawaan `_gram` adalah 1.000 g, satu ikat
# kangkung dihitung 1 kg dan satu menu melonjak jadi ribuan kkal per porsi.
# Sekarang satuan pasar didefinisikan, dan satuan tak dikenal dilaporkan lewat
# `satuan_tidak_dikenal` alih-alih diam-diam dianggap 1 kg.
KONVERSI = {
    'kg': 1000.0, 'liter': 1000.0, 'g': 1.0, 'gram': 1.0, 'ml': 1.0,
    'pcs': 100.0, 'butir': 55.0, 'sachet': 20.0, 'siung': 5.0,
    'ikat': 250.0, 'buah': 150.0, 'lembar': 5.0, 'ekor': 150.0,
    'potong': 80.0, 'biji': 10.0, 'ruas': 10.0, 'gelas': 200.0,
    'cangkir': 240.0, 'sdm': 15.0, 'sdt': 5.0, 'sendok': 15.0,
}

#: Nilai konservatif untuk satuan yang tidak dikenal: 100 g per bagian, bukan
#: 1 kg. Tetap dipakai supaya gizi tidak hilang, tapi dilaporkan ke admin.
GRAM_ASUMSI = 100.0

# Satuan tak dikenal yang ditemui pada perhitungan terakhir (untuk peringatan).
_satuan_asumsi: set[str] = set()


def _gram(jumlah, satuan):
    nama = str(satuan or 'kg').strip().lower()
    gram = KONVERSI.get(nama)
    if gram is None:
        _satuan_asumsi.add(nama)
        gram = GRAM_ASUMSI
    return float(jumlah or 0) * gram


def satuan_asumsi_terpakai() -> list[str]:
    """Satuan yang tidak ada di KONVERSI dan harus diperbaiki admin."""
    return sorted(_satuan_asumsi)


def reset_satuan_asumsi() -> None:
    _satuan_asumsi.clear()

KUNCI_BOBOT = {'N': 'weight_nutrition', 'A': 'weight_budget',
               'M': 'weight_seasonal', 'L': 'weight_local'}


def _gram(jumlah, satuan):
    return float(jumlah or 0) * KONVERSI.get(str(satuan or 'kg').lower(), 1000.0)


def _peta_harga(db: Session) -> dict[int, float]:
    """Harga approved terbaru per bahan, tanpa membedakan wilayah.

    Data harga yang tersedia dipakai untuk semua pengguna supaya besaran biaya
    tetap bermakna. Wilayah pengguna tidak mengubah harga satuan.
    """
    baris = db.scalars(
        select(Price)
        .where(Price.status.in_([PriceStatus.APPROVED]))
        .order_by(Price.recorded_date.desc(), Price.id.desc())
    ).all()
    harga: dict[int, float] = {}
    for p in baris:
        harga.setdefault(p.ingredient_id, float(p.price))
    return harga


def _peta_musim(db: Session) -> dict[int, float]:
    """Fraksi bulan panen (0-1). Bahan tanpa baris dianggap netral."""
    hitung = defaultdict(lambda: [0.0, 0])
    for s in db.scalars(select(SeasonalAvailability)).unique():
        row = hitung[s.ingredient_id]
        if s.status == SeasonalStatus.IN_SEASON:
            row[0] += 1.0
        elif s.status == SeasonalStatus.SHOULDER:
            row[0] += 0.5
        row[1] += 1
    return {iid: (v[0] / 12.0) for iid, v in hitung.items()}


def _peta_lokal(db: Session) -> dict[int, float]:
    """Skor ketersediaan lokal per bahan, sama untuk semua wilayah."""
    keluaran: dict[int, float] = {}
    for row in db.scalars(
        select(LocalAvailability).order_by(LocalAvailability.id)
    ).unique():
        keluaran.setdefault(row.ingredient_id, SKOR_LOKAL.get(row.level, SKOR_LOKAL_BAKU))
    return keluaran


def _akg(db: Session) -> dict:
    """{(kelompok, kelamin): nilai}, plus kunci tanpa kelamin sebagai cadangan."""
    keluaran: dict = {}
    for s in db.scalars(select(NutritionStandard).order_by(NutritionStandard.id)):
        nilai = {
            'kelompok_umur': s.age_group, 'jenis_kelamin': s.sex,
            'energi_kcal': s.energy_kcal, 'protein_g': s.protein_g,
            'lemak_total_g': s.fat_g, 'karbohidrat_g': s.carb_g,
            'serat_g': s.fiber_g, 'kalsium_mg': s.calcium_mg,
            'besi_mg': s.iron_mg, 'vitamin_a_mcg': s.vitamin_a_mcg,
            'vitamin_c_mg': s.vitamin_c_mg, 'natrium_mg': s.sodium_mg,
            'berat_badan_kg': s.weight_kg, 'tinggi_badan_cm': s.height_cm,
        }
        keluaran[(s.age_group, s.sex)] = nilai
        keluaran.setdefault(s.age_group, nilai)
    return keluaran


def _antro(db: Session) -> dict:
    tabel = defaultdict(list)
    query = select(AnthropometryStandard).order_by(
        AnthropometryStandard.index_name, AnthropometryStandard.sex,
        AnthropometryStandard.age_month)
    for r in db.scalars(query):
        # PB/U (berbaring, 0-23 bln) dan TB/U (berdiri, 25-60 bln) adalah satu
        # kurva pertumbuhan; digabung supaya balita punya acuan yang benar.
        indeks = 'TB/U' if r.index_name == 'PB/U' else r.index_name
        tabel[(indeks, r.sex)].append((
            float(r.age_month),
            [(-3, float(r.minus3sd)), (-2, float(r.minus2sd)), (-1, float(r.minus1sd)),
             (0, float(r.median)), (1, float(r.plus1sd)), (2, float(r.plus2sd)),
             (3, float(r.plus3sd))]))
    return {k: v for k, v in tabel.items() if len(v) >= 2}


def _bobot(db: Session) -> dict:
    nilai = {k: v for k, v in db.execute(
        select(SystemConfig.config_key, SystemConfig.config_value))}
    bobot = {k: float(nilai[f]) if nilai.get(f) is not None else core.BOBOT_SAW_BAKU[k]
             for k, f in KUNCI_BOBOT.items()}
    if abs(sum(bobot.values()) - 1.0) > 1e-6:
        total = sum(bobot.values()) or 1.0
        bobot = {k: v / total for k, v in bobot.items()}
    return bobot


def _porsi(nilai) -> int:
    """Resep dengan 1 porsi tidak perlu dibagi; selain itu bagi per porsi."""
    return max(int(nilai or 1), 1)


def bangun_snapshot(db: Session, region_nama: str | None = None) -> dict:
    """Kembalikan snapshot siap pakai untuk `nutrition_core`.

    Bahan tanpa harga tidak digagalkan — dicatat di `bahan_tanpa_harga` supaya
    API bisa memperingatkan bahwa biaya menunya terlalu rendah. Satuan bahan
    yang tidak ada di tabel konversi dihitung dengan asumsi 100 g dan dilaporkan
    di `satuan_tidak_dikenal`, bukan diam-diam dianggap 1 kg.
    """
    reset_satuan_asumsi()
    region_id = None
    if region_nama:
        region_id = db.scalar(select(Region.id).where(Region.name == region_nama))
        if region_id is None:
            region_id = db.scalar(select(Region.id).where(
                Region.name.ilike(f'%{region_nama}%')))

    gizi = {n.ingredient_id: n for n in db.scalars(select(NutritionFact))}
    bahan = {i.id: i for i in db.scalars(select(Ingredient))}
    harga = _peta_harga(db)
    musim = _peta_musim(db)
    lokal = _peta_lokal(db)

    komposisi = defaultdict(list)
    for ri in db.scalars(select(RecipeIngredient).order_by(RecipeIngredient.id)):
        komposisi[ri.recipe_id].append(ri)

    menu: dict = {}
    tanpa_harga: set[str] = set()
    for r in db.scalars(select(Recipe).order_by(Recipe.id)):
        porsi = _porsi(r.servings)
        akum = defaultdict(float)
        bagian = []
        gram_slot = 0.0
        w_lokal = w_musim = 0.0
        alergen, daftar_bahan, slot = set(), [], set()
        for ri in komposisi.get(r.id, []):
            ins = bahan.get(ri.ingredient_id) if ri.ingredient_id else None
            gram = _gram(ri.quantity, ri.unit)
            nama = ins.name if ins else ri.name
            daftar_bahan.append(nama)
            bagian.append({'nama_bahan': nama,
                          'ingredient_id': ri.ingredient_id,
                          'gram': gram / porsi})
            nz = gizi.get(ri.ingredient_id) if ri.ingredient_id else None
            if ins is not None and ri.ingredient_id not in harga:
                tanpa_harga.add(nama)
            if ins and ins.mbg_slot:
                slot_dasar = ins.mbg_slot.value
                gram_slot += gram
                slot.add(slot_dasar)
                w_lokal += gram * (lokal.get(ins.id, SKOR_LOKAL_BAKU)
                                   if ins.is_local or ins.id in lokal else SKOR_LOKAL_BAKU)
                w_musim += gram * musim.get(ins.id, SKOR_MUSIM_BAKU)
            if ins and ins.allergens:
                alergen |= {str(a).strip().lower() for a in ins.allergens if str(a).strip()}
            if nz is None:
                continue
            f = gram / 100.0
            akum['kalori'] += float(nz.calories or 0) * f
            akum['protein'] += float(nz.protein or 0) * f
            akum['lemak'] += float(nz.fat or 0) * f
            akum['karbohidrat'] += float(nz.carbs or 0) * f
            akum['serat'] += float(nz.fiber or 0) * f
            akum['gula_g'] += float(nz.sugar_g or 0) * f
            akum['natrium_mg'] += float(nz.sodium_mg or 0) * f
            akum['kalsium_mg'] += float(nz.calcium_mg or 0) * f
            akum['besi_mg'] += float(nz.iron_mg or 0) * f
            akum['vitamin_a_mcg'] += float(nz.vitamin_a_mcg or 0) * f
            akum['vitamin_c_mg'] += float(nz.vitamin_c_mg or 0) * f
            bdd = float(nz.bdd_percent or 100) / 100.0
            hp = harga.get(ri.ingredient_id)
            if hp:
                akum['biaya'] += (gram / (bdd or 1.0)) / 1000.0 * hp
        menu[str(r.id)] = {
            'menu_id': str(r.id), 'kode': r.code or str(r.id),
            'nama_menu': r.name, 'tipe': r.meal_kind or 'komponen',
            'slot': tuple(s for s in core.SLOT_URUTAN if s in slot),
            'kategori': r.category.value if r.category else '',
            'bahan': daftar_bahan, 'porsi_resep': porsi,
            'gram_bahan': gram_slot,
            'kalori': akum['kalori'] / porsi, 'protein': akum['protein'] / porsi,
            'lemak': akum['lemak'] / porsi, 'karbohidrat': akum['karbohidrat'] / porsi,
            'serat': akum['serat'] / porsi, 'gula_g': akum['gula_g'] / porsi,
            'natrium_mg': akum['natrium_mg'] / porsi,
            'kalsium_mg': akum['kalsium_mg'] / porsi, 'besi_mg': akum['besi_mg'] / porsi,
            'vitamin_a_mcg': akum['vitamin_a_mcg'] / porsi,
            'vitamin_c_mg': akum['vitamin_c_mg'] / porsi,
            'biaya': akum['biaya'] / porsi,
            'skor_lokal': (w_lokal / gram_slot) if gram_slot else SKOR_LOKAL_BAKU,
            'skor_musim': (w_musim / gram_slot) if gram_slot else SKOR_MUSIM_BAKU,
            'alergen': tuple(sorted(alergen)),
            'komposisi': bagian,
            'harga_lengkap': all(b not in tanpa_harga for b in daftar_bahan),
        }

    bahan_ringkas = {
        i.id: {'nama_bahan': i.name,
               'bdd_percent': float(gizi[i.id].bdd_percent or 100) if i.id in gizi else 100.0,
               'harga_per_kg': harga.get(i.id)}
        for i in bahan.values()
    }

    return {
        'menu': menu,
        'bahan': bahan_ringkas,
        'akg': _akg(db),
        'antro': _antro(db),
        'bobot': _bobot(db),
        'region_id': region_id,
        'bahan_tanpa_harga': sorted(tanpa_harga),
        'satuan_tidak_dikenal': satuan_asumsi_terpakai(),
        'jumlah_menu': len(menu),
    }


def hitung_gizi_semua_menu(db: Session) -> int:
    """Hitung ulang `recipe_nutrition` dari bahan penyusunnya.

    Gizi per menu sengaja TIDAK dapat diedit dari halaman admin: kalau dua tempat
    bisa diubah (gizi bahan dan gizi menu), angkanya akan saling bertentangan dan
    mesin tidak jelas mengikuti yang mana. Admin mengoreksi bahan di sini, menu
    ikut berubah.
    """
    gizi = {n.ingredient_id: n for n in db.scalars(select(NutritionFact))}
    komposisi = defaultdict(list)
    for ri in db.scalars(select(RecipeIngredient)):
        komposisi[ri.recipe_id].append(ri)
    harga = _peta_harga(db)
    diperbarui = 0
    for r in db.scalars(select(Recipe)):
        porsi = _porsi(r.servings)
        t = defaultdict(float)
        for ri in komposisi.get(r.id, []):
            nz = gizi.get(ri.ingredient_id)
            if nz is None:
                continue
            gram = _gram(ri.quantity, ri.unit)
            f = gram / 100.0
            t['calories'] += float(nz.calories or 0) * f
            t['protein'] += float(nz.protein or 0) * f
            t['carbohydrates'] += float(nz.carbs or 0) * f
            t['fat'] += float(nz.fat or 0) * f
            t['fiber'] += float(nz.fiber or 0) * f
            bdd = float(nz.bdd_percent or 100) / 100.0
            hp = harga.get(ri.ingredient_id)
            if hp:
                t['cost'] += (gram / (bdd or 1.0)) / 1000.0 * float(hp)
        nilai = r.nutrition
        if nilai is None:
            from app.models.recipe import RecipeNutrition

            nilai = RecipeNutrition(recipe_id=r.id)
            db.add(nilai)
        for k, v in (('calories', 'calories'), ('protein', 'protein'),
                     ('carbohydrates', 'carbohydrates'), ('fat', 'fat'),
                     ('fiber', 'fiber')):
            setattr(nilai, k, round(t[v] / porsi, 1))
        r.estimated_cost = round(t['cost'] / porsi)
        diperbarui += 1
    db.commit()
    return diperbarui
