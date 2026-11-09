"""Layanan rekomendasi: mengubah permintaan pengguna menjadi paket makan.

Alur satu arah:

    permintaan -> snapshot basis data (engine_data) -> aturan gizi & skoring
    (nutrition_core) -> respons

Fungsi di sini tidak menulis basis data; penyimpanan riwayat dilakukan router.
Dengan begitu hasil selalu dapat direproduksi dari data yang sama.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.schemas.recommendation import (
    DaftarBelanja, DaftarBelanjaBaris, ProfilKeluargaIn, ProfilSekolahIn,
)
from app.services import engine_data, nutrition_core as core

WAKTU_MAKAN = ('Sarapan', 'Makan Siang', 'Makan Malam', 'Selingan 1', 'Selingan 2')

#: Kelompok penerima manfaat SPPG -> kelompok umur acuan AKG & anggaran BGN.
SPPG_LEVEL = {
    'sd_1_3': {'age_group': '7-9 tahun', 'label': 'SD kelas 1-3'},
    'sd_4_6': {'age_group': '10-12 tahun', 'label': 'SD kelas 4-6'},
    'smp': {'age_group': '13-15 tahun', 'label': 'SMP'},
    'sma': {'age_group': '16-18 tahun', 'label': 'SMA'},
    'lainnya': {'age_group': '19-29 tahun', 'label': 'Kelompok lainnya'},
}

#: Anggaran bahan makanan per porsi menurut Peraturan BGN 13/2026.
ANGGARAN_BGN = {'sd_1_3': 8000.0, 'sd_4_6': 10000.0, 'smp': 10000.0, 'sma': 10000.0}

#: Makan siang MBG menanggung sebagian dari kebutuhan harian.
PORSI_HARIAN = 3.0


def _slot_wajib(alergi, include_susu=True):
    slots = list(core.SLOT_URUTAN)
    if not include_susu or 'susu' in alergi:
        slots.remove('susu')
    return slots


def _target_per_porsi(snapshot, profil, info):
    """Target energi/protein/mikro untuk 1 porsi dewasa pada 1 waktu makan."""
    bagi = info['porsi_utama'] or 1.0
    mikro = {k: v / bagi for k, v in info['mikro_per_porsi'].items()}
    return (info['energi'] / bagi, info['protein'] / bagi, mikro)


def _item(m) -> dict:
    return {
        'slot': m['slot'], 'recipe_id': int(m['menu_id']), 'kode': m.get('kode', ''),
        'nama_menu': m['nama_menu'], 'menutup': list(m['menutup']),
        'biaya': m['biaya'], 'kalori': m['kalori'], 'protein': m['protein'],
        'kalsium_mg': m['kalsium_mg'], 'besi_mg': m['besi_mg'],
        'vitamin_a_mcg': m['vitamin_a_mcg'], 'vitamin_c_mg': m['vitamin_c_mg'],
        'gula_g': m['gula_g'], 'natrium_mg': m['natrium_mg'],
        'alergen': list(m['alergen']),
        'score_nutrition': m['skor']['N'], 'score_budget': m['skor']['A'],
        'score_seasonal': m['skor']['M'], 'score_local': m['skor']['L'],
        'score_total': m['skor']['SAW'],
    }


def rekomendasi_keluarga(db: Session, profil: ProfilKeluargaIn, mode: str = 'hidangan') -> dict:
    """Rencana makan keluarga: paket per waktu makan + peringatan gizinya."""
    snapshot = engine_data.bangun_snapshot(db, profil.region)
    alergi = core.normal_alergen(profil.alergi)
    info = core.target_keluarga(snapshot, profil)
    tk, tp, mikro = _target_per_porsi(snapshot, profil, info)
    slots = _slot_wajib(alergi, profil.include_susu)
    anggaran = info['anggaran_per_porsi']

    keluaran = {
        'status': 'ok', 'slot_wajib': slots, 'anggaran_per_porsi': anggaran,
        'waktu_makan': [], 'selingan': [], 'peringatan': [], 'penyesuaian': [],
        'anggaran_harian': profil.daily_budget,
        'target': {'energi_harian': info['energi'], 'protein_harian': info['protein'],
                   'porsi_dewasa_per_makan': info['porsi_utama'],
                   'energi_per_porsi': round(tk, 1), 'protein_per_porsi': round(tp, 2),
                   'mikro_per_porsi': {k: round(v, 1) for k, v in mikro.items()},
                   'anggota': [_gabung_antropometri(snapshot, r, a)
                               for r, a in zip(info['anggota'], profil.members)]},
    }
    if snapshot['jumlah_menu'] == 0:
        keluaran |= {'status': 'infeasible',
                     'alasan': 'belum ada data menu/bahan di basis data',
                     'saran': 'jalankan scripts/import_nutrivillage_dataset.py'}
        return keluaran

    layak = core.saring(list(snapshot['menu'].values()), alergi,
                       profil.avoided_ingredients)
    dipakai, ditinggalkan = set(), set()
    for i in range(info['n_utama']):
        paket, status, catatan = core.rakit_paket(
            layak, slots, anggaran, tk, tp, mikro, snapshot['bobot'], mode=mode,
            preferences=profil.preferences, sudah_dipakai=dipakai)
        if status != 'ok':
            keluaran |= {'status': 'infeasible', 'alasan': catatan['alasan'],
                         'saran': catatan.get('saran'), 'waktu_makan': keluaran['waktu_makan'],
                         'minimum_dibutuhkan': catatan.get('minimum_dibutuhkan')}
            return _peringatan_harga(keluaran, snapshot)
        ditinggalkan |= set(catatan.get('slot_ditinggalkan') or [])
        dipakai |= {p['menu_id'] for p in paket}
        keluaran['waktu_makan'].append({
            'waktu': WAKTU_MAKAN[i], 'anggaran_per_porsi': anggaran,
            'paket': [_item(p) for p in paket],
            'ringkas': core.ringkas_paket(paket, anggaran, tk, tp),
        })

    for j in range(info['n_selingan']):
        batasan = anggaran * 0.35
        selingan = _selingan(layak, keluaran, batasan, tk, tp, snapshot['bobot'])
        if selingan:
            keluaran['selingan'].append(selingan)
            dipakai.add(str(selingan['recipe_id']))

    if ditinggalkan:
        nama = ', '.join(sorted(ditinggalkan))
        keluaran['penyesuaian'].append(
            f'Slot {nama} tidak memiliki kandidat yang lolos alergi/pantangan; '
            f'porsinya dibagi ulang ke slot lain.')
    keluaran['total_biaya_harian'] = round(
        sum(w['ringkas']['total_biaya'] for w in keluaran['waktu_makan']) * info['faktor']
        + sum(s['biaya'] for s in keluaran['selingan']) * info['faktor'])
    keluaran['patuh_anggaran'] = keluaran['total_biaya_harian'] <= profil.daily_budget + 1
    semua = [p['recipe_id'] for w in keluaran['waktu_makan'] for p in w['paket']]
    keluaran['variasi'] = round(len(set(semua)) / len(semua), 3) if semua else 1.0
    keluaran['peringatan'] = _peringatan(keluaran, info, alergi)
    return _peringatan_harga(keluaran, snapshot)


def _selingan(layak, keluaran, batasan, tk, tp, bobot):
    """Selingan = buah atau susu satuan terkecil, di luar yang sudah dipakai."""
    sudah = {str(p['recipe_id']) for w in keluaran['waktu_makan'] for p in w['paket']}
    sudah |= {str(s['recipe_id']) for s in keluaran['selingan']}
    calon = [m for m in layak if m['slot'] in (('buah',), ('susu',))
             and m['menu_id'] not in sudah and m['biaya'] <= batasan]
    if not calon:
        return None
    calon.sort(key=lambda m: -(m['kalori'] / max(tk * 0.10, 1)
                              + m['protein'] / max(tp * 0.02, 1)))
    m = calon[0]
    return {'waktu': WAKTU_MAKAN[3 + len(keluaran['selingan'])],
            'recipe_id': int(m['menu_id']), 'nama_menu': m['nama_menu'],
            'slot': m['slot'][0], 'biaya': round(m['biaya']),
            'kalori': round(m['kalori']), 'protein': round(m['protein'], 1)}


def _gabung_antropometri(snapshot, baris, anggota):
    """Tambahkan z-score anak (BMI untuk dewasa) pada target per anggota."""
    nilai = core.antropometri(snapshot, anggota)
    if nilai['metode'].startswith('z-score'):
        baris |= {'z_bb_u': nilai['z_bb_u'], 'z_tb_u': nilai['z_tb_u'],
                  'z_imt_u': nilai['z_imt_u']}
        baris['status_gizi'] = f"{nilai['status']} (TB/U) · {nilai['status_bb']} (BB/U)"
    else:
        baris['status_gizi'] = nilai['status']
    return baris


def _peringatan(keluaran, info, alergi):
    """Umpan balik mutu paket — kekurangan gizi harus terlihat, tidak tersembunyi."""
    pesan = []
    ringkas = [w['ringkas'] for w in keluaran['waktu_makan']]
    if not ringkas:
        return pesan
    energi = sum(r['pct_kcal'] for r in ringkas) / len(ringkas)
    protein = sum(r['pct_protein'] for r in ringkas) / len(ringkas)
    if energi < 80:
        pesan.append(
            f'Target energi hanya tercapai {energi:.0f}% per waktu makan. Anggaran '
            f'{keluarga_rp(keluaran["anggaran_per_porsi"])}/porsi terlalu ketat untuk '
            f'{len(info["anggota"])} anggota.')
    if protein < 80:
        pesan.append(f'Target protein hanya tercapai {protein:.0f}%.')
    elif protein > 160:
        pesan.append(
            f'Protein {protein:.0f}% dari target (kelebihan). Tidak berbahaya, tetapi '
            f'porsi lauk bisa diturunkan untuk menghemat anggaran.')
    gula = sum(r['gula_pct_energi'] for r in ringkas) / len(ringkas)
    if gula > 10:
        pesan.append(f'Gula {gula:.1f}% dari energi, melewati batas 10% (pedoman GGL).')
    if keluaran['variasi'] < 0.7:
        pesan.append(
            f"Variasi menu rendah: {len({p['recipe_id'] for w in keluaran['waktu_makan'] for p in w['paket']})} "
            "menu unik untuk seluruh waktu makan. Bahan yang lolos alergi terbatas.")
    if 'susu' in alergi:
        pesan.append('Slot susu dihapus karena alergi; kalsium diambil dari tahu/tempe/'
                     'teri/sayur hijau.')
    return pesan


def keluarga_rp(nilai) -> str:
    return f'Rp{int(round(nilai)):,}'.replace(',', '.')


def _peringatan_harga(keluaran, snapshot):
    tanpa = snapshot.get('bahan_tanpa_harga') or []
    if tanpa:
        keluaran['peringatan'] = (keluaran.get('peringatan') or []) + [
            f'{len(tanpa)} bahan belum punya harga terverifikasi ('
            + ', '.join(tanpa[:5]) + (', ...' if len(tanpa) > 5 else '')
            + f'). Biaya paket kemungkinan terlalu rendah — lengkapi di halaman '
              f'admin Harga.']
    satuan = snapshot.get('satuan_tidak_dikenal') or []
    if satuan:
        keluaran['peringatan'] = (keluaran.get('peringatan') or []) + [
            f'{len(satuan)} satuan bahan tidak dikenali mesin ('
            + ', '.join(satuan[:5]) + (', ...' if len(satuan) > 5 else '')
            + f') dan dihitung sebagai 100 g per bagian — periksa di admin Bahan.']
    return keluaran


def rekomendasi_sppg(db: Session, sekolah: ProfilSekolahIn) -> dict:
    """Rencana SPPG: paket per kelompok penerima manfaat, skala ratusan porsi."""
    snapshot = engine_data.bangun_snapshot(db, sekolah.region)
    alergi = core.normal_alergen(sekolah.allergies)
    keluaran = {'status': 'ok', 'sekolah': sekolah.name, 'wilayah': sekolah.region,
                'alergi': alergi, 'kelompok': [], 'peringatan': [], 'total_siswa': 0,
                'total_biaya': 0}
    if snapshot['jumlah_menu'] == 0:
        return keluaran | {'status': 'infeasible',
                           'alasan': 'belum ada data menu/bahan di basis data',
                           'saran': 'jalankan scripts/import_nutrivillage_dataset.py'}

    layak = core.saring(list(snapshot['menu'].values()), alergi)
    for g in sekolah.groups:
        acuan = SPPG_LEVEL[g.level]
        ak = core.baris_akg(snapshot, _contoh_umur(acuan['age_group']), 'laki-laki')
        energi_harian = float(ak.get('energi_kcal') or 0)
        protein_harian = float(ak.get('protein_g') or 0)
        anggaran = float(g.budget_per_portion or ANGGARAN_BGN.get(g.level, 10000.0))
        tk = energi_harian / PORSI_HARIAN
        tp = protein_harian / PORSI_HARIAN
        mikro = {k: float(ak.get(core_key) or 0) / PORSI_HARIAN for k, core_key in (
            ('kalsium_mg', 'kalsium_mg'), ('besi_mg', 'besi_mg'),
            ('vitamin_a_mcg', 'vitamin_a_mcg'), ('vitamin_c_mg', 'vitamin_c_mg'))}
        slots = _slot_wajib(alergi, include_susu=True)

        paket, status, catatan = core.rakit_paket(
            layak, slots, anggaran, tk, tp, mikro, snapshot['bobot'],
            mode='komponen', preferences=(), sudah_dipakai=())
        baris = {'level': g.level, 'label': acuan['label'], 'siswa': g.student_count,
                 'anggaran_per_porsi': anggaran, 'target_kcal': round(tk, 1),
                 'target_protein': round(tp, 2)}
        if status != 'ok':
            keluaran['peringatan'].append(
                f"{acuan['label']}: {status} — {catatan['alasan']} "
                f"(butuh minimum {keluarga_rp(catatan.get('minimum_dibutuhkan') or 0)}"
                f"/porsi pada anggaran {keluarga_rp(anggaran)})")
            baris |= {'paket': [], 'ringkas': None, 'biaya_batch': 0,
                      'anggaran_batch': round(anggaran * g.student_count),
                      'status': status}
            keluaran['kelompok'].append(baris)
            continue
        ringkas = core.ringkas_paket(paket, anggaran, tk, tp)
        baris |= {'paket': [_item(p) for p in paket], 'ringkas': ringkas,
                  'biaya_batch': round(ringkas['total_biaya'] * g.student_count),
                  'anggaran_batch': round(anggaran * g.student_count), 'status': 'ok'}
        if catatan.get('slot_ditinggalkan'):
            keluaran['peringatan'].append(
                f"{acuan['label']}: slot "
                f"{', '.join(catatan['slot_ditinggalkan'])} tidak punya kandidat "
                f"yang lolos alergi; porsinya dibagi ulang.")
        keluaran['total_siswa'] += g.student_count
        keluaran['total_biaya'] += baris['biaya_batch']
        keluaran['kelompok'].append(baris)

    if not any(k['status'] == 'ok' for k in keluaran['kelompok']):
        keluaran['status'] = 'infeasible'
        keluaran['alasan'] = 'tidak ada kelompok yang dapat dipenuhi pada anggarannya'
    return _peringatan_harga(keluaran, snapshot)


def _contoh_umur(kelompok):
    """Ambil umur tengah kelompok AKG untuk pencarian baris acuan."""
    for lo, hi, label in core.KELOMPOK_UMUR:
        if label == kelompok:
            return (lo + hi) // 2 if hi < 200 else 85
    return 25


def belanja_keluarga(db: Session, profil: ProfilKeluargaIn,
                     rencana: dict | None = None) -> DaftarBelanja:
    """Kebutuhan bahan mentah, diskalakan faktor porsi (bukan jumlah kepala).

    Gram bahan dibagi BDD karena harga pasar berlaku untuk berat kotor.
    """
    snapshot = engine_data.bangun_snapshot(db, profil.region)
    rencana = rencana or rekomendasi_keluarga(db, profil)
    info = core.target_keluarga(snapshot, profil)
    faktor = info['faktor'] * max(info['n_utama'], 1)
    total = defaultdict(lambda: [0.0, 0.0])
    peringatan = []
    untuk = [p for w in rencana.get('waktu_makan', []) for p in w['paket']]
    untuk += [{'recipe_id': s['recipe_id'], 'slot': s.get('slot', 'buah')}
              for s in rencana.get('selingan', [])]
    for item in untuk:
        menu = snapshot['menu'].get(str(item['recipe_id']))
        if not menu:
            continue
        for bagian in menu['komposisi']:
            b = snapshot['bahan'].get(bagian['ingredient_id']) or {}
            bdd = (float(b.get('bdd_percent') or 100) / 100.0) or 1.0
            gram_kotor = bagian['gram'] * faktor / bdd
            hp = b.get('harga_per_kg')
            kunci = (bagian['ingredient_id'], bagian['nama_bahan'])
            total[kunci][0] += gram_kotor
            total[kunci][1] += (gram_kotor / 1000.0 * float(hp)) if hp else 0.0
            if not hp:
                peringatan.append(bagian['nama_bahan'])
    baris = [DaftarBelanjaBaris(
        ingredient_id=k[0], nama_bahan=k[1], gram=round(v[0], 1),
        kg=round(v[0] / 1000.0, 3), biaya=round(v[1]))
        for k, v in sorted(total.items(), key=lambda x: -x[1][1])]
    return DaftarBelanja(
        label='Satu hari (seluruh waktu makan)', faktor_porsi=round(faktor, 2), baris=baris,
        total_biaya=round(sum(b.biaya for b in baris)),
        peringatan=sorted(set(f'Harga belum tersedia untuk: {p}' for p in peringatan)))
