# NutriVillage AI — Cara Menjalankan

Repo ini adalah **backend** (FastAPI + MySQL). Ia dipakai bersama repo frontend
[`nutrivillage-ai-frontend`](https://github.com/AdityaManggala334/nutrivillage-ai-frontend)
(folder `web-next/`).

---

## ⭐ Cara tercepat — Docker (cukup punya Docker Desktop)

Tidak perlu install Node.js, Python, atau MySQL.

### 1. Clone KEDUA repo secara bersebelahan

Nama folder **harus** sama seperti di bawah:

```bash
mkdir nutrivillage && cd nutrivillage
git clone https://github.com/AdityaManggala334/nutrivillage-ai-frontend.git
git clone https://github.com/AdityaManggala334/nutrivillage-ai-backend.git
```

Hasilnya:

```
nutrivillage/
├─ nutrivillage-ai-frontend/    # berisi web-next/
└─ nutrivillage-ai-backend/     # jalankan perintah dari sini
```

### 2. Jalankan semuanya

```bash
cd nutrivillage-ai-backend
docker compose -f docker-compose.full.yml up --build
```

Tunggu sampai muncul log `Uvicorn running on http://0.0.0.0:8000`.

### 3. Buka di browser

| Layanan | URL |
| --- | --- |
| **Website** | <http://localhost:3000> |
| API docs (Swagger) | <http://localhost:8000/docs> |
| Adminer (eksplor DB) | <http://localhost:8080> |

Login Adminer: System **MySQL**, Server **db**, Username **root**, Password *(kosong)*,
Database **nutri_village_ai**.

### 4. Akun demo

| Peran | Email | Password |
| --- | --- | --- |
| Masyarakat | `keluarga@nutrivillage.id` | `nutrivillage` |
| Petugas SPPG | `sppg@nutrivillage.id` | `sppg12345` |
| Admin | `admin@nutrivillage.id` | `admin12345` |

Akun ini dibuat otomatis saat container backend pertama kali start.

### Perintah berguna

```bash
docker compose -f docker-compose.full.yml ps        # status
docker compose -f docker-compose.full.yml logs -f   # lihat log
docker compose -f docker-compose.full.yml down      # stop (data MySQL tetap)
docker compose -f docker-compose.full.yml down -v   # stop + HAPUS SEMUA DATA
```

---

## Cara manual (tanpa Docker)

Butuh **Python 3.11+** dan **MySQL 8 / MariaDB**.

### 1. Nyalakan MySQL

Pakai MySQL/MariaDB lokal (user `root` tanpa password), atau via Docker saja:

```bash
docker compose up -d          # memakai docker-compose.yml (MySQL + Adminer)
```

### 2. Siapkan & jalankan backend

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python scripts/init_db.py          # buat tabel + akun demo
uvicorn app.main:app --reload --port 8000
```

Health check: <http://127.0.0.1:8000/health>

---

## Endpoint utama

Semua di bawah prefix `/api/v1`:

| Method | Endpoint | Keterangan |
| --- | --- | --- |
| POST | `/auth/register` | Registrasi (masyarakat / petugas SPPG) |
| POST | `/auth/login` | Login → JWT |
| POST | `/auth/logout` | Logout |
| GET | `/auth/me` | Profil sesi |
| GET | `/users/count` | Jumlah pengguna (admin) |
| GET/POST | `/users` | Daftar / tambah pengguna (admin) |
| PATCH | `/users/{id}` | Ubah pengguna (admin) |
| GET/POST | `/schools` | Sekolah (petugas SPPG) |
| GET/PATCH/DELETE | `/schools/{id}` | Detail / ubah / hapus sekolah |
| GET/POST | `/schools/{id}/groups` | Kelompok penerima manfaat |
| GET | `/budget-policies` | Kebijakan anggaran |

## Catatan

- `JWT_SECRET` **harus sama** dengan milik frontend agar token bisa diverifikasi.
  Pada Docker, nilai sudah diset di `docker-compose.full.yml`.
- Perubahan kode cukup di-commit & push; untuk update di sisi pengguna:
  `git pull && docker compose -f docker-compose.full.yml up --build`.
- Fitur yang sudah **tersimpan permanen di MySQL**: akun/login, pengguna (admin),
  sekolah + kelompok penerima manfaat, kebijakan anggaran. Fitur lain (resep,
  rekomendasi, meal planner, shopping list) masih in-memory/mock.
