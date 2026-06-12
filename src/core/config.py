from __future__ import annotations

from typing import Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://brass:brass_secure_pwd@localhost:5432/brass_export"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 40
    database_pool_timeout: int = 30
    database_echo: bool = False

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Trade Intelligence APIs (commercial) ─────────────────────────────────
    volza_api_key: Optional[str] = None
    volza_username: Optional[str] = None
    volza_password: Optional[str] = None
    volza_api_url: str = "https://api.volza.com/v1"

    import_yeti_api_key: Optional[str] = None
    import_yeti_session_cookie: Optional[str] = None

    export_genius_api_key: Optional[str] = None
    export_genius_username: Optional[str] = None
    export_genius_password: Optional[str] = None

    datamyne_username: Optional[str] = None
    datamyne_password: Optional[str] = None

    panjiva_api_key: Optional[str] = None
    panjiva_username: Optional[str] = None
    panjiva_password: Optional[str] = None

    india_export_data_api_key: Optional[str] = None

    # ── Public APIs ───────────────────────────────────────────────────────────
    un_comtrade_api_key: Optional[str] = None
    trade_map_username: Optional[str] = None
    trade_map_password: Optional[str] = None

    sam_gov_api_key: Optional[str] = None
    world_bank_api_base: str = (
        "https://search.worldbank.org/api/v2/procurementnotices"
    )
    adb_api_base: str = "https://www.adb.org/projects/search"
    ungm_scrape_enabled: bool = True
    ted_europa_scrape_enabled: bool = True

    # ── Proxy ─────────────────────────────────────────────────────────────────
    proxy_url: Optional[str] = None
    proxy_rotation_enabled: bool = False
    proxy_list_file: Optional[str] = None
    brightdata_scraping_browser_url: Optional[str] = None

    # ── Rate limiting ─────────────────────────────────────────────────────────
    requests_per_second: float = 2.0
    requests_per_day: int = 10000

    # ── Pipeline ──────────────────────────────────────────────────────────────
    batch_size: int = 1000
    dedup_threshold: float = 0.85
    entity_resolution_workers: int = 8
    headless: bool = True

    # ── Auth / Security ───────────────────────────────────────────────────────
    secret_key: str = "change_me_in_production_use_openssl_rand_hex_32"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    environment: str = "development"

    # ── OAuth — Google ────────────────────────────────────────────────────────
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # ── AWS S3 ────────────────────────────────────────────────────────────────
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_s3_bucket: Optional[str] = None
    aws_s3_region: str = "ap-south-1"

    # ── Elasticsearch ─────────────────────────────────────────────────────────
    elasticsearch_url: str = "http://localhost:9200"

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # ── Brass product HS codes ────────────────────────────────────────────────
    brass_hs_codes: list[str] = [
        "7418",  # table/kitchen/sanitary ware — copper alloys
        "7419",  # other articles of copper
        "8306",  # bells, statuettes, ornaments — base metal
        "6913",  # decorative ceramic articles
        "9405",  # lamps and lighting
        "9403",  # furniture (hotel/hospitality)
        "6304",  # furnishing articles (curtain rings etc.)
        "8301",  # padlocks, locks, clasps
        "8302",  # fittings, handles, brackets
        "6912",  # tableware, ceramic
    ]

    # ── Search keywords for product matching ─────────────────────────────────
    brass_keywords: list[str] = [
        "brass decor",
        "brass handicraft",
        "brass statue",
        "brass figurine",
        "brass gift",
        "brass giftware",
        "brass hotelware",
        "brass garden",
        "brass religious",
        "brass artifact",
        "brass OEM",
        "metal handicraft",
        "metal decor",
        "brass lamp",
        "brass candleholder",
        "brass vase",
        "brass planter",
        "brass idol",
        "moradabad brass",
        "indian brass",
    ]

    @field_validator("database_url")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("Only PostgreSQL is supported")
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        _default_key = "change_me_in_production_use_openssl_rand_hex_32"
        if self.environment == "production" and self.secret_key == _default_key:
            raise ValueError(
                "SECRET_KEY must be changed before deploying to production. "
                "Generate one with: openssl rand -hex 32"
            )
        return self


settings = Settings()
