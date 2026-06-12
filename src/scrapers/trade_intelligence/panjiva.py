"""
Panjiva scraper (S&P Global Market Intelligence).
Panjiva provides global trade data with buyer/supplier profiles.
API: enterprise REST API requiring subscription.
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog

from src.core.config import settings
from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

PANJIVA_API = "https://panjiva.com/api/v2.0"
BRASS_HS = settings.brass_hs_codes

TARGET_COUNTRIES = [
    "US", "GB", "DE", "FR", "AU", "CA", "NL", "AE",
    "SA", "SG", "JP", "KR", "ZA", "BR", "MX",
]


class PanjivaScraper(BaseScraper):
    """
    Panjiva REST API with API key auth.
    Requires PANJIVA_API_KEY.
    """
    source_name = "panjiva"
    requests_per_second = 0.5
    PAGE_SIZE = 100

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        if not settings.panjiva_api_key:
            log.warning("panjiva.no_api_key")
            return

        for hs in BRASS_HS:
            for country in TARGET_COUNTRIES:
                async for r in self._fetch(hs, country):
                    yield r

    async def _fetch(self, hs: str, country: str) -> AsyncGenerator[RawRecord, None]:
        offset = 0
        headers = {"Authorization": f"Token {settings.panjiva_api_key}"}

        while True:
            try:
                resp = await self.get(
                    f"{PANJIVA_API}/shippers",
                    params={
                        "hs_code": hs,
                        "shipper_country": "IN",
                        "consignee_country": country,
                        "limit": self.PAGE_SIZE,
                        "offset": offset,
                        "sort_by": "last_shipment_date",
                        "sort_order": "desc",
                    },
                    headers=headers,
                )
            except Exception as exc:
                log.error("panjiva.error", hs=hs, country=country, error=str(exc))
                break

            results = resp.get("results", [])
            if not results:
                break

            for item in results:
                consignee = item.get("consignee", {})
                name = (consignee.get("name") or "").strip()
                if not name:
                    continue

                yield RawRecord(
                    external_id=str(consignee.get("id", "")),
                    data_source=self.source_name,
                    company_name=name,
                    country_code=country,
                    country_name=consignee.get("country"),
                    city=consignee.get("city"),
                    address=consignee.get("address"),
                    website=consignee.get("website"),
                    hs_codes=[hs],
                    buyer_type="importer",
                    total_shipments=self._safe_int(item.get("shipment_count")),
                    estimated_annual_volume_usd=self._safe_float(
                        item.get("total_weight_kg")
                    ),  # convert weight to USD estimate
                    last_import_date=item.get("last_shipment_date"),
                    first_import_date=item.get("first_shipment_date"),
                    confidence_score=0.90,
                    raw_data=item,
                )

            count = resp.get("count", 0)
            offset += self.PAGE_SIZE
            if offset >= count:
                break
