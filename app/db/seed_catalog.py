"""Seed data katalog NutriVillage AI.

Sumber data: dataset mock aplikasi web (resep, bahan, harga, musim, komoditas
lokal, informasi keamanan pangan, artikel, notifikasi) dipindahkan ke MySQL/TiDB.

Idempoten: setiap entri dicek lewat kolom `code` (atau nama) sebelum dibuat.
Catatan: `nutrition_facts` (master TKPI) sengaja TIDAK diisi nilai karangan;
admin mengisinya dari sumber resmi. Gizi per resep memakai data aplikasi.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Article,
    FoodSafetyInfo,
    Ingredient,
    LocalAvailability,
    Notification,
    Price,
    Recipe,
    RecipeIngredient,
    RecipeNutrition,
    Region,
    ScraperRun,
    SeasonalAvailability,
    SystemConfig,
)
from app.models.enums import (
    ArticleCategory,
    FoodSafetyVerification,
    IngredientCategory,
    LocalLevel,
    NotificationKind,
    PriceSourceType,
    PriceStatus,
    RecipeCategory,
    ScraperStatus,
    SeasonalStatus,
)

_MONTHS = {
    "Januari": 1, "Februari": 2, "Maret": 3, "April": 4, "Mei": 5, "Juni": 6,
    "Juli": 7, "Agustus": 8, "September": 9, "Oktober": 10, "November": 11,
    "Desember": 12,
}


def _days_ago(n: int) -> datetime:
    return datetime.now() - timedelta(days=n)


REGIONS: list[dict] = [
    {"name": "Kabupaten Madiun", "province": "Jawa Timur"},
    {"name": "Kota Madiun", "province": "Jawa Timur"},
    {"name": "Luar Daerah", "province": "-"},
]

INGREDIENTS: list[dict] = [
    {"code": "bahan-beras", "name": "Beras", "category": IngredientCategory.POKOK, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-jagung", "name": "Jagung manis", "category": IngredientCategory.POKOK, "unit": "buah", "is_local": True, "is_in_season": True},
    {"code": "bahan-jagung-pipil", "name": "Jagung pipil", "category": IngredientCategory.POKOK, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-kentang", "name": "Kentang", "category": IngredientCategory.POKOK, "unit": "kg", "is_local": False, "is_in_season": True},
    {"code": "bahan-tempe", "name": "Tempe", "category": IngredientCategory.PROTEIN, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-tahu", "name": "Tahu", "category": IngredientCategory.PROTEIN, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-ayam", "name": "Ayam", "category": IngredientCategory.PROTEIN, "unit": "kg", "is_local": False, "is_in_season": True},
    {"code": "bahan-ikan-nila", "name": "Ikan nila", "category": IngredientCategory.PROTEIN, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-telur", "name": "Telur", "category": IngredientCategory.PROTEIN, "unit": "kg", "is_local": False, "is_in_season": True},
    {"code": "bahan-kacang", "name": "Kacang tanah", "category": IngredientCategory.PROTEIN, "unit": "kg", "is_local": True, "is_in_season": False},
    {"code": "bahan-teri", "name": "Ikan teri", "category": IngredientCategory.PROTEIN, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-kangkung", "name": "Kangkung", "category": IngredientCategory.SAYUR, "unit": "ikat", "is_local": True, "is_in_season": True},
    {"code": "bahan-tauge", "name": "Tauge", "category": IngredientCategory.SAYUR, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-terong", "name": "Terong", "category": IngredientCategory.SAYUR, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-labu-siam", "name": "Labu siam", "category": IngredientCategory.SAYUR, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-kacang-panjang", "name": "Kacang panjang", "category": IngredientCategory.SAYUR, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-wortel", "name": "Wortel", "category": IngredientCategory.SAYUR, "unit": "kg", "is_local": False, "is_in_season": True},
    {"code": "bahan-seledri", "name": "Seledri", "category": IngredientCategory.SAYUR, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-kemangi", "name": "Kemangi", "category": IngredientCategory.SAYUR, "unit": "ikat", "is_local": True, "is_in_season": True},
    {"code": "bahan-bayam", "name": "Bayam", "category": IngredientCategory.SAYUR, "unit": "ikat", "is_local": True, "is_in_season": True},
    {"code": "bahan-daun-pepaya", "name": "Daun pepaya", "category": IngredientCategory.SAYUR, "unit": "ikat", "is_local": True, "is_in_season": True},
    {"code": "bahan-tomat", "name": "Tomat", "category": IngredientCategory.SAYUR, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-gula-jawa", "name": "Gula jawa", "category": IngredientCategory.BUMBU, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-bawang-merah", "name": "Bawang merah", "category": IngredientCategory.BUMBU, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-bawang-putih", "name": "Bawang putih", "category": IngredientCategory.BUMBU, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-cabai", "name": "Cabai", "category": IngredientCategory.BUMBU, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-minyak", "name": "Minyak goreng", "category": IngredientCategory.BUMBU, "unit": "liter", "is_local": False, "is_in_season": True},
    {"code": "bahan-kecap", "name": "Kecap manis", "category": IngredientCategory.BUMBU, "unit": "liter", "is_local": False, "is_in_season": True},
    {"code": "bahan-kelapa", "name": "Kelapa parut", "category": IngredientCategory.BUMBU, "unit": "kg", "is_local": True, "is_in_season": True},
    {"code": "bahan-santan", "name": "Santan kelapa", "category": IngredientCategory.BUMBU, "unit": "liter", "is_local": True, "is_in_season": True},
    {"code": "bahan-bumbu", "name": "Bumbu rempah", "category": IngredientCategory.BUMBU, "unit": "paket", "is_local": True, "is_in_season": True},
    {"code": "bahan-daun-pisang", "name": "Daun pisang", "category": IngredientCategory.LAINNYA, "unit": "paket", "is_local": True, "is_in_season": True},
]

RECIPES: list[dict] = [
    {
        "code": "resep-nasi-pecel", "name": "Nasi Pecel Madiun", "category": RecipeCategory.MAKANAN_UTAMA,
        "description": "Nasi dengan sayur rebus dan sambal kacang khas Madiun yang kaya serat.",
        "servings": 4, "cooking_time_min": 30, "image_key": "pecel", "is_local": True, "in_season": True,
        "tags": ["sayur", "kacang", "tradisional"],
        "nutrition": (520, 18, 62, 22, 6),
        "steps": [
            "Rebus kangkung dan tauge hingga matang, lalu tiriskan.",
            "Haluskan kacang tanah, gula jawa, dan cabai menjadi sambal pecel.",
            "Sajikan nasi hangat dengan sayur dan sambal pecel.",
        ],
        "ingredients": [
            ("bahan-beras", 0.3, "kg", 4500), ("bahan-kacang", 0.1, "kg", 3000),
            ("bahan-kangkung", 1, "ikat", 3000), ("bahan-tauge", 0.15, "kg", 2500),
            ("bahan-tempe", 0.15, "kg", 3000), ("bahan-gula-jawa", 0.05, "kg", 1500),
        ],
    },
    {
        "code": "resep-sayur-lodeh", "name": "Sayur Lodeh Tempe", "category": RecipeCategory.SAYUR,
        "description": "Sayur kuah santan dengan tempe dan aneka sayuran lokal.",
        "servings": 4, "cooking_time_min": 30, "image_key": "lodeh", "is_local": True, "in_season": True,
        "tags": ["santan", "sayur"],
        "nutrition": (310, 14, 24, 18, 7),
        "steps": [
            "Potong tempe, labu siam, kacang panjang, dan terong.",
            "Rebus santan bersama bumbu hingga mendidih.",
            "Masukkan sayuran dan masak hingga empuk.",
        ],
        "ingredients": [
            ("bahan-kelapa", 0.2, "kg", 4000), ("bahan-tempe", 0.2, "kg", 4000),
            ("bahan-labu-siam", 0.3, "kg", 4000), ("bahan-kacang-panjang", 0.2, "kg", 3000),
            ("bahan-terong", 0.25, "kg", 3000),
        ],
    },
    {
        "code": "resep-oseng-kangkung", "name": "Oseng Kangkung Tempe", "category": RecipeCategory.SAYUR,
        "description": "Tumis kangkung dan tempe dengan bawang dan cabai, cepat dan murah.",
        "servings": 3, "cooking_time_min": 20, "image_key": "oseng", "is_local": True, "in_season": True,
        "tags": ["pedas", "sayur", "hemat"],
        "nutrition": (240, 12, 16, 14, 5),
        "steps": [
            "Tumis bawang merah dan cabai hingga harum.",
            "Masukkan tempe, masak sebentar.",
            "Tambahkan kangkung dan masak hingga layu.",
        ],
        "ingredients": [
            ("bahan-kangkung", 1, "ikat", 3000), ("bahan-tempe", 0.15, "kg", 3000),
            ("bahan-bawang-merah", 0.05, "kg", 1500), ("bahan-cabai", 0.03, "kg", 1500),
            ("bahan-minyak", 0.05, "liter", 2000),
        ],
    },
    {
        "code": "resep-sup-ayam-jagung", "name": "Sup Ayam Jagung", "category": RecipeCategory.BERKUAH,
        "description": "Sup hangat berisi ayam, jagung manis, dan sayuran untuk keluarga.",
        "servings": 4, "cooking_time_min": 45, "image_key": "sup", "is_local": True, "in_season": True,
        "tags": ["ayam", "berkuah", "anak"],
        "nutrition": (380, 26, 34, 14, 4),
        "steps": [
            "Rebus ayam hingga keluar kaldu.",
            "Masukkan jagung, wortel, dan kentang.",
            "Bumbui dan taburi seledri sebelum diangkat.",
        ],
        "ingredients": [
            ("bahan-ayam", 0.4, "kg", 14000), ("bahan-jagung", 2, "buah", 6000),
            ("bahan-wortel", 0.15, "kg", 3000), ("bahan-kentang", 0.2, "kg", 4000),
            ("bahan-seledri", 0.05, "kg", 1000),
        ],
    },
    {
        "code": "resep-tahu-telur", "name": "Tahu Telur Bumbu Kecap", "category": RecipeCategory.LAUK,
        "description": "Tahu dan telur dimasak dengan bumbu kecap manis, sumber protein terjangkau.",
        "servings": 3, "cooking_time_min": 25, "image_key": "tahu-telur", "is_local": True, "in_season": True,
        "tags": ["telur", "protein", "hemat"],
        "nutrition": (420, 24, 18, 28, 3),
        "steps": [
            "Goreng tahu dan telur hingga berkulit.",
            "Tumis bawang putih, lalu masukkan kecap.",
            "Masak tahu dan telur bersama bumbu hingga meresap.",
        ],
        "ingredients": [
            ("bahan-tahu", 0.3, "kg", 4500), ("bahan-telur", 4, "butir", 8000),
            ("bahan-kecap", 0.1, "liter", 3000), ("bahan-bawang-putih", 0.03, "kg", 1500),
            ("bahan-minyak", 0.05, "liter", 2000),
        ],
    },
    {
        "code": "resep-pepes-ikan", "name": "Pepes Ikan Nila", "category": RecipeCategory.LAUK,
        "description": "Ikan nila dibumbui rempah lalu dikukus dalam daun pisang, rendah lemak.",
        "servings": 4, "cooking_time_min": 40, "image_key": "pepes", "is_local": True, "in_season": True,
        "tags": ["ikan", "kukus", "protein"], "price_updated_days_ago": 9,
        "nutrition": (350, 30, 8, 20, 2),
        "steps": [
            "Lumuri ikan nila dengan bumbu halus.",
            "Bungkus ikan bersama kemangi dan cabai dalam daun pisang.",
            "Kukus hingga matang, lalu bakar sebentar.",
        ],
        "ingredients": [
            ("bahan-ikan-nila", 0.6, "kg", 21000), ("bahan-kemangi", 1, "ikat", 2500),
            ("bahan-cabai", 0.05, "kg", 2500), ("bahan-daun-pisang", 1, "paket", 2000),
            ("bahan-bumbu", 1, "paket", 3000),
        ],
    },
    {
        "code": "resep-urap-nasi-jagung", "name": "Nasi Jagung Urap Sayur", "category": RecipeCategory.MAKANAN_UTAMA,
        "description": "Nasi jagung khas pedesaan dengan urap sayur kelapa yang mengenyangkan.",
        "servings": 4, "cooking_time_min": 35, "image_key": "urap", "is_local": True, "in_season": True,
        "tags": ["jagung", "sayur", "tradisional"],
        "nutrition": (410, 12, 68, 10, 8),
        "steps": [
            "Masak nasi jagung hingga matang.",
            "Rebus bayam, kacang panjang, dan tauge.",
            "Campur sayur dengan kelapa parut berbumbu, sajikan dengan nasi jagung.",
        ],
        "ingredients": [
            ("bahan-jagung-pipil", 0.3, "kg", 5000), ("bahan-beras", 0.2, "kg", 3000),
            ("bahan-bayam", 1, "ikat", 2500), ("bahan-kacang-panjang", 0.15, "kg", 2500),
            ("bahan-kelapa", 0.15, "kg", 3000),
        ],
    },
    {
        "code": "resep-buntil-daun-pepaya", "name": "Buntil Daun Pepaya", "category": RecipeCategory.LAUK,
        "description": "Daun pepaya diisi kelapa berbumbu dan ikan teri, kaya serat dan kalsium.",
        "servings": 4, "cooking_time_min": 60, "image_key": "buntil", "is_local": True, "in_season": True,
        "tags": ["ikan", "sayur", "tradisional"], "price_updated_days_ago": 12,
        "nutrition": (290, 16, 20, 16, 9),
        "steps": [
            "Layukan daun pepaya lalu bungkus isian kelapa dan teri.",
            "Susun buntil dalam panci berisi santan encer.",
            "Masak dengan api kecil hingga bumbu meresap.",
        ],
        "ingredients": [
            ("bahan-daun-pepaya", 1, "ikat", 3000), ("bahan-kelapa", 0.25, "kg", 5000),
            ("bahan-teri", 0.1, "kg", 6000), ("bahan-santan", 0.3, "liter", 4500),
            ("bahan-bumbu", 1, "paket", 3000),
        ],
    },
]

# FR-23: harga bahan (sebagian sudah approved, sebagian pending verifikasi).
PRICES: list[dict] = [
    {"ingredient": "Beras", "price": 15000, "unit": "kg", "source": "Pasar Madiun", "status": PriceStatus.APPROVED, "days_ago": 1},
    {"ingredient": "Tempe", "price": 20000, "unit": "kg", "source": "Pasar Madiun", "status": PriceStatus.APPROVED, "days_ago": 2},
    {"ingredient": "Ayam", "price": 35000, "unit": "kg", "source": "Portal Pasar", "status": PriceStatus.APPROVED, "days_ago": 3},
    {"ingredient": "Kangkung", "price": 3500, "unit": "ikat", "source": "Portal Pasar", "status": PriceStatus.PENDING, "days_ago": 0},
    {"ingredient": "Ikan nila", "price": 36000, "unit": "kg", "source": "Portal Pasar", "status": PriceStatus.PENDING, "days_ago": 0},
    {"ingredient": "Telur", "price": 27000, "unit": "kg", "source": "Pasar Madiun", "status": PriceStatus.PENDING, "days_ago": 9},
]

SEASONS: list[dict] = [
    {"ingredient": "Jagung manis", "months": ["Januari", "Februari", "Maret", "April"], "status": SeasonalStatus.IN_SEASON},
    {"ingredient": "Kacang panjang", "months": ["Mei", "Juni", "Juli"], "status": SeasonalStatus.IN_SEASON},
    {"ingredient": "Terong", "months": ["April", "Mei", "Juni", "Juli"], "status": SeasonalStatus.IN_SEASON},
    {"ingredient": "Kangkung", "months": ["Sepanjang tahun"], "status": SeasonalStatus.IN_SEASON},
    {"ingredient": "Tomat", "months": ["Juni", "Juli", "Agustus"], "status": SeasonalStatus.IN_SEASON},
]

LOCAL_COMMODITIES: list[dict] = [
    {"ingredient": "Beras", "region": "Kabupaten Madiun", "level": LocalLevel.ABUNDANT},
    {"ingredient": "Tempe", "region": "Kabupaten Madiun", "level": LocalLevel.ABUNDANT},
    {"ingredient": "Ikan nila", "region": "Kabupaten Madiun", "level": LocalLevel.ABUNDANT},
    {"ingredient": "Jagung manis", "region": "Kabupaten Madiun", "level": LocalLevel.ABUNDANT},
    {"ingredient": "Kangkung", "region": "Kabupaten Madiun", "level": LocalLevel.AVAILABLE},
    {"ingredient": "Ayam", "region": "Luar Daerah", "level": LocalLevel.LIMITED},
]

# SKPL: bobot skoring SAW (AHP) 40/30/15/15.
SYSTEM_CONFIG: list[tuple[str, float]] = [
    ("weight_nutrition", 0.400),
    ("weight_budget", 0.300),
    ("weight_seasonal", 0.150),
    ("weight_local", 0.150),
]

FOOD_SAFETY: list[dict] = [
    {"code": "aman-1", "topic": "Telur", "risk_type": "Mikrobiologis — Salmonella",
     "hazard": "Telur mentah atau setengah matang dapat mengandung Salmonella yang menyebabkan gangguan pencernaan.",
     "handling": "Masak telur hingga bagian putih dan kuningnya matang, simpan pada suhu dingin, dan cuci tangan setelah menangani telur mentah.",
     "source": "Pedoman Keamanan Pangan Kemenkes RI", "verification": FoodSafetyVerification.VERIFIED},
    {"code": "aman-2", "topic": "Ayam & unggas", "risk_type": "Mikrobiologis — kontaminasi silang",
     "hazard": "Cairan mentah ayam dapat mencemari talenan dan peralatan sehingga menimbulkan kontaminasi silang.",
     "handling": "Pisahkan talenan bahan mentah dan matang, masak hingga suhu internal aman, serta bersihkan permukaan yang tersentuh.",
     "source": "WHO Five Keys to Safer Food", "verification": FoodSafetyVerification.VERIFIED},
    {"code": "aman-3", "topic": "Kacang tanah", "risk_type": "Kimiawi — aflatoksin",
     "hazard": "Kacang tanah yang disimpan lembap berisiko ditumbuhi kapang penghasil aflatoksin.",
     "handling": "Simpan kacang di tempat kering dan tertutup, buang yang berjamur atau berbau apek, dan pilih bahan dari sumber terpercaya.",
     "source": "Badan Pengawas Obat dan Makanan (BPOM)", "verification": FoodSafetyVerification.VERIFIED},
    {"code": "aman-4", "topic": "Sayuran daun", "risk_type": "Mikrobiologis & residu pestisida",
     "hazard": "Sayuran dapat membawa tanah, kotoran, atau residu pestisida bila tidak dicuci dengan benar.",
     "handling": "Cuci sayuran di bawah air mengalir, rendam sebentar bila perlu, dan masak hingga matang.",
     "source": "Belum diverifikasi", "verification": FoodSafetyVerification.PENDING},
    {"code": "aman-5", "topic": "Santan & olahan berkuah", "risk_type": "Mikrobiologis — pertumbuhan bakteri",
     "hazard": "Masakan santan yang dibiarkan pada suhu ruang terlalu lama cepat mengalami kerusakan.",
     "handling": "Sajikan segera, panaskan kembali hingga mendidih sebelum dikonsumsi, dan simpan sisa di lemari pendingin.",
     "source": "Belum diverifikasi", "verification": FoodSafetyVerification.PENDING},
]

ARTICLES: list[dict] = [
    {"code": "artikel-gizi-seimbang", "title": "Mengenal Gizi Seimbang untuk Keluarga",
     "excerpt": "Panduan sederhana menyusun porsi makan harian yang seimbang tanpa harus mahal.",
     "category": ArticleCategory.GIZI_DASAR, "read_minutes": 4,
     "body": [
         "Gizi seimbang bukan berarti harus mahal. Prinsip utamanya adalah memenuhi kebutuhan karbohidrat, protein, lemak, vitamin, dan mineral dalam porsi yang tepat setiap hari.",
         "Isi piring idealnya terdiri dari setengah bagian sayur dan buah, seperempat karbohidrat, dan seperempat protein. Untuk keluarga di Kabupaten Madiun, sumber protein bisa dipenuhi dari tempe, tahu, telur, atau ikan nila yang harganya terjangkau.",
         "Yang penting adalah konsistensi. Menyusun menu mingguan lebih dulu membuat belanja jadi lebih hemat dan gizi keluarga tetap terjaga.",
     ]},
    {"code": "artikel-pangan-lokal", "title": "Kenapa Memilih Pangan Lokal?",
     "excerpt": "Pangan lokal lebih segar, lebih murah, dan membantu petani di sekitar kita.",
     "category": ArticleCategory.PANGAN_LOKAL, "read_minutes": 3,
     "body": [
         "Pangan lokal adalah bahan makanan yang diproduksi di daerah sekitar kita. Karena jarak tempuhnya pendek, kesegarannya lebih terjaga dan harganya biasanya lebih murah.",
         "Di Kabupaten Madiun, kita mudah menemukan beras, tempe, kangkung, jagung manis, dan ikan nila. Memilih bahan-bahan ini berarti turut mendukung petani dan pelaku usaha lokal.",
         "NutriVillage AI mengutamakan pangan lokal dalam rekomendasinya supaya menu yang disusun tetap hemat dan bergizi.",
     ]},
    {"code": "artikel-hemat-budget", "title": "Tips Menyusun Menu dengan Anggaran Terbatas",
     "excerpt": "Beberapa cara praktis menekan biaya belanja tanpa mengurangi nilai gizi.",
     "category": ArticleCategory.TIPS_HEMAT, "read_minutes": 5,
     "body": [
         "Langkah pertama adalah menentukan anggaran harian keluarga. Setelah itu, susun menu yang memakai bahan yang sedang musim karena harganya lebih murah.",
         "Manfaatkan bahan yang bisa dipakai di beberapa menu sekaligus, misalnya tempe untuk oseng dan sayur lodeh. Ini membuat belanja lebih efisien.",
         "Terakhir, catat daftar belanja sebelum pergi ke pasar agar tidak membeli barang di luar rencana.",
     ]},
    {"code": "artikel-alergi", "title": "Mengelola Alergi Makanan di Rumah",
     "excerpt": "Cara mencatat dan menghindari bahan pemicu alergi saat menyusun menu.",
     "category": ArticleCategory.KESEHATAN, "read_minutes": 4,
     "body": [
         "Alergi makanan perlu dicatat dengan rapi agar tidak terlewat saat memasak. Catat bahan pemicunya, misalnya kacang, seafood, atau telur.",
         "Saat menyusun menu, pastikan bahan pemicu tidak dipakai. Aplikasi seperti NutriVillage AI dapat menyaring menu yang mengandung bahan pantangan keluarga.",
         "Selalu periksa label kemasan dan tanyakan bahan saat membeli makanan jadi.",
     ]},
]

NOTIFICATIONS: list[dict] = [
    {"code": "notif-1", "title": "Rekomendasi baru tersedia", "message": "3 menu bergizi sudah disiapkan sesuai anggaran keluarga.", "kind": NotificationKind.SUCCESS, "read": False, "days_ago": 0},
    {"code": "notif-2", "title": "Harga bahan diperbarui", "message": "Harga tempe dan kangkung sudah diverifikasi admin hari ini.", "kind": NotificationKind.INFO, "read": False, "days_ago": 1},
    {"code": "notif-3", "title": "Stok musiman", "message": "Jagung manis sedang musim, menu berbahan jagung lebih hemat.", "kind": NotificationKind.INFO, "read": True, "days_ago": 2},
    {"code": "notif-4", "title": "Pengingat jadwal masak", "message": "Meal Planner pekan ini belum lengkap. Yuk isi jadwalnya.", "kind": NotificationKind.WARNING, "read": True, "days_ago": 3},
]

SCRAPER_RUNS: list[dict] = [
    {"source": "Portal Pasar Madiun", "status": ScraperStatus.SUCCESS, "items_count": 42, "error_message": None, "days_ago": 0},
    {"source": "Portal Pasar Madiun", "status": ScraperStatus.SUCCESS, "items_count": 40, "error_message": None, "days_ago": 1},
    {"source": "Portal Pasar Madiun", "status": ScraperStatus.FAILED, "items_count": 0, "error_message": "Timeout saat mengambil halaman harga", "days_ago": 2},
    {"source": "Portal Pasar Madiun", "status": ScraperStatus.SUCCESS, "items_count": 41, "error_message": None, "days_ago": 3},
    {"source": "Portal Pasar Madiun", "status": ScraperStatus.PARTIAL, "items_count": 5, "error_message": "Struktur HTML berubah, selector tidak ditemukan", "days_ago": 4},
    {"source": "Portal Pasar Madiun", "status": ScraperStatus.SUCCESS, "items_count": 39, "error_message": None, "days_ago": 5},
]


def seed_regions(db: Session) -> dict[str, Region]:
    result: dict[str, Region] = {}
    for item in REGIONS:
        row = db.query(Region).filter(Region.name == item["name"]).one_or_none()
        if row is None:
            row = Region(**item)
            db.add(row)
            db.flush()
        result[item["name"]] = row
    db.commit()
    return result


def seed_ingredients(db: Session) -> dict[str, Ingredient]:
    result: dict[str, Ingredient] = {}
    for item in INGREDIENTS:
        row = db.query(Ingredient).filter(Ingredient.code == item["code"]).one_or_none()
        if row is None:
            row = Ingredient(**item)
            db.add(row)
            db.flush()
        result[item["code"]] = row
    db.commit()
    return result


def seed_recipes(db: Session, ingredients: dict[str, Ingredient]) -> None:
    for item in RECIPES:
        existing = db.query(Recipe).filter(Recipe.code == item["code"]).one_or_none()
        if existing is not None:
            continue
        total_cost = sum(line[3] for line in item["ingredients"])
        price_updated_at = _days_ago(item.get("price_updated_days_ago", 2))
        recipe = Recipe(
            code=item["code"],
            name=item["name"],
            category=item["category"],
            description=item["description"],
            servings=item["servings"],
            cooking_time_min=item["cooking_time_min"],
            steps=list(item["steps"]),
            tags=list(item["tags"]),
            image_key=item["image_key"],
            image_alt=f"Foto {item['name']}, sajian pangan lokal Kabupaten Madiun.",
            is_local=item["is_local"],
            in_season=item["in_season"],
            estimated_cost=total_cost,
            price_updated_at=price_updated_at,
        )
        cal, prot, carb, fat, fiber = item["nutrition"]
        recipe.nutrition = RecipeNutrition(
            calories=cal, protein=prot, carbohydrates=carb, fat=fat, fiber=fiber
        )
        recipe.ingredients = [
            RecipeIngredient(
                ingredient_id=(ingredients.get(code).id if ingredients.get(code) else None),
                name=(ingredients[code].name if code in ingredients else code),
                quantity=qty,
                unit=unit,
                estimated_price=price,
            )
            for (code, qty, unit, price) in item["ingredients"]
        ]
        db.add(recipe)
    db.commit()


def seed_prices(db: Session, ingredients: dict[str, Ingredient]) -> None:
    by_name = {ing.name: ing for ing in ingredients.values()}
    for item in PRICES:
        ing = by_name.get(item["ingredient"])
        if ing is None:
            continue
        exists = (
            db.query(Price)
            .filter(Price.ingredient_id == ing.id, Price.status == item["status"])
            .one_or_none()
        )
        if exists is not None:
            continue
        db.add(
            Price(
                ingredient_id=ing.id,
                price=item["price"],
                unit=item["unit"],
                source=item["source"],
                source_type=PriceSourceType.SCRAPER if "Portal" in item["source"] else PriceSourceType.MANUAL,
                status=item["status"],
                recorded_date=(datetime.now() - timedelta(days=item["days_ago"])).date(),
            )
        )
    db.commit()


def seed_seasonal(db: Session, ingredients: dict[str, Ingredient]) -> None:
    by_name = {ing.name: ing for ing in ingredients.values()}
    for item in SEASONS:
        ing = by_name.get(item["ingredient"])
        if ing is None:
            continue
        months = list(_MONTHS.values()) if "Sepanjang tahun" in item["months"] else [_MONTHS[m] for m in item["months"] if m in _MONTHS]
        for month in months:
            exists = (
                db.query(SeasonalAvailability)
                .filter(SeasonalAvailability.ingredient_id == ing.id, SeasonalAvailability.month == month)
                .one_or_none()
            )
            if exists is None:
                db.add(SeasonalAvailability(ingredient_id=ing.id, month=month, status=item["status"]))
    db.commit()


def seed_local(db: Session, ingredients: dict[str, Ingredient], regions: dict[str, Region]) -> None:
    by_name = {ing.name: ing for ing in ingredients.values()}
    for item in LOCAL_COMMODITIES:
        ing = by_name.get(item["ingredient"])
        region = regions.get(item["region"])
        if ing is None or region is None:
            continue
        exists = (
            db.query(LocalAvailability)
            .filter(LocalAvailability.ingredient_id == ing.id, LocalAvailability.region_id == region.id)
            .one_or_none()
        )
        if exists is None:
            db.add(LocalAvailability(ingredient_id=ing.id, region_id=region.id, level=item["level"]))
    db.commit()


def seed_system_config(db: Session) -> None:
    for key, value in SYSTEM_CONFIG:
        exists = db.query(SystemConfig).filter(SystemConfig.config_key == key).one_or_none()
        if exists is None:
            db.add(SystemConfig(config_key=key, config_value=value))
    db.commit()


def seed_food_safety(db: Session) -> None:
    for item in FOOD_SAFETY:
        exists = db.query(FoodSafetyInfo).filter(FoodSafetyInfo.code == item["code"]).one_or_none()
        if exists is None:
            db.add(FoodSafetyInfo(**item))
    db.commit()


def seed_articles(db: Session) -> None:
    for item in ARTICLES:
        exists = db.query(Article).filter(Article.code == item["code"]).one_or_none()
        if exists is None:
            db.add(Article(**item))
    db.commit()


def seed_notifications(db: Session) -> None:
    for item in NOTIFICATIONS:
        exists = db.query(Notification).filter(Notification.code == item["code"]).one_or_none()
        if exists is not None:
            continue
        data = dict(item)
        created = _days_ago(data.pop("days_ago"))
        db.add(Notification(**data, created_at=created))
    db.commit()


def seed_scraper_runs(db: Session) -> None:
    if db.query(ScraperRun).count() > 0:
        return
    for item in SCRAPER_RUNS:
        when = _days_ago(item["days_ago"])
        db.add(
            ScraperRun(
                source=item["source"],
                started_at=when,
                finished_at=when,
                status=item["status"],
                items_count=item["items_count"],
                error_message=item["error_message"],
            )
        )
    db.commit()


def seed_catalog(db: Session) -> None:
    """Jalankan seluruh seed katalog (idempoten)."""
    regions = seed_regions(db)
    ingredients = seed_ingredients(db)
    seed_recipes(db, ingredients)
    seed_prices(db, ingredients)
    seed_seasonal(db, ingredients)
    seed_local(db, ingredients, regions)
    seed_system_config(db)
    seed_food_safety(db)
    seed_articles(db)
    seed_notifications(db)
    seed_scraper_runs(db)
    print("[seed] katalog (bahan, resep, harga, musim, lokal, konten) siap")
