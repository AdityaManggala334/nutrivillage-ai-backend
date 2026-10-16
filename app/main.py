"""Entry point FastAPI NutriVillage AI — FR-01 (Auth) + profil petugas SPPG MBG."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import Base, engine

# Impor model agar seluruh tabel terdaftar pada Base.metadata.
from app.models import SppgOfficer, User  # noqa: F401
from app.routers import (
    account,
    auth,
    content,
    history,
    market,
    master,
    profile,
    recipes,
    schools,
    users,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Gagal cepat bila konfigurasi produksi belum aman (JWT_SECRET default, dsb).
    settings.validate_production()
    # Tabel dibuat otomatis bila belum ada (idempoten). Database dibuat oleh
    # scripts/init_db.py karena CREATE DATABASE tidak bisa via create_all.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Backend NutriVillage AI. Fase ini mencakup autentikasi dan registrasi "
        "masyarakat umum serta petugas SPPG MBG."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(account.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(schools.router, prefix=settings.api_prefix)
app.include_router(master.router, prefix=settings.api_prefix)
app.include_router(market.router, prefix=settings.api_prefix)
app.include_router(content.router, prefix=settings.api_prefix)
app.include_router(profile.router, prefix=settings.api_prefix)
app.include_router(recipes.router, prefix=settings.api_prefix)
app.include_router(history.router, prefix=settings.api_prefix)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
