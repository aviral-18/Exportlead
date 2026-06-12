"""
IndiaMART buyer scraper — https://www.indiamart.com
Focuses on the "Buy Leads" (buyer enquiries) for brass products.
"""
from __future__ import annotations

import re
from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

IM_BASE = "https://www.indiamart.com"
CATEGORIES = [
    "brass-handicrafts",
    "brass-statues-idols",
    "metal-wall-decor",
    "brass-gift-items",
    "brass-lamps",
    "brass-home-decor",
    "religious-brass-articles",
    "brass-garden-decor",
]


class IndiaMARTScraper(BaseScraper):
    source_name = "indiamart"
    requires_browser = True
    requests_per_second = 0.8

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for cat in CATEGORIES:
            async for r in self._scrape_buy_leads(cat):
                yield r

    async def _scrape_buy_leads(self, category: str) -> AsyncGenerator[RawRecord, None]:
        context = await self._new_context()
        try:
            page = await context.new_page()
            url = f"{IM_BASE}/buy-products/{category}/"
            await page.goto(url, wait_until="networkidle", timeout=45_000)

            for _ in range(10):
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")

                for lead in soup.select(".buy-lead-box, .lead-item, [class*='buy-lead']"):
                    name_el = lead.select_one(".company-name, .buyer-name, h3")
                    country_el = lead.select_one(".location, .country, [class*='loc']")
                    qty_el = lead.select_one(".qty-required, .quantity")
                    product_el = lead.select_one(".product-name, .looking-for, h4")
                    contact_el = lead.select_one(".person-name, .contact")

                    if not name_el:
                        continue
                    name = name_el.get_text(strip=True)
                    if not name:
                        continue

                    country_text = country_el.get_text(strip=True) if country_el else ""
                    # IndiaMART shows city/country mixed; try to parse country
                    country_code = self._extract_country_code(country_text)

                    yield RawRecord(
                        external_id=None,
                        data_source=self.source_name,
                        company_name=name,
                        country_name=country_text or None,
                        country_code=country_code,
                        contact_person=contact_el.get_text(strip=True) if contact_el else None,
                        product_categories=[category.replace("-", " ")],
                        product_description=product_el.get_text(strip=True) if product_el else None,
                        buyer_type="importer",
                        confidence_score=0.62,
                        raw_data={
                            "category": category,
                            "qty": qty_el.get_text(strip=True) if qty_el else None,
                        },
                    )

                next_btn = await page.query_selector("a.next, .pagination-next")
                if not next_btn:
                    break
                await next_btn.click()
                await page.wait_for_timeout(1500)
        except Exception as exc:
            log.error("indiamart.error", cat=category, error=str(exc))
        finally:
            await context.close()

    COUNTRY_MAP = {
        "USA": "US", "UNITED STATES": "US", "UK": "GB", "UNITED KINGDOM": "GB",
        "GERMANY": "DE", "FRANCE": "FR", "AUSTRALIA": "AU", "CANADA": "CA",
        "UAE": "AE", "SAUDI": "SA", "SINGAPORE": "SG", "JAPAN": "JP",
        "SOUTH KOREA": "KR", "SOUTH AFRICA": "ZA", "BRAZIL": "BR",
        "NETHERLANDS": "NL", "BELGIUM": "BE", "ITALY": "IT", "SPAIN": "ES",
    }

    def _extract_country_code(self, text: str) -> str | None:
        upper = text.upper()
        for name, code in self.COUNTRY_MAP.items():
            if name in upper:
                return code
        return None
