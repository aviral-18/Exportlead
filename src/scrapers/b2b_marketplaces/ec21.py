"""EC21.com buyer scraper — https://www.ec21.com — Korean B2B marketplace."""
from __future__ import annotations

from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

EC21_BASE = "https://www.ec21.com"
TERMS = [
    "brass decor", "brass handicraft", "brass statues",
    "metal home decor", "brass gift items",
]


class EC21Scraper(BaseScraper):
    source_name = "ec21"
    requires_browser = False
    requests_per_second = 1.2

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for term in TERMS:
            page = 1
            while page <= 10:
                url = (
                    f"{EC21_BASE}/buy-offers/brass-handicraft/"
                    f"?keyword={term.replace(' ', '+')}&page={page}"
                )
                try:
                    html = await self.get(url, json_response=False)
                except Exception as exc:
                    log.error("ec21.error", term=term, error=str(exc))
                    break

                soup = BeautifulSoup(html, "html.parser")
                items = soup.select(".bo-list li, .buy-offer-item")
                if not items:
                    break

                for item in items:
                    name_el = item.select_one(".company-name, h3 a, .company a")
                    country_el = item.select_one(".country, .flag, [class*='country']")
                    product_el = item.select_one(".product-name, h4, .title")

                    if not name_el:
                        continue
                    name = name_el.get_text(strip=True)
                    if not name:
                        continue

                    link = name_el.get("href", "")
                    yield RawRecord(
                        external_id=link.split("/")[-1] if link else None,
                        data_source=self.source_name,
                        company_name=name,
                        country_name=country_el.get_text(strip=True) if country_el else None,
                        website=f"{EC21_BASE}{link}" if link.startswith("/") else link,
                        product_categories=[term],
                        product_description=product_el.get_text(strip=True) if product_el else None,
                        buyer_type="importer",
                        confidence_score=0.55,
                        raw_data={"term": term, "page": page},
                    )
                page += 1
