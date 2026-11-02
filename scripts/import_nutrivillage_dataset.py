"""Impor dataset NutriVillage v2.2 ke basis data.

Pemakaian::

    python scripts/import_nutrivillage_dataset.py                     # folder bawaan
    python scripts/import_nutrivillage_dataset.py --dry-run           # pratinjau
    python scripts/import_nutrivillage_dataset.py --sumber /path/Dataset
    python scripts/import_nutrivillage_dataset.py --region "Kota Madiun"

Berkas yang dibaca (nama harus diawali nomor ini): 01, 02, 03, 04, 05, 06, 07, 10.
Berkas lain diabaikan, termasuk 08/09/11 yang hanya dipakai notebook.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.services.dataset_import import impor_teks  # noqa: E402

BERKAS_WAJIB = ('01_menu_komponen', '02_bahan_gizi', '03_resep_komponen',
                '04_harga_pangan', '05_akg', '10_antropometri_zscore')

BAWAAN = Path('/home/amputra/Documents/Materi Kuliah Semester 3/Py Untuk Sistem '
              'Cerdas/Laporan UTS/NutriVillage_v2/Dataset')


def muat(sumber: Path) -> dict[str, str]:
    isi = {}
    for berkas in sorted(sumber.glob('*.csv')):
        for logis in ('01_menu_komponen', '02_bahan_gizi', '03_resep_komponen',
                      '04_harga_pangan', '05_akg', '06_musim_pangan',
                      '07_alergen_bahan', '10_antropometri_zscore'):
            if berkas.name.startswith(logis):
                isi[logis] = berkas.read_text(encoding='utf-8-sig')
                break
    return isi


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sumber', type=Path, default=BAWAAN,
                        help='folder berisi CSV dataset v2.2')
    parser.add_argument('--region', default='Kabupaten Madiun',
                        help='wilayah acuan harga & ketersediaan lokal')
    parser.add_argument('--dry-run', action='store_true',
                        help='validasi saja, tidak menulis apa pun')
    args = parser.parse_args()

    if not args.sumber.is_dir():
        print(f'Folder dataset tidak ditemukan: {args.sumber}')
        return 2
    isi = muat(args.sumber)
    kurang = [b for b in BERKAS_WAJIB if b not in isi]
    if kurang:
        print('Berkas wajib belum ada:', ', '.join(kurang))
        return 2

    db = SessionLocal()
    try:
        laporan = impor_teks(db, isi, region_nama=args.region, dry_run=args.dry_run)
    finally:
        db.close()

    print('Impor', 'PRATINJAU' if args.dry_run else 'DITERAPKAN', '-')
    print('  dibuat   :', laporan.get('dibuat'))
    print('  diperbarui:', laporan.get('diperbarui'))
    print('  gizi menu dihitung ulang:', laporan.get('gizi_menu_dihitung'), 'menu')
    error = laporan.get('error') or []
    print(f'  error baris: {laporan.get("jumlah_error")}')
    for e in error[:15]:
        print('   ', e)
    return 1 if error else 0


if __name__ == '__main__':
    raise SystemExit(main())
