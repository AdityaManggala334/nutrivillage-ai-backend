"""Inti mesin rekomendasi NutriVillage AI — logika murni, tanpa basis data.

Modul ini hanya bekerja dengan kamus biasa (lihat ``Snapshot`` di
``app/services/recommender.py``). Berpisah dari lapisan database supaya aturan
gizi dan skoring dapat diuji tanpa koneksi MySQL, dan supaya jalur
``admin edit -> database -> mesin`` hanya punya satu tempat penerjemahan.

Aturan yang dipakai:

* Target gizi: AKG Permenkes 28/2019; energi dewasa dari EER Mifflin-St Jeor.
* Status gizi: z-score Permenkes 2/2020 untuk anak, BMI untuk dewasa.
* Paket: slot wajib BGN (pokok, hewani, nabati, sayur, buah, susu).
* Biaya: gram bersih dibagi BDD, dikali harga per kg.
* LLM tidak berada di jalur ini.
"""
from __future__ import annotations

SLOT_URUTAN = ('pokok', 'hewani', 'nabati', 'sayur', 'buah', 'susu')

#: Nama waktu makan dalam satu hari (FR-05 revisi: semua waktu makan penuh,
#: bukan selingan setengah porsi). Indeks 0 = waktu makan pertama.
WAKTU_MAKAN_LABEL = (
    'Sarapan', 'Selingan Pagi', 'Makan Siang', 'Selingan Sore', 'Makan Malam',
)

#: Andil energi & anggaran tiap waktu makan, per jumlah waktu makan (jumlah = 1,0).
#: Makan siang selalu terbesar; selingan hanya 10-15% karena bukan makan utama.
MEAL_SHARES = {
    1: (1.0,),
    2: (0.45, 0.55),
    3: (0.25, 0.40, 0.35),
    4: (0.25, 0.35, 0.15, 0.25),
    5: (0.20, 0.10, 0.35, 0.10, 0.25),
}

#: Slot waktu makan bawaan bila pengguna tidak memilih sendiri.
DEFAULT_MEAL_SLOTS = {
    1: ('sarapan',),
    2: ('sarapan', 'makan_malam'),
    3: ('sarapan', 'makan_siang', 'makan_malam'),
    4: ('sarapan', 'makan_siang', 'selingan_sore', 'makan_malam'),
    5: ('sarapan', 'selingan_pagi', 'makan_siang', 'selingan_sore', 'makan_malam'),
}

#: Slot selingan: cukup satu menu ringan, bukan paket 6 komponen.
SELINGAN_SLOTS = frozenset(('selingan_pagi', 'selingan_sore'))

#: Andil pola 5 waktu makan (kompatibilitas pemanggil lama).
SHARE_WAKTU_MAKAN = MEAL_SHARES[5]

#: Berapa banyak waktu makan yang didukung mesin. SKPL V4 FR-05 revisi.
MAKS_WAKTU_MAKAN = 5


def meal_shares(n):
    """Andil per waktu makan untuk ``n`` kali makan; selalu berjumlah 1,0."""
    return MEAL_SHARES[min(max(int(n), 1), MAKS_WAKTU_MAKAN)]


def default_meal_slots(n):
    return DEFAULT_MEAL_SLOTS[min(max(int(n), 1), MAKS_WAKTU_MAKAN)]

# Andil tiap slot terhadap target satu porsi (energi, protein, biaya).
SLOT_SHARE = {
    'pokok':  {'kcal': 0.35, 'protein': 0.10, 'biaya': 0.18},
    'hewani': {'kcal': 0.15, 'protein': 0.45, 'biaya': 0.35},
    'nabati': {'kcal': 0.12, 'protein': 0.20, 'biaya': 0.12},
    'sayur':  {'kcal': 0.08, 'protein': 0.05, 'biaya': 0.08},
    'buah':   {'kcal': 0.10, 'protein': 0.02, 'biaya': 0.12},
    'susu':   {'kcal': 0.20, 'protein': 0.18, 'biaya': 0.15},
}

