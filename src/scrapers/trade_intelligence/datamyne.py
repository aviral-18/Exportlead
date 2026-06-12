"""
Datamyne scraper — commercial subscription (now part of S&P Global).
Provides US, Latin American, and other customs import/export records.
"""
from __future__ import annotations

import hashlib
from typing import AsyncGenerator

import structlog

from src.core.config import settings
from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

DATAMYNE_API = "https://api.datamyne.com/v3"
BRASS_KEYWORDS = settings.brass_keywords[:8]


class DatamyneScraper(BaseScraper):
    """
    Datamyne API (username/password OAuth2).
    Focuses on US Customs Bill of Lading data and Latin American markets.
    """
    source_name = "datamyne"
    requests_per_second = 0.8
    PAGE_SIZE = 100

    def __init__(self) -> None:
        super().__init__()
        self._token: str | None = None

    async def _authenticate(self) -> str | None:
        if self._token:
            return self._token
        if not settings.datamyne_username:
            return None
        resp = await self.post(
            f"{DATAMYNE_API}/oauth/token",
            data={
                "grant_type": "password",
                "username": settings.datamyne_username,
                "password": settings.datamyne_password,
            },
        )
        self._token = resp.get("access_token")
        return self._token

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        token = await self._authenticate()
        if not token:
            log.warning("datamyne.no_credentials")
            return

        for keyword in BRASS_KEYWORDS:
            async for record in self._search_importers(token, keyword):
                yield record

    async def _search_importers(
        self, token: str, keyword: str
    ) -> AsyncGenerator[RawRecord, None]:
        page = 0
        seen: set[str] = set()

        while True:
            try:
                resp = await self.get(
                    f"{DATAMYNE_API}/importers/search",
                    params={
                        "q": keyword,
                        "country": "US",
                        "origin": "IN",
                        "page": page,
                        "size": self.PAGE_SIZE,
                        "sort": "lastShipmentDate,desc",
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
            except Exception as exc:
                log.error("datamyne.error", keyword=keyword, error=str(exc))
                break

            content = resp.get("content", [])
            if not content:
                break

            for item in content:
                name = (item.get("importerName") or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)

                yield RawRecord(
                    external_id=item.get("importerId"),
                    data_source=self.source_name,
                    company_name=name,
                    country_code="US",
                    country_name="United States",
                    city=item.get("city"),
                    state_province=item.get("state"),
                    address=item.get("address"),
                    hs_codes=item.get("hsCodes", []),
                    product_categories=[keyword],
                    buyer_type="importer",
                    total_shipments=self._safe_int(item.get("totalShipments")),
                    estimated_annual_volume_usd=self._safe_float(item.get("totalValueUsd")),
                    last_import_date=item.get("lastShipmentDate"),
                    first_import_date=item.get("firstShipmentDate"),
                    confidence_score=0.87,
                    raw_data=item,
                )

            total_pages = resp.get("totalPages", 1)
            page += 1
            if page >= total_pages:
                break
