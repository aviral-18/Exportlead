"""
TED Europa scraper — EU Tenders Electronic Daily.
Public API: https://ted.europa.eu/api/v3.0/
Searches for EU public procurement contracts related to decorative/craft items.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import AsyncGenerator

import structlog

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

TED_API = "https://ted.europa.eu/api/v3.0/notices/search"

CPV_CODES = [
    "39000000",  # furniture, furnishings, household appliances
    "39290000",  # miscellaneous furnishings
    "39295000",  # embroidery and haberdashery items
    "39500000",  # textile articles
    "44000000",  # construction structures and materials
    "44810000",  # paints
    "44820000",  # varnishes
    "44831000",  # art objects / collectibles
    "18000000",  # clothing, footwear, luggage
    "39830000",  # cleaning products
]

SEARCH_TERMS = [
    "brass decoration", "metal handicraft", "decorative brass",
    "brass artifact", "metal decor", "brass gifts",
    "brass ornament", "metal artwork",
]

EU_COUNTRY_CODES = [
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
]


class TEDEuropaScraper(BaseScraper):
    """
    EU public procurement database.
    Identifies EU government agencies buying decorative metal / craft items.
    """
    source_name = "ted_europa"
    requests_per_second = 1.0

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        if not settings.ted_europa_scrape_enabled:
            return

        date_from = (datetime.utcnow() - timedelta(days=730)).strftime("%Y%m%d")
        date_to = datetime.utcnow().strftime("%Y%m%d")

        for term in SEARCH_TERMS:
            async for r in self._search(term, date_from, date_to):
                yield r

    async def _search(
        self, term: str, date_from: str, date_to: str
    ) -> AsyncGenerator[RawRecord, None]:
        page = 1
        PAGE_SIZE = 100

        while True:
            payload = {
                "query": f'FT~"{term}"',
                "fields": [
                    "ND", "PD", "TD", "AA_NAME", "AA_COUNTRY", "AA_TYPE",
                    "OJ_URL", "VALUES", "CPV",
                ],
                "scope": 3,
                "paginationPage": page,
                "paginationSize": PAGE_SIZE,
                "dateFrom": date_from,
                "dateTo": date_to,
                "onlyLatestVersions": True,
            }
            try:
                resp = await self.post(TED_API, json=payload)
            except Exception as exc:
                log.error("ted_europa.error", term=term, error=str(exc))
                break

            notices = resp.get("results", [])
            if not notices:
                break

            for n in notices:
                authority = n.get("AA_NAME", [])
                if isinstance(authority, list):
                    authority = authority[0] if authority else ""
                if not authority:
                    continue

                country = n.get("AA_COUNTRY", [])
                country_code = country[0] if isinstance(country, list) and country else None

                values = n.get("VALUES", [])
                value = None
                if values:
                    try:
                        value = float(str(values[0]).replace(",", ""))
                    except (ValueError, TypeError):
                        pass

                yield RawRecord(
                    external_id=n.get("ND"),
                    data_source=self.source_name,
                    company_name=authority,
                    country_code=country_code,
                    product_categories=[term],
                    product_description=n.get("TD", [term])[0] if n.get("TD") else term,
                    buyer_type="government",
                    estimated_annual_volume_usd=value,
                    last_import_date=n.get("PD"),
                    confidence_score=0.85,
                    raw_data={
                        "notice_id": n.get("ND"),
                        "aa_type": n.get("AA_TYPE"),
                        "cpv": n.get("CPV"),
                        "url": n.get("OJ_URL"),
                    },
                )

            total = resp.get("total", {}).get("value", 0)
            if page * PAGE_SIZE >= total:
                break
            page += 1


# Import settings reference fix
from src.core.config import settings  # noqa: E402
