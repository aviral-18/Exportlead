"""
Maison & Objet (Paris) scraper — premier design fair for home decor buyers.
https://www.maison-objet.com
Key buyer segments: interior design buyers, hotel procurement, luxury retail.
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

MO_BASE = "https://www.maison-objet.com"

SECTORS = [
    "home-accessories",
    "decoration",
    "gift",
    "interior-design",
    "fragrances",
]


class MaisonObjetScraper(BaseScraper):
    source_name = "maison_objet"
    requires_browser = True
    requests_per_second = 0.6

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for sector in SECTORS:
            async for r in self._scrape_exhibitors(sector):
                yield r

    async def _scrape_exhibitors(self, sector: str) -> AsyncGenerator[RawRecord, None]:
        context = await self._new_context()
        try:
            page = await context.new_page()
            url = f"{MO_BASE}/en/exhibitors/?sector={sector}&page=1"
            await page.goto(url, wait_until="networkidle", timeout=45_000)

            pg = 1
            while pg <= 20:
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")

                for card in soup.select(".exhibitor-card, .company-card, [class*='exhibitor']"):
                    name_el = card.select_one("h3, .company-name, .name")
                    country_el = card.select_one(".country, .location, [class*='country']")
                    link_el = card.select_one("a[href*='/exhibitor/']")
                    type_el = card.select_one(".company-type, .type")

                    if not name_el:
                        continue
                    name = name_el.get_text(strip=True)
                    if not name:
                        continue

                    country = country_el.get_text(strip=True) if country_el else None
                    # M&O has strong presence of French/European luxury buyers
                    if country and country.lower() in ("france", "fr"):
                        country_code = "FR"
                    else:
                        country_code = None

                    yield RawRecord(
                        external_id=(
                            link_el["href"].split("/")[-1] if link_el else None
                        ),
                        data_source=self.source_name,
                        company_name=name,
                        country_name=country,
                        country_code=country_code,
                        product_categories=[sector.replace("-", " "), "home decor"],
                        buyer_type=self._infer_type(type_el.get_text(strip=True) if type_el else ""),
                        confidence_score=0.75,
                        raw_data={"fair": "maison_objet", "sector": sector, "page": pg},
                    )

                next_btn = await page.query_selector("a.next, .pagination-next, [aria-label='Next']")
                if not next_btn:
                    break
                await next_btn.click()
                await page.wait_for_timeout(2000)
                pg += 1
        except Exception as exc:
            log.error("maison_objet.error", sector=sector, error=str(exc))
        finally:
            await context.close()

    @staticmethod
    def _infer_type(text: str) -> str:
        t = text.lower()
        if "hotel" in t or "hospitality" in t:
            return "hospitality"
        if "retail" in t or "boutique" in t:
            return "retailer"
        if "wholesale" in t or "distribution" in t:
            return "distributor"
        if "sourcing" in t or "import" in t:
            return "sourcing_company"
        return "importer"
