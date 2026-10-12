"""Konfigurasi backend (environment + default pengembangan)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NutriVillage AI API"
    api_prefix: str = "/api/v1"

    # MySQL/MariaDB XAMPP: root tanpa password, database nutri_village_ai.
    database_url: str = (
        "mysql+pymysql://root:@127.0.0.1:3306/nutri_village_ai?charset=utf8mb4"
    )

    # HARUS sama dengan JWT_SECRET pada frontend Next.js (web-next/.env.local)
    # agar token yang ditandatangani backend bisa diverifikasi middleware/Route Handler.
    jwt_secret: str = "nutrivillage-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Lingkungan & produksi ---------------------------------------------
    # "development" (default) atau "production".
    environment: str = "development"

    # TLS database (mis. TiDB Cloud). Isi DATABASE_SSL_CA dengan ISI file CA
    # (PEM) atau path ke file .pem. Kosongkan untuk MySQL lokal.
    database_ssl_ca: str = ""
    # False = enkripsi tanpa verifikasi sertifikat (kurang aman, untuk uji saja).
    database_ssl_verify: bool = True

    # Di DB terkelola (TiDB/Aiven) database sudah dibuat provider -> lewati
    # `CREATE DATABASE`. Set "1"/"true" di produksi.
    skip_create_database: bool = False

    # Seed akun demo publik. WAJIB false di produksi (default true untuk dev).
    seed_demo_accounts: bool = True

    # Akun admin awal (dipakai saat produksi). Dibuat hanya jika belum ada.
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_admin_name: str = "Administrator"

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def validate_production(self) -> None:
        """Gagal cepat bila konfigurasi produksi belum aman."""
        if not self.is_production:
            return
        problems: list[str] = []
        if self.jwt_secret.strip() in {"", "nutrivillage-dev-secret-change-me"}:
            problems.append(
                "JWT_SECRET masih default/kosong. Set nilai rahasia acak yang kuat."
            )
        if "root:@127.0.0.1" in self.database_url or "@localhost" in self.database_url:
            problems.append(
                "DATABASE_URL masih menunjuk ke MySQL lokal. Gunakan URL database produksi."
            )
        if not self.database_ssl_ca and self.database_url.startswith("mysql+"):
            problems.append(
                "DATABASE_SSL_CA belum diisi (TiDB/DB terkelola biasanya wajib TLS)."
            )
        if self.seed_demo_accounts:
            problems.append(
                "SEED_DEMO_ACCOUNTS masih aktif. Matikan agar akun demo publik tidak dibuat."
            )
        if problems:
            raise RuntimeError(
                "Konfigurasi produksi belum aman:\n - " + "\n - ".join(problems)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
