# NutriVillage AI — Backend (FastAPI + MySQL)
#
# Build:  docker build -t nutrivillage-backend .
# Run:    lihat docker-compose.full.yml (disarankan)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependensi Python (semua punya wheel manylinux, tak perlu compiler).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Kode aplikasi.
COPY . .

RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
