#!/bin/sh
# Entrypoint backend NutriVillage AI.
# - Menyiapkan tabel + seed akun demo (idempoten, aman dijalankan berulang).
# - Menjalankan FastAPI via uvicorn.
set -e

echo "[entrypoint] Menyiapkan database (scripts/init_db.py)..."
python scripts/init_db.py

echo "[entrypoint] Menjalankan FastAPI di 0.0.0.0:8000 ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
