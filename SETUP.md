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

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/init_db.py          # buat tabel + data acuan (wilayah, bobot SAW) + akun demo
uvicorn app.main:app --reload --port 8000
```

**Windows (PowerShell / CMD)**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate             # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python scripts\init_db.py
uvicorn app.main:app --reload --port 8000
```

Catatan Windows:

- Butuh **Python 3.12** dari python.org — centang **“Add python.exe to PATH”** saat memasang.
- Jika PowerShell menolak mengaktifkan venv, jalankan sekali:
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
- `uvloop` **tidak tersedia untuk Windows**; di `requirements.txt` barisnya sudah diberi
  penanda `; sys_platform != "win32"` sehingga otomatis dilewati (uvicorn tetap berjalan
  memakai asyncio biasa). Semua paket lain memiliki wheel Windows untuk Python 3.12.
  Bila pip Anda tetap mengeluh soal `uvloop`, lewati barisnya secara manual:
  ```powershell
  Get-Content requirements.txt | Where-Object { $_ -notmatch '^uvloop' } | Set-Content requirements-win.txt
  pip install -r requirements-win.txt
  ```
- Path CA TiDB di `.env` tulis dengan garis miring depan (`C:/Users/Nama/isrgrootx1.pem`)
  atau tempel isi file PEM-nya — jangan backslash mentah.
- Bila clone berada di path panjang, aktifkan `git config --system core.longpaths true`.
- Berkas `*.sh` (mis. `scripts/start.sh`, `docker-entrypoint.sh`) hanya dipakai Render/Docker,
  jadi tidak perlu dijalankan di Windows.

Health check: <http://127.0.0.1:8000/health>

### 3. Variabel `.env` yang sering ditanya

| Variabel | Default | Keterangan |
| --- | --- | --- |
| `DATABASE_URL` | MySQL lokal | Format TiDB: `mysql+pymysql://<user>.<root>:<pass>@<host>:4000/<db>?charset=utf8mb4` |
| `DATABASE_SSL_CA` | kosong | Isi file PEM (deploy) atau path `.pem` (lokal). Wajib untuk TiDB Cloud |
| `SKIP_CREATE_DATABASE` | `false` | Set `1` untuk DB terkelola (TiDB Serverless tidak mengizinkan `CREATE DATABASE`) |
| `SEED_CONTENT` | `false` | `1` = isi katalog contoh (bahan, resep, harga, artikel). **Jangan** `1` di produksi |
| `RESET_DATA` | `false` | `1` = **hapus seluruh data** saat boot. Hanya untuk mengosongkan DB milik sendiri |
| `BOOTSTRAP_ADMIN_EMAIL/PASSWORD` | kosong | Bila diisi, admin awal dibuat (hanya jika belum ada) |
| `JWT_SECRET` | nilai dev | **Harus sama** dengan `JWT_SECRET` di `web-next/.env.local` |


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
- Semua data aplikasi tersimpan di database: akun/login (`users`, `sppg_officers`),
  profil keluarga (`profiles`, `family_members`), katalog (`ingredients`, `recipes`,
  `recipe_ingredients`, `nutrition_facts`, `prices`, `seasonal_availability`,
  `local_availability`), konten (`articles`, `notifications`, `food_safety_info`),
  riwayat & favorit (`history_entries`, `favorites`), serta meal planner & daftar
  belanja (`meal_plans`, `shopping_lists`, `shopping_list_items`).
- Yang **tidak** diambil dari database: algoritma Recommendation Engine (SAW) yang
  menghitung skor saat request. Agar ada bahan uji, set `SEED_CONTENT=1` lalu jalankan
  `python scripts/init_db.py` (kembalikan ke `0` setelahnya).
