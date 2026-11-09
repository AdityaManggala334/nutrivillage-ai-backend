# Deploy Backend NutriVillage AI — Render + TiDB Cloud

Panduan ini men-deploy **backend FastAPI** ke **Render**, dengan database
**TiDB Cloud** (MySQL-compatible). Frontend di-deploy terpisah ke Vercel
(lihat `web-next/DEPLOY.md` di repo frontend).

```
Browser → Vercel (Next.js) → Render (FastAPI) → TiDB Cloud (MySQL)
```

---

## 0. Prasyarat
- Akun [Render](https://render.com) (gratis).
- Akun [TiDB Cloud](https://tidbcloud.com) (Starter, gratis).
- Repo ini sudah ada di GitHub.

---

## 1. Buat database di TiDB Cloud
1. Buat cluster **TiDB Cloud Starter** (pilih region **Singapore**).
2. Buka **Connect** → catat:
   - **Host** (mis. `gateway01.ap-southeast-1.prod.aws.tidbcloud.com`)
   - **Port**: `4000`
   - **User** (mis. `3xxxxxx.root`)
   - **Password**
   - **Database**: biasanya `test` (pakai ini; TiDB Serverless tidak mengizinkan `CREATE DATABASE`).
3. Unduh **CA certificate** (klik *Download CA cert* / salin isi file `isrgrootx1.pem` atau `ca.pem`).

> Bentuk `DATABASE_URL`:
> ```
> mysql+pymysql://<user>:<password>@<host>:4000/test?charset=utf8mb4
> ```

---

## 2. Deploy ke Render
1. Render → **New → Blueprint** → pilih repo `nutrivillage-ai-backend`.
   (Blueprint `render.yaml` sudah tersedia.)
2. Isi variabel bertanda **wajib** (kolom Environment):

| Key | Nilai |
| --- | --- |
| `DATABASE_URL` | connection string TiDB di atas |
| `DATABASE_SSL_CA` | **isi** file CA (PEM) yang diunduh pada langkah 1 |
| `DATABASE_SSL_VERIFY` | `true` |
| `JWT_SECRET` | nilai rahasia acak, kuat (mis. hasil `openssl rand -hex 32`) |
| `CORS_ORIGINS` | URL frontend Vercel, mis. `https://nutrivillage.vercel.app` |
| `BOOTSTRAP_ADMIN_EMAIL` | email admin awalmu |
| `BOOTSTRAP_ADMIN_PASSWORD` | password admin awal (kuat) |

   Variabel `ENVIRONMENT=production`, `SKIP_CREATE_DATABASE=1`,
   `SEED_DEMO_ACCOUNTS=0` sudah diatur otomatis oleh blueprint.
3. Klik **Apply/Deploy**. Tunggu sampai build selesai.
4. Saat start, `scripts/start.sh` menjalankan `init_db.py` (membuat tabel +
   akun admin awal dari env).

> Render otomatis menjalankan ulang `init_db.py` setiap deploy/restart — aman
> karena idempoten.

---

## 3. Verifikasi
Buka (ganti dengan URL Render-mu):
- `https://<nama-service>.onrender.com/health` → `{"status":"ok",...}`
- `https://<nama-service>.onrender.com/docs` → Swagger UI

Cek log Render: pastikan tidak ada error `Access denied` atau TLS.

---

## 4. Anti "tidur" (keep-warm) — penting untuk Render free
Render free menidurkan service setelah ±15 menit idle; request pertama jadi
lambat (30–50 detik). Supaya demo tetap responsif:
- Buat cron gratis di [cron-job.org](https://cron-job.org) yang memanggil
  `https://<nama-service>.onrender.com/health` **setiap 10 menit**.

---

## 5. Update ke depannya
```bash
git push            # ke GitHub
# Render otomatis redeploy (auto-deploy aktif)
```

### 5a. Urutan migrasi bila ada nilai ENUM baru

Kolom `users.role` dan `prices.source_type` adalah MySQL `ENUM`. Menambah nilai
di kode **tidak** menambah nilai di database. Jika kode lebih dulu ter-deploy
sebelum kolomnya dilebarkan, MySQL menolak menulis (`Data truncated for column
'role'`) dan pengguna baru gagal dibuat.

Urutan aman:

1. Jalankan `ALTER TABLE` lebih dulu (Render > Shell, atau client MySQL):

   ```sql
   ALTER TABLE users  MODIFY role ENUM('user','petugas_sppg','petugas_lapangan','admin','guest') NOT NULL;
   ALTER TABLE prices MODIFY source_type ENUM('scraper','manual','lapangan') NOT NULL;
   ALTER TABLE prices ADD COLUMN created_by INTEGER NULL;
   ```

2. Baru `git push` kode yang memakai nilai baru.

`scripts/init_db.py` (yang dijalankan `start.sh`) sudah memuat pernyataan ini,
tetapi ia berjalan setelah aplikasi siap melayani pada boot pertama — jadi untuk
perubahan ENUM, jalankan manual lebih dulu.

### 5b. Membersihkan data latihan

`seed_scraper_runs()` sudah dihapus dari kode, tetapi baris lamanya masih ada di
database yang pernah di-seed. Halaman Monitoring akan tetap menampilkan angka
latihan sampai baris itu dihapus:

```sql
DELETE FROM scraper_runs;
UPDATE prices SET source_type = 'manual' WHERE source_type = 'scraper';
```

Pernyataan `UPDATE` di atas hanya benar bila scraper sungguhan belum pernah
berjalan — periksa dulu dengan `SELECT COUNT(*) FROM scraper_runs`.

---

## 6. Troubleshooting
| Gejala | Sebab / solusi |
| --- | --- |
| `Konfigurasi produksi belum aman` | `ENVIRONMENT=production` tapi `JWT_SECRET` masih default / `DATABASE_URL` lokal / `DATABASE_SSL_CA` kosong / `SEED_DEMO_ACCOUNTS` masih true |
| `Access denied for user` | Cek user/password TiDB di `DATABASE_URL` |
| Error TLS / SSL | Pastikan `DATABASE_SSL_CA` berisi **isi** file CA (bukan path yang tidak ada di Render) |
| `Table doesn't exist` | `init_db.py` gagal di start — cek log Render |
| Login frontend gagal | `JWT_SECRET` harus **sama** dengan env Vercel |

---

## Alternatif: Docker (VM / Fly.io)
Repo ini juga menyertakan `Dockerfile` + `docker-compose.full.yml` (untuk
menjalankan seluruh stack, termasuk MySQL, di satu VM). Lihat `SETUP.md`.