BOBOT_SAW_BAKU = {'N': 0.40, 'A': 0.30, 'M': 0.15, 'L': 0.15}
BOBOT_MIKRO = 0.30
BONUS_PREFERENSI = 0.20
PENALTI_VARIASI = 0.85
GIZI_MINIMUM = 0.40
MIKRO = ('kalsium_mg', 'besi_mg', 'vitamin_a_mcg', 'vitamin_c_mg')

BATAS_GULA_G = 15.0
BATAS_NATRIUM_MG = 600.0

ENERGI_ACUAN = 2650.0
PAL = {'rendah': 1.2, 'sedang': 1.55, 'tinggi': 1.725}
USIA_DEWASA = 19
LAKI = 'laki-laki'

# Skor rasio datar pada 85-130% target: melebihi target bukan bonus.
RASIO_BAWAH, RASIO_ATAS, RASIO_LANDAI = 0.85, 1.30, 0.45

# Batas atas kandidat per slot: menu yang kalorinya di atas 150% target slotnya
# tidak masuk kolam kandidat. Tanpa ini, satu komponen berkalori raksasa
# membuat satu waktu makan jadi 4x kebutuhan (temuan audit A2).
RASIO_KANDIDAT_MAKS = 1.50

# Upgrade mutu berhenti begitu kalori paket mencapai 110% target slotnya.
# Tanpa ini, sisa anggaran dipakai terus menaikkan energi sampai 150% (temuan
# pengukuran A2: semua slot mendarat tepat di plafon).
RASIO_UPGRADE_MAKS = 1.10

# FR-03: budget sebagai batas atas. Paket yang termurah melebihi anggaran
# sedikit (di bawah toleransi ini) masih dianggap layak dengan penanda
# over_budget; lebih dari itu, mesin menurunkan kandidat termurah dulu.
TOLERANSI_ANGGARAN = 1.15

ALIAS_ALERGEN = {'santan': 'kelapa', 'dairy': 'susu', 'laktosa': 'susu'}

KELOMPOK_UMUR = (
    (1, 3, '1-3 tahun'), (4, 6, '4-6 tahun'), (7, 9, '7-9 tahun'),
    (10, 12, '10-12 tahun'), (13, 15, '13-15 tahun'), (16, 18, '16-18 tahun'),
    (19, 29, '19-29 tahun'), (30, 49, '30-49 tahun'), (50, 64, '50-64 tahun'),
    (65, 80, '65-80 tahun'), (81, 200, '80+ tahun'),
)


def angka(nilai, baku=0.0):
    """Konversi aman: kolom numerik basis data boleh bernilai None."""
    if nilai is None:
        return baku
    try:
        return float(nilai)
    except (TypeError, ValueError):
        return baku


def normal_alergen(alergi):
    return sorted({ALIAS_ALERGEN.get(str(a).lower(), str(a).lower())
                   for a in (alergi or ()) if str(a).strip()})


# --------------------------------------------------------------- target gizi
def kelompok_umur(age):
    for lo, hi, label in KELOMPOK_UMUR:
        if lo <= age <= hi:
            return label
    return '19-29 tahun'


def baris_akg(snapshot, age, gender):
    kel = kelompok_umur(age)
    jk = 'Semua' if age < 10 else ('Laki-laki' if gender == LAKI else 'Perempuan')
    akg = snapshot['akg']
    return akg.get((kel, jk)) or akg.get((kel, 'Semua')) or akg.get(kel) or {}


def bmi(weight_kg, height_cm):
    if not height_cm:
        return 0.0
    return weight_kg / (height_cm / 100.0) ** 2


def kategori_bmi(nilai, age):
    if age < USIA_DEWASA:
        return 'perlu z-score antropometri'
    if nilai < 18.5:
        return 'kurus'
    if nilai < 23:
        return 'normal'
    if nilai < 25:
        return 'overweight'
    if nilai < 30:
        return 'obes I'
    return 'obes II'


def eer(anggota):
    """Energi aktual: memakai berat & tinggi badan nyata, bukan acuan AKG."""
    bmr = (10 * anggota.weight_kg + 6.25 * anggota.height_cm - 5 * anggota.age
           + (5 if anggota.gender == LAKI else -161))
    return bmr * PAL.get(anggota.activity_level, 1.55)


