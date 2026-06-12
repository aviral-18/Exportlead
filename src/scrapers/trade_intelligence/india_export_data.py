"""
India Export Data scraper — https://www.indiantradeportal.in / https://www.zauba.com
Multiple providers of Indian Customs export shipment data.
Primary: indiantradeportal.in (DGFT / Ministry of Commerce data).
Secondary: zauba.com (public partial data).
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.core.config import settings
from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

ZAUBA_BASE = "https://www.zauba.com"
DGFT_API = "https://www.dgft.gov.in/CP/foreigntradestatistics"

# Moradabad exporters ship to these countries primarily
TOP_DESTINATIONS = [
    "USA", "United Kingdom", "Germany", "France", "Australia",
    "Canada", "Netherlands", "UAE", "Saudi Arabia", "Singapore",
    "Japan", "South Korea", "South Africa", "Brazil", "Mexico",
    "Italy", "Spain", "Belgium", "Switzerland", "Austria",
]

BRASS_SEARCH_TERMS = [
    "brass handicraft",
    "brass decor",
    "brass statue",
    "brass fitting",
    "metal craft moradabad",
]


class IndiaExportDataScraper(BaseScraper):
    """
    Scrapes Indian export data to identify foreign importers of Indian brass goods.
    Uses Zauba.com (public) for buyer identification.
    Can also use a paid API provider (INDIA_EXPORT_DATA_API_KEY).
    """
    source_name = "india_export_data"
    requires_browser = True
    requests_per_second = 1.0

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        if settings.india_export_data_api_key:
            async for r in self._scrape_api():
                yield r
        else:
            async for r in self._scrape_zauba():
                yield r

    async def _scrape_api(self) -> AsyncGenerator[RawRecord, None]:
        """Paid API endpoint for Indian customs data."""
        for term in BRASS_SEARCH_TERMS:
            page = 1
            while True:
                try:
                    resp = await self.get(
                        "https://api.indiantradedata.com/v1/export",
                        params={
                            "product": term,
                            "origin": "Moradabad",
                            "page": page,
                            "per_page": 200,
                        },
                        headers={"X-API-Key": settings.india_export_data_api_key},
                    )
                except Exception as exc:
                    log.error("india_export.api_error", term=term, error=str(exc))
                    break

                records = resp.get("shipments", [])
                if not records:
                    break

                for r in records:
                    buyer = r.get("foreign_buyer", "").strip()
                    if not buyer:
                        continue
                    yield RawRecord(
                        external_id=r.get("shipment_id"),
                        data_source=self.source_name,
                        company_name=buyer,
                        country_name=r.get("destination_country"),
                        city=r.get("buyer_city"),
                        address=r.get("buyer_address"),
                        hs_codes=[r.get("hs_code", "")],
                        product_description=r.get("product_description"),
                        buyer_type="importer",
                        estimated_annual_volume_usd=self._safe_float(r.get("fob_value_usd")),
                        last_import_date=r.get("shipment_date"),
                        confidence_score=0.83,
                        raw_data=r,
                    )

                total = resp.get("total", 0)
                if page * 200 >= total:
                    break
                page += 1

    async def _scrape_zauba(self) -> AsyncGenerator[RawRecord, None]:
        """Scrape Zauba.com public export data."""
        for term in BRASS_SEARCH_TERMS[:2]:  # rate-limited
            url = f"{ZAUBA_BASE}/export-search.html"
            try:
                html = await self.browse(
                    f"{url}?q={term.replace(' ', '+')}&country=",
                    wait_for_selector=".table-hover",
                )
            except Exception as exc:
                log.error("zauba.error", term=term, error=str(exc))
                continue

            soup = BeautifulSoup(html, "html.parser")
            for row in soup.select("table.table-hover tbody tr"):
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue
                buyer = cells[2].get_text(strip=True)
                country = cells[3].get_text(strip=True)
                if not buyer:
                    continue
                yield RawRecord(
                    external_id=None,
                    data_source=self.source_name,
                    company_name=buyer,
                    country_name=country,
                    hs_codes=[cells[0].get_text(strip=True)[:6]],
                    product_description=cells[1].get_text(strip=True),
                    buyer_type="importer",
                    confidence_score=0.65,
                    raw_data={"term": term, "country": country},
                )
