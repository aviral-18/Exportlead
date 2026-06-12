"""
TradeIndia.com buyer scraper — https://www.tradeindia.com
Indian B2B marketplace; has a buyers / importers section.
"""
from __future__ import annotations

import re
from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

TI_BASE = "https://www.tradeindia.com"
CATEGORIES = [
    "brass-handicrafts",
    "brass-statues",
    "brass-decor",
    "metal-handicrafts",
    "brass-gifts",
    "brass-hotelware",
    "brass-garden-decoratives",
    "religious-brass-items",
]


class TradeIndiaScraper(BaseScraper):
    source_name = "tradeindia"
    requires_browser = False
    requests_per_second = 1.5

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for cat in CATEGORIES:
            async for r in self._scrape_buyers(cat):
                yield r

    async def _scrape_buyers(self, category: str) -> AsyncGenerator[RawRecord, None]:
        page = 1
        while page <= 15:
            url = f"{TI_BASE}/Buyers/{category}/{page}/"
            try:
                html = await self.get(url, json_response=False)
            except Exception as exc:
                log.error("tradeindia.error", cat=category, error=str(exc))
                break

            soup = BeautifulSoup(html, "html.parser")
            buyers = soup.select(".buyer-listing .buyer-detail, .buyer-box")
            if not buyers:
                break

            for buyer in buyers:
                name_el = buyer.select_one("h3 a, .company-name a, .buyer-name")
                country_el = buyer.select_one(".country, .location-flag, [class*='country']")
                qty_el = buyer.select_one(".quantity-required, .qty")
                product_el = buyer.select_one(".product-name, .looking-for")
                contact_el = buyer.select_one(".contact-person, .person-name")

                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not name:
                    continue

                link = name_el.get("href", "")
                ext_id = re.search(r"/(\d+)/", link)

                yield RawRecord(
                    external_id=ext_id.group(1) if ext_id else None,
                    data_source=self.source_name,
                    company_name=name,
                    country_name=country_el.get_text(strip=True) if country_el else None,
                    contact_person=contact_el.get_text(strip=True) if contact_el else None,
                    product_categories=[category.replace("-", " ")],
                    product_description=product_el.get_text(strip=True) if product_el else None,
                    buyer_type="importer",
                    confidence_score=0.65,
                    raw_data={
                        "category": category,
                        "page": page,
                        "qty": qty_el.get_text(strip=True) if qty_el else None,
                    },
                )
            page += 1