def target_anggota(snapshot, a):
    ak = baris_akg(snapshot, a.age, a.gender)
    energi_akg = angka(ak.get('energi_kcal'))
    protein = angka(ak.get('protein_g'))
    if a.age >= USIA_DEWASA:
        energi, dasar = round(eer(a)), 'EER (Mifflin-St Jeor)'
    else:
        energi, dasar = energi_akg, 'AKG'
    nilai_bmi = bmi(a.weight_kg, a.height_cm)
    return {
        'nama': a.name, 'umur': a.age, 'gender': a.gender,
        'kelompok_akg': ak.get('kelompok_umur') or kelompok_umur(a.age),
        'bb': a.weight_kg, 'tb': a.height_cm, 'aktivitas': a.activity_level,
        'bmi': round(nilai_bmi, 1), 'status_gizi': kategori_bmi(nilai_bmi, a.age),
        'energi_akg': energi_akg, 'energi': energi, 'protein': protein,
        'dasar': dasar, 'faktor_porsi': round(energi / ENERGI_ACUAN, 3),
        'alergi': normal_alergen(a.allergies),
    }


def target_keluarga(snapshot, profil):
    rows = [target_anggota(snapshot, a) for a in profil.members]
    energi = sum(r['energi'] for r in rows)
    protein = sum(r['protein'] for r in rows)
    faktor = sum(r['faktor_porsi'] for r in rows)
    # FR-05 revisi: target energi, protein, mikro, dan anggaran dibagi ke tiap
    # waktu makan memakai MEAL_SHARES (bukan rata), lalu diskalakan faktor porsi.
    n_utama = min(max(profil.meals_per_day, 1), MAKS_WAKTU_MAKAN)
    n_selingan = 0
    porsi_utama = faktor * n_utama
    total_porsi = porsi_utama
    mikro = {}
    for kunci, kolom in (('kalsium_mg', 'kalsium_mg'), ('besi_mg', 'besi_mg'),
                        ('vitamin_a_mcg', 'vitamin_a_mcg'),
                        ('vitamin_c_mg', 'vitamin_c_mg')):
        mikro[kunci] = sum(angka((baris_akg(snapshot, a.age, a.gender) or {}).get(kolom))
                           for a in profil.members)
    bagi = porsi_utama or 1.0
    return {
        'anggota': rows, 'energi': energi, 'protein': protein, 'faktor': faktor,
        'n_utama': n_utama, 'n_selingan': n_selingan, 'mikro': mikro,
        'andil': meal_shares(n_utama),
        'porsi_utama': round(bagi, 2),
        'anggaran_per_porsi': round(profil.daily_budget / total_porsi) if total_porsi else 0,
        'energi_per_porsi': energi / bagi if bagi else 0,
        'protein_per_porsi': protein / bagi if bagi else 0,
        'mikro_per_porsi': {k: round(v / bagi, 1) for k, v in mikro.items()},
    }


# ------------------------------------------------- z-score (Permenkes 2/2020)
STATUS_BB = ((-3, 'gizi buruk'), (-2, 'gizi kurang'), (1, 'gizi baik'),
             (99, 'risiko gizi lebih'))
STATUS_TB = ((-3, 'severely stunted'), (-2, 'stunted'), (2, 'normal'),
             (99, 'tinggi'))


def _nilai_z(titik, nilai):
    for (z1, v1), (z2, v2) in zip(titik, titik[1:]):
        if v1 <= nilai <= v2 and v2 > v1:
            return round(z1 + (nilai - v1) / (v2 - v1) * (z2 - z1), 2)
    if nilai < titik[0][1]:
        return -3.0
    if nilai > titik[-1][1]:
        return 3.0
    return None


def z_score(snapshot, indeks, gender, umur_bulan, nilai):
    """Interpolasi linear antar titik SD tabel Permenkes 2/2020."""
    baris = snapshot.get('antro', {}).get((indeks, gender))
    if not baris or not nilai:
        return None
    _, titik = min(baris, key=lambda b: abs(b[0] - umur_bulan))
    return _nilai_z(titik, nilai)


