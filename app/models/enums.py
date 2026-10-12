"""Enum domain bersama.

Nilai enum **disesuaikan dengan istilah yang dipakai aplikasi web**
(mis. `activity_level` = rendah/sedang/tinggi), bukan label mentah SKPL,
supaya tidak perlu lapisan penerjemahan di frontend.

Pemetaan ke SKPL V4 (untuk dokumentasi):
- activity_level: rendah=low, sedang=medium, tinggi=high
- meal_type: sarapan, makan-siang, makan-malam (SKPL: makan_siang)
- users.role: user/petugas_sppg/admin/guest (SKPL: user/admin; diperluas)
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SAEnum


def enum_column(enum_cls: type[Enum], name: str) -> SAEnum:
    """Kolom ENUM yang menyimpan *value* anggota (bukan nama)."""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda cls: [member.value for member in cls],
    )


class IngredientCategory(str, Enum):
    POKOK = "Pokok"
    PROTEIN = "Protein"
    SAYUR = "Sayur"
    BUAH = "Buah"
    BUMBU = "Bumbu"
    SUSU = "Susu"
    LAINNYA = "Lainnya"


class RecipeCategory(str, Enum):
    MAKANAN_UTAMA = "Makanan Utama"
    SAYUR = "Sayur"
    LAUK = "Lauk"
    BERKUAH = "Berkuah"
    CAMILAN = "Camilan"
    MINUMAN = "Minuman"


class ActivityLevel(str, Enum):
    RENDAH = "rendah"
    SEDANG = "sedang"
    TINGGI = "tinggi"


class Gender(str, Enum):
    LAKI_LAKI = "laki-laki"
    PEREMPUAN = "perempuan"


class AgeGroup(str, Enum):
    BALITA = "balita"
    ANAK = "anak"
    DEWASA = "dewasa"
    LANSIA = "lansia"


class PriceStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PriceSourceType(str, Enum):
    SCRAPER = "scraper"
    MANUAL = "manual"


class PriceVerificationStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class SeasonalStatus(str, Enum):
    IN_SEASON = "in_season"
    SHOULDER = "shoulder"
    OFF_SEASON = "off_season"


class LocalLevel(str, Enum):
    ABUNDANT = "abundant"
    AVAILABLE = "available"
    LIMITED = "limited"


class MealType(str, Enum):
    SARAPAN = "sarapan"
    MAKAN_SIANG = "makan-siang"
    MAKAN_MALAM = "makan-malam"


class DayOfWeek(str, Enum):
    SENIN = "senin"
    SELASA = "selasa"
    RABU = "rabu"
    KAMIS = "kamis"
    JUMAT = "jumat"
    SABTU = "sabtu"
    MINGGU = "minggu"


class ScraperStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class FoodSafetyVerification(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class NotificationKind(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"


class ArticleCategory(str, Enum):
    GIZI_DASAR = "Gizi Dasar"
    PANGAN_LOKAL = "Pangan Lokal"
    TIPS_HEMAT = "Tips Hemat"
    KESEHATAN = "Kesehatan"
