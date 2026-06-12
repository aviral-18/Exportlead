"""
ITC TradeMap scraper — https://www.trademap.org
Provides trade statistics by HS code, country, and company.
Requires ITC login (free registration for some features, subscription for others).
"""
from __future__ import annotations

import re
from typing import AsyncGenerator

import structlog
from bs4 import BeautifulSoup

from src.core.config import settings
from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

TRADEMAP_BASE = "https://www.trademap.org"
LOGIN_URL = f"{TRADEMAP_BASE}/tradestat/Product_SelProduct_TS.aspx"

HS_CODES_6DIGIT = [
    "741810", "741820", "741900", "830600", "830610", "830620",
    "940540", "940550", "691300", "691390",
]

TARGET_REPORTERS = [
    "usa", "gbr", "deu", "fra", "aus", "can", "nld", "bel",
    "ita", "esp", "are", "sau", "sgp", "mys", "jpn", "kor",
    "zaf", "bra", "mex", "pol", "swe", "dnk", "che", "aut",
]


class TradeMapScraper(BaseScraper):
    """
    Scrapes TradeMap company-level import data.
    Requires TRADE_MAP_USERNAME and TRADE_MAP_PASSWORD.
    Falls back to public aggregate data without auth.
    """
    source_name = "trade_map"
    requires_browser = True
    requests_per_second = 0.8

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        if not settings.trade_map_username:
            log.warning("trade_map.no_credentials")
            async for r in self._scrape_public():
                yield r
            return
        async for r in self._scrape_authenticated():
            yield r

    async def _scrape_public(self) -> AsyncGenerator[RawRecord, None]:
        """Fetch publicly available country-level trade data."""
        for hs in HS_CODES_6DIGIT[:3]:  # rate-limited on public
            url = (
                f"{TRADEMAP_BASE}/Country_SelProductCountry_TS.aspx"
                f"?nvpm=1%7c%7c%7c%7c%7c{hs}%7c%7c%7c6%7c1%7c1%7c1%7c2%7c1%7c2%7c1%7c1"
            )
            try:
                html = await self.browse(url, wait_for_selector="#GridViewPanelHS6")
            except Exception as exc:
                log.error("trade_map.browse_error", hs=hs, error=str(exc))
                continue

            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table", {"id": re.compile(r"GridView")})
            if not table:
                continue

            for row in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) < 4:
                    continue
                country = cells[0]
                trade_value_str = cells[2].replace(",", "")
                trade_value = self._safe_float(trade_value_str)
                if not trade_value:
                    continue

                yield RawRecord(
                    external_id=f"trademap_pub_{hs}_{country.lower()[:3]}",
                    data_source=self.source_name,
                    company_name=f"{country} Brass Importers",
                    country_name=country,
                    hs_codes=[hs],
                    buyer_type="importer",
                    estimated_annual_volume_usd=trade_value * 1000,
                    confidence_score=0.55,
                    raw_data={"country": country, "hs": hs, "value": trade_value},
                )

    async def _scrape_authenticated(self) -> AsyncGenerator[RawRecord, None]:
        """Authenticated scrape for company-level import data."""
        context = await self._new_context()
        try:
            page = await context.new_page()
            # Login
            await page.goto(f"{TRADEMAP_BASE}/Logon.aspx")
            await page.fill("#ctl00_PageContent_Login1_UserName", settings.trade_map_username)
            await page.fill("#ctl00_PageContent_Login1_Password", settings.trade_map_password)
            await page.click("#ctl00_PageContent_Login1_LoginButton")
            await page.wait_for_load_state("networkidle")

            for hs in HS_CODES_6DIGIT:
                url = (
                    f"{TRADEMAP_BASE}/Companies_SelProductCountry_TS.aspx"
                    f"?nvpm=1%7cind%7c%7c%7c%7c{hs}%7c%7c%7c6%7c1%7c1%7c2%7c2%7c1%7c2%7c1%7c1"
                )
                await page.goto(url, wait_until="networkidle")
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")

                for row in self._parse_company_table(soup, hs):
                    yield row
        finally:
            await context.close()

    def _parse_company_table(self, soup: BeautifulSoup, hs: str):
        table = soup.find("table", id=re.compile(r"GridViewPanelHS6"))
        if not table:
            return
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if not cells:
                continue
            data = dict(zip(headers, cells))
            company = data.get("Importer", "").strip()
            if not company:
                continue
            yield RawRecord(
                external_id=f"trademap_{hs}_{company[:32]}",
                data_source=self.source_name,
                company_name=company,
                country_name=data.get("Country"),
                hs_codes=[hs],
                buyer_type="importer",
                estimated_annual_volume_usd=self._safe_float(
                    data.get("Trade Value (USD Thousand)", "0").replace(",", "")
                ),
                confidence_score=0.78,
                raw_data=data,
            )