def _label(z, tabel):
    if z is None:
        return 'tidak dapat dinilai'
    for batas, nama in tabel:
        if z < batas:
            return nama
    return tabel[-1][1]


def antropometri(snapshot, a):
    """z-score untuk anak (<19 th), BMI untuk dewasa."""
    if a.age >= USIA_DEWASA:
        nilai = bmi(a.weight_kg, a.height_cm)
        return {'metode': 'BMI (dewasa)', 'bmi': round(nilai, 1),
                'status': kategori_bmi(nilai, a.age)}
    gender = 'L' if a.gender == LAKI else 'P'
    bulan = a.age * 12
    z_bb = z_score(snapshot, 'BB/U', gender, bulan, a.weight_kg)
    z_tb = z_score(snapshot, 'TB/U', gender, bulan, a.height_cm)
    z_imt = z_score(snapshot, 'IMT/U', gender, bulan, bmi(a.weight_kg, a.height_cm))
    return {'metode': 'z-score (Permenkes 2/2020)',
            'bmi': round(bmi(a.weight_kg, a.height_cm), 1),
            'z_bb_u': z_bb, 'z_tb_u': z_tb, 'z_imt_u': z_imt,
            'status': _label(z_tb, STATUS_TB), 'status_bb': _label(z_bb, STATUS_BB),
            'status_imt': _label(z_imt, ((-3, 'sangat kurus'), (-2, 'kurus'),
                                         (1, 'normal'), (2, 'gemuk'),
                                         (99, 'obes')))}


# ------------------------------------------------------------------- skoring
def rasio_skor(r):
    if RASIO_BAWAH <= r <= RASIO_ATAS:
        return 1.0
    if r < RASIO_BAWAH:
        return max(0.0, 1.0 - (RASIO_BAWAH - r) / RASIO_LANDAI)
    return max(0.0, 1.0 - (r - RASIO_ATAS) / RASIO_LANDAI)


def skor_mikro(menu, target_mikro):
    """Rata-rata pemenuhan mikro HANYA untuk nutrisi yang datanya tersedia."""
    ada = []
    for k in MIKRO:
        t = angka(target_mikro.get(k))
        v = angka(menu.get(k))
        if t > 0 and v > 0:
            ada.append(min(v / t, 1.0))
    return sum(ada) / len(ada) if ada else None


def cocok_preferensi(menu, preferences):
    if not preferences:
        return 0.0
    teks = ' '.join(menu['bahan']).lower()
    kena = sum(1 for p in preferences if p and str(p).lower() in teks)
    return kena / len(preferences)


def saring(menu_list, alergi=(), dihindari=(), cek_ggl=True):
    alergi = set(normal_alergen(alergi))
    out = []
    for m in menu_list:
        if alergi and set(m['alergen']) & alergi:
            continue
        bahan = ' '.join(m['bahan']).lower()
        if any(str(v).lower() in bahan for v in (dihindari or ()) if v):
            continue
        if cek_ggl and (m['gula_g'] > BATAS_GULA_G or m['natrium_mg'] > BATAS_NATRIUM_MG):
            continue
        out.append(m)
    return out


def skor_slot(calon, tk, tp, mikro, plafon, bobot, preferences=(), sudah_dipakai=()):
    """Skor SAW kandidat satu slot, terurut terbaik dahulu."""
    if not calon or plafon <= 0:
        return []
    penalti = set(sudah_dipakai)
    keluaran = []
    for m in calon:
        r_k = m['kalori'] / tk if tk > 0 else 0.0
        r_p = m['protein'] / tp if tp > 0 else 0.0
        n_makro = 0.5 * rasio_skor(r_p) + 0.5 * rasio_skor(r_k)
        n_mikro = skor_mikro(m, mikro)
        n = ((1 - BOBOT_MIKRO) * n_makro + BOBOT_MIKRO * n_mikro
             if n_mikro is not None else n_makro)
        efisiensi = max(0.0, min(1.0, 1.0 - m['biaya'] / plafon))
        saw = (bobot['N'] * n + bobot['A'] * efisiensi
               + bobot['M'] * min(max(m['skor_musim'], 0.0), 1.0)
               + bobot['L'] * min(max(m['skor_lokal'], 0.0), 1.0))
        saw *= (1 + BONUS_PREFERENSI * cocok_preferensi(m, preferences))
        if m['menu_id'] in penalti:
            saw *= PENALTI_VARIASI
        keluaran.append({**m, 'N': n, 'A': efisiensi, 'M': m['skor_musim'],
                         'L': m['skor_lokal'], 'SAW': saw,
                         'rasio_kcal': r_k, 'rasio_prot': r_p})
    keluaran.sort(key=lambda x: -x['SAW'])
    return keluaran


