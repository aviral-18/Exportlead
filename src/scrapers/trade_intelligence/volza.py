"""
Volza.com scraper — commercial subscription required.
Volza provides shipment-level import/export data with buyer and supplier details.
API docs: https://api.volza.com (requires API key from subscription).
"""
from __future__ import annotations

import hashlib
from typing import AsyncGenerator

import structlog

from src.core.config import settings
from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

# Brass-relevant HS chapters/headings
BRASS_HS_CODES = settings.brass_hs_codes

# Volza country codes for top brass-importing markets
TARGET_COUNTRIES = [
    "US", "GB", "DE", "FR", "AU", "CA", "NL", "BE", "IT", "ES",
    "AE", "SA", "KW", "QA", "SG", "MY", "JP", "KR", "ZA", "NG",
    "BR", "MX", "AR", "PL", "SE", "DK", "NO", "FI", "CH", "AT",
]


class VolzaScraper(BaseScraper):
    """
    Queries the Volza REST API for import shipments of brass products.
    Requires VOLZA_API_KEY in environment.

    The Volza API returns paginated shipment records including:
      - importer_name, importer_country, importer_address
      - hs_code, product_description
      - shipment_date, shipment_value_usd, shipment_weight_kg
    """
    source_name = "volza"
    requests_per_second = 1.0
    PAGE_SIZE = 500

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        if not settings.volza_api_key:
            log.warning("volza.no_api_key", msg="Set VOLZA_API_KEY to enable")
            return

        for hs_code in BRASS_HS_CODES:
            for country in TARGET_COUNTRIES:
                async for record in self._scrape_hs_country(hs_code, country):
                    yield record

    async def _scrape_hs_country(
        self, hs_code: str, importer_country: str
    ) -> AsyncGenerator[RawRecord, None]:
        page = 1
        seen_importers: set[str] = set()

        while True:
            try:
                resp = await self.get(
                    f"{settings.volza_api_url}/import-shipments",
                    params={
                        "hs_code": hs_code,
                        "importer_country": importer_country,
                        "page": page,
                        "page_size": self.PAGE_SIZE,
                        "sort": "shipment_date:desc",
                    },
                    headers={
                        "X-API-Key": settings.volza_api_key,
                        "Accept": "application/json",
                    },
                )
            except Exception as exc:
                log.error("volza.fetch_error", hs=hs_code, country=importer_country, error=str(exc))
                break

            shipments = resp.get("data", [])
            if not shipments:
                break

            for s in shipments:
                importer_name = s.get("importer_name", "").strip()
                if not importer_name:
                    continue

                # Deduplicate importers within this batch
                key = hashlib.md5(
                    f"{importer_name}|{importer_country}".lower().encode()
                ).hexdigest()
                if key in seen_importers:
                    continue
                seen_importers.add(key)

                yield RawRecord(
                    external_id=s.get("importer_id") or key,
                    data_source=self.source_name,
                    company_name=importer_name,
                    country_code=importer_country,
                    country_name=s.get("importer_country_name"),
                    city=s.get("importer_city"),
                    address=s.get("importer_address"),
                    website=s.get("importer_website"),
                    phone=[s["importer_phone"]] if s.get("importer_phone") else [],
                    hs_codes=[hs_code],
                    product_description=s.get("product_description"),
                    buyer_type="importer",
                    import_frequency=self._estimate_frequency(s),
                    estimated_annual_volume_usd=self._safe_float(
                        s.get("annual_value_usd")
                    ),
                    last_import_date=s.get("latest_shipment_date"),
                    first_import_date=s.get("earliest_shipment_date"),
                    total_shipments=self._safe_int(s.get("total_shipments")),
                    total_suppliers=self._safe_int(s.get("total_suppliers")),
                    confidence_score=0.88,
                    raw_data=s,
                )

            total = resp.get("total", 0)
            if page * self.PAGE_SIZE >= total:
                break
            page += 1

    @staticmethod
    def _estimate_frequency(shipment: dict) -> str:
        total = int(shipment.get("total_shipments", 0))
        if total >= 50:
            return "monthly"
        if total >= 12:
            return "quarterly"
        if total >= 4:
            return "annual"
        return "sporadic"
