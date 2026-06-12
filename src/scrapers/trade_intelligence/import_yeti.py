"""
ImportYeti.com scraper.
ImportYeti provides US Customs import records (Bill of Lading data).
Uses their search API with session authentication.
"""
from __future__ import annotations

import hashlib
from typing import AsyncGenerator

import structlog

from src.core.config import settings
from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

IMPORTYETI_BASE = "https://www.importyeti.com"
SEARCH_KEYWORDS = [
    "brass decor", "brass handicraft", "brass statue",
    "brass figurine", "brass giftware", "brass hotelware",
    "brass lamp", "brass candleholder", "moradabad brass",
    "metal handicraft india", "brass garden decor",
]


class ImportYetiScraper(BaseScraper):
    """
    ImportYeti has a public search on their website.
    Authentication via session cookie (IMPORT_YETI_SESSION_COOKIE).
    Falls back to public unauthenticated search with limited results.
    """
    source_name = "import_yeti"
    requires_browser = False
    requests_per_second = 1.5

    def __init__(self) -> None:
        super().__init__()
        self._cookie = settings.import_yeti_session_cookie

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for keyword in SEARCH_KEYWORDS:
            async for record in self._search(keyword):
                yield record

    async def _search(self, keyword: str) -> AsyncGenerator[RawRecord, None]:
        page = 1
        while True:
            try:
                headers = {}
                if self._cookie:
                    headers["Cookie"] = self._cookie

                resp = await self.get(
                    f"{IMPORTYETI_BASE}/api/search",
                    params={
                        "q": keyword,
                        "page": page,
                        "type": "company",
                    },
                    headers=headers,
                )
            except Exception as exc:
                log.error("import_yeti.error", keyword=keyword, error=str(exc))
                break

            companies = resp.get("results", [])
            if not companies:
                break

            for c in companies:
                name = c.get("name", "").strip()
                if not name:
                    continue

                consignees = c.get("consignees", [c])
                for company in consignees:
                    cname = company.get("name") or name
                    country = company.get("country_code", "US")
                    ext_id = hashlib.md5(
                        f"{cname}|{country}".lower().encode()
                    ).hexdigest()

                    yield RawRecord(
                        external_id=company.get("id") or ext_id,
                        data_source=self.source_name,
                        company_name=cname,
                        country_code=country,
                        country_name=company.get("country"),
                        city=company.get("city"),
                        address=company.get("address"),
                        website=company.get("website"),
                        hs_codes=company.get("hs_codes", []),
                        product_categories=[keyword],
                        buyer_type="importer",
                        total_shipments=self._safe_int(company.get("shipment_count")),
                        last_import_date=company.get("latest_date"),
                        first_import_date=company.get("earliest_date"),
                        confidence_score=0.82,
                        raw_data=company,
                    )

            total_pages = resp.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