def kolam_slot(layak, slots, tk, tp, mikro, anggaran, bobot, preferences, sudah_dipakai):
    """Kandidat terskor per slot dengan target proporsional.

    Saat sebagian slot ditinggalkan (misal karena alergi), proporsi energi &
    protein dinormalisasi ulang ke slot yang tersisa supaya paket tetap gizi
    cukup, bukan kehilangan jatah begitu saja.
    """
    tot_k = sum(SLOT_SHARE[s]['kcal'] for s in slots) or 1.0
    tot_p = sum(SLOT_SHARE[s]['protein'] for s in slots) or 1.0
    kolam = {}
    for s in slots:
        murni = [m for m in layak if m['slot'] == (s,)]
        raw = [m for m in layak if s in m['slot']]
        tk_s = tk * SLOT_SHARE[s]['kcal'] / tot_k
        tp_s = tp * SLOT_SHARE[s]['protein'] / tot_p
        bahan = (murni or raw)
        # Dua arah: kandidat harus minimal 40% target slot (gizi cukup) DAN
        # tidak melebihi 150% target slot (tidak menumpuk energi). Kandidat
        # yang kelebihan tetap masuk bila kolam jadi kosong (lihat fallback
        # di bawah), supaya alergi berat tidak menggagalkan rekomendasi.
        lolos = [m for m in bahan
                 if m['kalori'] >= GIZI_MINIMUM * tk_s or m['protein'] >= GIZI_MINIMUM * tp_s]
        proporsional = [m for m in lolos
                        if m['kalori'] <= RASIO_KANDIDAT_MAKS * tk_s]
        dipakai_kolam = proporsional or lolos or bahan
        kolam[s] = (skor_slot(dipakai_kolam, tk_s, tp_s, mikro,
                              anggaran * SLOT_SHARE[s]['biaya'], bobot,
                              preferences, sudah_dipakai), tk_s, tp_s,
                    dipakai_kolam)
    return kolam

