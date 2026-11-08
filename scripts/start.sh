#!/usr/bin/env sh
# Start command untuk Render / platform PaaS lain.
# 1) Menyiapkan tabel + akun awal (idempoten) dengan batas waktu.
# 2) Menjalankan FastAPI pada port dari environment ($PORT).
#
# init_db TIDAK boleh menahan boot tanpa batas: TiDB Serverless bisa
# scale-to-zero sehingga koneksi pertama lambat dan health check Render gagal.
set -e

if command -v timeout >/dev/null 2>&1; then
  timeout 120 python scripts/init_db.py || echo "[db] init_db gagal/timeout — API tetap dijalankan"
else
  python scripts/init_db.py || echo "[db] init_db gagal — API tetap dijalankan"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
