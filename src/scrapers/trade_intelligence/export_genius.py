"""
Export Genius scraper — commercial subscription required.
Provides shipment-level import/export data for 70+ countries.
API: https://www.exportgenius.in/api
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog

from src.core.config import settings
from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

EXPORT_GENIUS_API = "https://www.exportgenius.in/api/v2"
BRASS_HS = settings.brass_hs_codes

IMPORTER_COUNTRIES = [
    "USA", "UK", "Germany", "France", "Australia", "Canada",
    "Netherlands", "UAE", "Saudi Arabia", "Singapore", "Japan",
    "South Korea", "South Africa", "Brazil", "Mexico", "Poland",
]


class ExportGeniusScraper(BaseScraper):
    """
    Export Genius REST API.
    Requires EXPORT_GENIUS_API_KEY or username/password.
    """
    source_name = "export_genius"
    requests_per_second = 1.0
    PAGE_SIZE = 200

    def __init__(self) -> None:
        super().__init__()
        self._token: str | None = None

    async def _authenticate(self) -> str | None:
        if self._token:
            return self._token
        if settings.export_genius_api_key:
            self._token = settings.export_genius_api_key
            return self._token
        if settings.export_genius_username and settings.export_genius_password:
            resp = await self.post(
                f"{EXPORT_GENIUS_API}/auth/token",
                json={
                    "username": settings.export_genius_username,
                    "password": settings.export_genius_password,
                },
            )
            self._token = resp.get("access_token")
        return self._token

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        token = await self._authenticate()
        if not token:
            log.warning("export_genius.no_credentials")
            return

        for hs in BRASS_HS:
            for country in IMPORTER_COUNTRIES:
                async for r in self._query(token, hs, country):
                    yield r

    async def _query(
        self, token: str, hs: str, country: str
    ) -> AsyncGenerator[RawRecord, None]:
        page = 1
        while True:
            try:
                resp = await self.get(
                    f"{EXPORT_GENIUS_API}/importers",
                    params={
                        "hs_code": hs,
                        "country": country,
                        "exporter_country": "India",
                        "page": page,
                        "limit": self.PAGE_SIZE,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
            except Exception as exc:
                log.error("export_genius.error", hs=hs, country=country, error=str(exc))
                break

            records = resp.get("data", [])
            if not records:
                break

            for r in records:
                name = (r.get("importer_name") or "").strip()
                if not name:
                    continue
                yield RawRecord(
                    external_id=r.get("importer_id"),
                    data_source=self.source_name,
                    company_name=name,
                    country_name=country,
                    city=r.get("city"),
                    address=r.get("address"),
                    website=r.get("website"),
                    phone=[r["phone"]] if r.get("phone") else [],
                    email=[r["email"]] if r.get("email") else [],
                    hs_codes=[hs],
                    product_description=r.get("product_description"),
                    buyer_type="importer",
                    estimated_annual_volume_usd=self._safe_float(r.get("total_value_usd")),
                    last_import_date=r.get("last_shipment_date"),
                    total_shipments=self._safe_int(r.get("shipment_count")),
                    confidence_score=0.85,
                    raw_data=r,
                )

            if page * self.PAGE_SIZE >= resp.get("total", 0):
                break
            page += 1
