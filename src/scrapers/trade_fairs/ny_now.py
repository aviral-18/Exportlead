"""
NY NOW (New York) scraper — major US gift and home decor trade show.
https://www.nynow.com
Key buyer source: US specialty retailers, boutiques, department store buyers.
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

NYNOW_BASE = "https://www.nynow.com"

CATEGORIES = [
    "home-decor",
    "gift",
    "lifestyle",
    "handmade",
    "green",
]


class NYNowScraper(BaseScraper):
    source_name = "ny_now"
    requires_browser = True
    requests_per_second = 0.8

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for cat in CATEGORIES:
            async for r in self._scrape_exhibitors(cat):
                yield r

    async def _scrape_exhibitors(self, category: str) -> AsyncGenerator[RawRecord, None]:
        url = f"{NYNOW_BASE}/exhibitors/?category={category}"
        try:
            html = await self.browse(url, wait_for_selector=".exhibitor-list, .results-grid")
        except Exception as exc:
            log.error("ny_now.error", cat=category, error=str(exc))
            return

        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select(".exhibitor-card, .result-item, [class*='exhibitor']"):
            name_el = card.select_one("h3, h4, .name, .company-name")
            state_el = card.select_one(".state, .location")
            website_el = card.select_one("a[href*='http']:not([href*='nynow'])")
            product_el = card.select_one(".products, .description, .categories")

            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name:
                continue

            yield RawRecord(
                external_id=None,
                data_source=self.source_name,
                company_name=name,
                country_code="US",
                country_name="United States",
                state_province=state_el.get_text(strip=True) if state_el else None,
                website=website_el["href"] if website_el else None,
                product_categories=[
                    category.replace("-", " "),
                    product_el.get_text(strip=True)[:100] if product_el else "",
                ],
                buyer_type="retailer",
                confidence_score=0.70,
                raw_data={"fair": "ny_now", "category": category},
            )

        # NY NOW also has a buyer directory
        async for r in self._scrape_buyer_directory():
            yield r

    async def _scrape_buyer_directory(self) -> AsyncGenerator[RawRecord, None]:
        url = f"{NYNOW_BASE}/buyers/directory/"
        try:
            html = await self.browse(url)
        except Exception as exc:
            log.error("ny_now.buyer_dir_error", error=str(exc))
            return

        soup = BeautifulSoup(html, "html.parser")
        for item in soup.select(".buyer-item, .directory-item"):
            name_el = item.select_one(".company, h3, .name")
            country_el = item.select_one(".country, .region")
            type_el = item.select_one(".buyer-type, .type")

            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name:
                continue

            yield RawRecord(
                external_id=None,
                data_source=self.source_name,
                company_name=name,
                country_code="US",
                country_name=country_el.get_text(strip=True) if country_el else "United States",
                product_categories=["gift", "home decor"],
                buyer_type=self._map_type(type_el.get_text(strip=True) if type_el else ""),
                confidence_score=0.73,
                raw_data={"fair": "ny_now", "type": "buyer_directory"},
            )

    @staticmethod
    def _map_type(text: str) -> str:
        t = text.lower()
        if "department" in t:
            return "retailer"
        if "wholesale" in t:
            return "distributor"
        if "boutique" in t or "specialty" in t:
            return "retailer"
        if "museum" in t or "gift shop" in t:
            return "retailer"
        return "retailer"
