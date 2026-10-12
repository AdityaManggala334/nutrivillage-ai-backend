#!/usr/bin/env sh
# Start command untuk Render / platform PaaS lain.
# 1) Menyiapkan tabel + akun awal (idempoten).
# 2) Menjalankan FastAPI pada port dari environment ($PORT).
set -e

python scripts/init_db.py
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
