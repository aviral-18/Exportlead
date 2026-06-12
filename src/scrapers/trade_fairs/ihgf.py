"""
IHGF Delhi Fair scraper — India's largest handicraft export fair.
https://www.ihgf-delhi-fair.com
Organised by EPCH (Export Promotion Council for Handicrafts).
This is the primary sourcing event for Moradabad brass exporters.
We scrape buyer registrations and exhibitor lists.
"""
from __future__ import annotations

import re
from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

IHGF_BASE = "https://www.ihgf-delhi-fair.com"
EPCH_BASE = "https://www.epch.in"

BUYER_CATEGORIES = [
    "brass-metal-crafts",
    "home-decor",
    "gifts-novelties",
    "hotel-hospitality",
    "religious-products",
]


class IHGFFairScraper(BaseScraper):
    """
    IHGF Fair is the most direct source of brass buyer contacts.
    Scrapes:
    1. Registered overseas buyer list (public portion)
    2. Exhibitor directory (Indian suppliers whose buyer contacts we can infer)
    3. EPCH buyer meet records
    """
    source_name = "ihgf"
    requires_browser = True
    requests_per_second = 0.8

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        async for r in self._scrape_buyer_list():
            yield r
        async for r in self._scrape_epch_buyers():
            yield r

    async def _scrape_buyer_list(self) -> AsyncGenerator[RawRecord, None]:
        url = f"{IHGF_BASE}/buyers/registered-buyers/"
        try:
            html = await self.browse(url, wait_for_selector=".buyer-list, table")
        except Exception as exc:
            log.error("ihgf.buyer_list_error", error=str(exc))
            return

        soup = BeautifulSoup(html, "html.parser")

        # Table format
        table = soup.find("table")
        if table:
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            for row in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if not cells:
                    continue
                data = dict(zip(headers, cells))

                name = data.get("company name", data.get("buyer name", cells[0] if cells else ""))
                if not name:
                    continue

                yield RawRecord(
                    external_id=None,
                    data_source=self.source_name,
                    company_name=name,
                    country_name=data.get("country", data.get("origin", "")),
                    product_categories=[data.get("product interest", "brass handicraft")],
                    buyer_type="importer",
                    confidence_score=0.82,
                    raw_data={"fair": "ihgf", "source": "buyer_list", **data},
                )

        # Card format
        for card in soup.select(".buyer-card, .buyer-item"):
            name_el = card.select_one(".company-name, h3, h4")
            country_el = card.select_one(".country, .origin")
            product_el = card.select_one(".product-interest, .products")

            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name:
                continue

            yield RawRecord(
                external_id=None,
                data_source=self.source_name,
                company_name=name,
                country_name=country_el.get_text(strip=True) if country_el else None,
                product_categories=[
                    product_el.get_text(strip=True) if product_el else "brass handicraft"
                ],
                buyer_type="importer",
                confidence_score=0.82,
                raw_data={"fair": "ihgf", "source": "buyer_card"},
            )

    async def _scrape_epch_buyers(self) -> AsyncGenerator[RawRecord, None]:
        """Scrape EPCH buyer database — the export council for handicrafts."""
        url = f"{EPCH_BASE}/overseas-buyers/"
        for cat in BUYER_CATEGORIES:
            cat_url = f"{url}?category={cat}"
            try:
                html = await self.browse(cat_url, wait_for_selector=".buyer-listing")
            except Exception as exc:
                log.error("epch.error", cat=cat, error=str(exc))
                continue

            soup = BeautifulSoup(html, "html.parser")
            for item in soup.select(".buyer-listing .item, .buyer-block"):
                name_el = item.select_one(".company, h3, .name")
                country_el = item.select_one(".country")
                website_el = item.select_one("a.website, a[target='_blank']")
                contact_el = item.select_one(".contact, .person")
                email_el = item.select_one("a[href^='mailto:']")
                phone_el = item.select_one(".phone, .tel")

                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not name:
                    continue

                email_href = email_el.get("href", "").replace("mailto:", "") if email_el else None

                yield RawRecord(
                    external_id=None,
                    data_source=self.source_name,
                    company_name=name,
                    country_name=country_el.get_text(strip=True) if country_el else None,
                    website=website_el["href"] if website_el else None,
                    email=[email_href] if email_href else [],
                    phone=[phone_el.get_text(strip=True)] if phone_el else [],
                    contact_person=contact_el.get_text(strip=True) if contact_el else None,
                    product_categories=[cat.replace("-", " ")],
                    buyer_type="importer",
                    confidence_score=0.85,
                    raw_data={"fair": "ihgf", "source": "epch", "category": cat},
                )