# -------------------------------------------------------------- perakitan
def rakit_paket(layak, slots, anggaran, tk, tp, mikro, bobot, mode='komponen',
                preferences=(), sudah_dipakai=()):
    """Rakit satu paket makan. Return ``(paket, status, catatan)``.

    Slot tanpa kandidat DILEWAT dengan catatan, bukan menggagalkan seluruh
    paket — hasil ini yang membuat alergi berat tetap dapat rekomendasi.
    """
    slots = [s for s in SLOT_URUTAN if s in slots]
    awal = kolam_slot(layak, slots, tk, tp, mikro, anggaran, bobot, preferences,
                      sudah_dipakai)
    tersedia = [s for s in slots if awal[s][0]]
    ditinggalkan = [s for s in slots if not awal[s][0]]
    if not tersedia:
        return [], 'infeasible', {
            'alasan': 'tidak ada kandidat untuk semua slot wajib',
            'slot_ditinggalkan': ditinggalkan,
            'saran': 'tambah data gizi/alergen bahan atau longgarkan pantangan'}

    kolam = kolam_slot(layak, tersedia, tk, tp, mikro, anggaran, bobot, preferences,
                       sudah_dipakai)
    termurah = {s: min((m['biaya'] for m in kolam[s][0]), default=0.0) for s in tersedia}
    minimum = round(sum(termurah.values()))
    if minimum > anggaran:
        return [], 'infeasible', {
            'alasan': 'anggaran tidak cukup untuk slot wajib',
            'minimum_dibutuhkan': minimum, 'budget': round(anggaran),
            'slot_ditinggalkan': ditinggalkan,
            'saran': f'naikkan anggaran per porsi ke Rp{minimum:,} atau '
                     f'kurangi frekuensi makan'.replace(',', '.'),
        }

    # FR-03: budget sebagai batas atas. Saat paket termurah yang proporsional
    # tidak muat (over-budget), sisa pekerjaan dipindah ke tahap pemilihan:
    # kandidat terurut makin murah diutamakan, dan upgrade mutu DImatikan,
    # sehingga mesin menurunkan biaya alih-alih memakai menu mahal lalu
    # memberi badge "melebihi anggaran".
    over_budget = minimum > anggaran * TOLERANSI_ANGGARAN

    paket, terisi = [], set()
    sisa = float(anggaran)

    def pasang(slot, m, tutup):
        nonlocal sisa
        paket.append({'slot': slot, 'menu_id': m['menu_id'], 'nama_menu': m['nama_menu'],
                      'menutup': sorted(tutup), 'biaya': round(m['biaya']),
                      'kalori': round(m['kalori']), 'protein': round(m['protein'], 1),
                      'kalsium_mg': round(m['kalsium_mg']), 'besi_mg': round(m['besi_mg'], 1),
                      'vitamin_a_mcg': round(m['vitamin_a_mcg']),
                      'vitamin_c_mg': round(m['vitamin_c_mg']),
                      'gula_g': round(m['gula_g'], 1), 'natrium_mg': round(m['natrium_mg']),
                      'skor': {k: round(m[k], 3) for k in ('N', 'A', 'M', 'L', 'SAW')},
                      'alergen': list(m['alergen'])})
        sisa -= m['biaya']
        terisi.update(tutup)

    if mode == 'hidangan':
        hidangan = [m for m in skor_slot([x for x in layak if x['tipe'] == 'hidangan'],
                                        tk, tp, mikro, anggaran, bobot, preferences,
                                        sudah_dipakai)
                    if m['biaya'] <= sisa]
        for m in hidangan:
            tutup = set(m['slot']) & set(tersedia)
            if not tutup:
                continue
            butuh = [s for s in tersedia if s not in tutup]
            if m['biaya'] <= sisa - sum(termurah[s] for s in butuh):
                pasang('hidangan', m, tutup)
                break

    for s in tersedia:
        if s in terisi:
            continue
        butuh = [x for x in tersedia if x not in terisi and x != s]
        plafon = sisa - sum(termurah[x] for x in butuh)
        calon = [m for m in kolam[s][0] if m['biaya'] <= plafon]
        if not calon:
            calon = [min(kolam[s][0], key=lambda m: m['biaya'])]
        if over_budget:
            # Opsi B: urutkan kandidat termurah dahulu. Skor SAW tetap jadi
            # dasar pemilihan bila biayanya setara (selisih < 5%), supaya mutu
            # tidak diorban lebih dari perlu.
            urut = sorted(calon, key=lambda m: m['biaya'])
            termurah_biaya = urut[0]['biaya']
            calon = [m for m in urut if m['biaya'] <= termurah_biaya * 1.05] or urut[:1]
        pasang(s, calon[0], {s} - terisi)

    if over_budget:
        return paket, 'ok', {'slot_ditinggalkan': ditinggalkan,
                             'minimum_dibutuhkan': minimum,
                             'over_budget': True}
    upgrade_paket(paket, kolam, lambda: sisa, tk, tp, sudah_dipakai)
    return paket, 'ok', {'slot_ditinggalkan': ditinggalkan, 'minimum_dibutuhkan': minimum}


def _kualitas(m, tk, tp):
    """Nilai paket: pemenuhan target + porsi nyata.

    Skor N saja tidak cukup untuk memilih saat anggaran berlebih: begitu target
    tercapai, semua kandidat bernilai 1,0 dan anggaran besar berhenti berpengaruh.
    """
    return (m['N'] + 0.10 * min(m['kalori'] / tk if tk else 0, 1.5)
            + 0.05 * min(m['protein'] / tp if tp else 0, 1.5))


