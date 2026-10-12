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

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
