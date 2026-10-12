# Backend NutriVillage AI (FastAPI + MySQL)

Backend untuk **FR-01 Autentikasi & Akses**. Fase ini mencakup registrasi,
login, logout, dan profil sesi untuk dua jenis pengguna baru:

- **Masyarakat umum** (`role = user`)
- **Petugas SPPG MBG** (`role = petugas_sppg`) — menyimpan NIP, unit SPPG,
  wilayah, dan jabatan (opsional)

## Teknologi

| Komponen | Keterangan |
| --- | --- |
| Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Database | MySQL 8 / MariaDB 10.4 (XAMPP) — database `nutri_village_ai` |
| Autentikasi | JWT (HS256, PyJWT) + bcrypt (password hash) |
| Validasi | Pydantic v2 |

## Menjalankan

```bash
# 0) Nyalakan MySQL 8 (+ Adminer) lewat Docker
#    (alternatif: pakai MySQL/MariaDB lokal dengan kredensial yang sama)
docker compose up -d
docker compose logs -f mysql   # tunggu "ready for connections"

# 1) Siapkan virtualenv & dependensi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2) Buat database + tabel + akun demo
python scripts/init_db.py

# 3) Jalankan server
uvicorn app.main:app --reload --port 8000
```

> Jalankan uvicorn dari root repo ini karena `.env` dibaca relatif ke CWD.
> `docker-compose.yml` menyediakan MySQL 8 di `127.0.0.1:3306`
> (user `root`, tanpa password, database `nutri_village_ai`) dan Adminer di
> <http://localhost:8080>.

Dokumentasi interaktif: <http://127.0.0.1:8000/docs>

### Akun demo (dibuat `init_db.py`)

| Peran | Email | Password |
| --- | --- | --- |
| Masyarakat | `keluarga@nutrivillage.id` | `nutrivillage` |
| Petugas SPPG | `sppg@nutrivillage.id` | `sppg12345` |
| Admin | `admin@nutrivillage.id` | `admin12345` |

## Endpoint

| Method | Endpoint | Keterangan |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Registrasi masyarakat / petugas SPPG |
| POST | `/api/v1/auth/login` | Login, mengembalikan JWT |
| POST | `/api/v1/auth/logout` | Logout (stateless, hapus cookie di klien) |
| GET | `/api/v1/auth/me` | Profil sesi (butuh `Authorization: Bearer <token>`) |
| GET | `/api/v1/users/count` | Jumlah pengguna (khusus admin) |
| GET | `/health` | Health check |

### Contoh registrasi petugas SPPG

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Siti Petugas",
    "email": "siti.sppg@example.com",
    "password": "sppgpass123",
    "confirm_password": "sppgpass123",
    "role": "petugas_sppg",
    "nip": "199203152019032007",
    "sppg_unit": "SPPG Dolopo",
    "region": "Kec. Dolopo, Kab. Madiun",
    "position": "Ahli Gizi"
  }'
```

## Konfigurasi

Salin `.env.example` menjadi `.env`. Variabel penting:

- `DATABASE_URL` — default `mysql+pymysql://root:@127.0.0.1:3306/nutri_village_ai?charset=utf8mb4`
- `JWT_SECRET` — **harus sama** dengan `JWT_SECRET` di frontend
  (folder `web-next/`, file `.env.local` pada repo `nutrivillage-ai-frontend`)
  agar frontend dapat memverifikasi token.

## Integrasi Frontend

Route Handler Next.js (`src/app/api/auth/*`) berperan sebagai **proxy** ke
backend ini melalui `src/server/backend-api.ts`. Cookie `nutrivillage_session`
(JWT) dan `nutrivillage_role` tetap dipakai middleware untuk proteksi rute.

## Fase berikutnya

Tabel PDM lain dari SKPL V4 Final (profiles, family_members, ingredients,
prices, recipes, recommendations, dst.) dan endpoint per FR (FR-02 s.d. FR-10)
belum termasuk pada fase ini.