def upgrade_paket(paket, kolam, baca_sisa, tk=0.0, tp=0.0, sudah_dipakai=()):
    """Pakai sisa anggaran untuk menaikkan mutu paket.

    Tanpa tahap ini, anggaran besar menghasilkan paket yang sama dengan anggaran
    kecil — persis cacat yang ditemukan saat audit mesin versi awal.

    Menu yang sudah dipakai waktu makan lain ikut ditekan di sini; tanpa itu
    tahap upgrade mengembalikan pilihan yang baru saja dihindari penalti variasi.
    """
    penalti = set(sudah_dipakai)
    # Target kalori per slot disimpan di kolam; upgrade berhenti menaikkan
    # energi begitu paket mencapai RASIO_UPGRADE_MAKS dari target slotnya.
    target_slot = {s: kal for s, (_, kal, _, _) in kolam.items()}

    def mutu(m, n, kalori, protein):
        nilai = _kualitas({'N': n, 'kalori': kalori, 'protein': protein}, tk, tp)
        return nilai * PENALTI_VARIASI if m in penalti else nilai

    for _ in range(40):
        terbaik = None
        for i, p in enumerate(paket):
            if p['slot'] == 'hidangan':
                continue
            kini = mutu(p['menu_id'], p['skor']['N'], p['kalori'], p['protein'])
            for m in kolam[p['slot']][0]:
                if m['biaya'] - p['biaya'] > baca_sisa() + 1e-6:
                    continue
                # Menu yang kalorinya melewati plafon upgrade slot ini tidak
                # dianggap perbaikan, walau skornya lebih tinggi.
                plafon_kalori = RASIO_UPGRADE_MAKS * (target_slot.get(p['slot']) or 0)
                if m['kalori'] > plafon_kalori:
                    continue
                untung = mutu(m['menu_id'], m['N'], m['kalori'], m['protein']) - kini
                if untung <= 1e-6:
                    continue
                if terbaik is None or untung > terbaik[0]:
                    terbaik = (untung, i, m)
        if terbaik is None:
            return
        _, i, m = terbaik
        lama = paket[i]
        paket[i] = {**lama, 'menu_id': m['menu_id'], 'nama_menu': m['nama_menu'],
                    'biaya': round(m['biaya']), 'kalori': round(m['kalori']),
                    'protein': round(m['protein'], 1),
                    'kalsium_mg': round(m['kalsium_mg']),
                    'besi_mg': round(m['besi_mg'], 1),
                    'vitamin_a_mcg': round(m['vitamin_a_mcg']),
                    'vitamin_c_mg': round(m['vitamin_c_mg']),
                    'gula_g': round(m['gula_g'], 1), 'natrium_mg': round(m['natrium_mg']),
                    'skor': {k: round(m[k], 3) for k in ('N', 'A', 'M', 'L', 'SAW')},
                    'alergen': list(m['alergen'])}


def ringkas_paket(paket, anggaran, tk, tp):
    total_biaya = sum(p['biaya'] for p in paket)
    total_kcal = sum(p['kalori'] for p in paket)
    total_prot = sum(p['protein'] for p in paket)
    gula = sum(p['gula_g'] for p in paket)
    natrium = sum(p['natrium_mg'] for p in paket)
    return {
        'jumlah_komponen': len(paket),
        'total_biaya': round(total_biaya),
        'sisa_anggaran': round(anggaran - total_biaya),
        'pemakaian_anggaran': round(total_biaya / anggaran * 100, 1) if anggaran else 0,
        'total_kcal': round(total_kcal), 'total_protein': round(total_prot, 1),
        'pct_kcal': round(total_kcal / tk * 100, 1) if tk else 0,
        'pct_protein': round(total_prot / tp * 100, 1) if tp else 0,
        'gula_g': round(gula, 1), 'natrium_mg': round(natrium),
        'gula_pct_energi': round(gula * 4 / total_kcal * 100, 1) if total_kcal else 0,
        'patuh_anggaran': bool(total_biaya <= anggaran + 1),
        'patuh_ggl': bool(gula <= BATAS_GULA_G * 1.35 and natrium <= BATAS_NATRIUM_MG),
    }
