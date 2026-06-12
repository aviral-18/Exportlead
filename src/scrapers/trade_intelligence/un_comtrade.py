"""
UN Comtrade scraper — public API (free tier: 100 req/day; premium for bulk).
Fetches import trade statistics by HS code and reporter country.
API: https://comtradeapi.un.org/

Unlike shipment-level data, Comtrade provides aggregate statistics.
We derive buyer country information and cross-reference with partner data.
"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import structlog

from src.core.config import settings
from src.scrapers.base import BaseScraper, RawRecord

log = structlog.get_logger(__name__)

COMTRADE_API = "https://comtradeapi.un.org/data/v1/get/C/A"

# Reporter countries (importers of brass products)
REPORTER_CODES = {
    "840": "US", "826": "GB", "276": "DE", "250": "FR",
    "036": "AU", "124": "CA", "528": "NL", "056": "BE",
    "380": "IT", "724": "ES", "784": "AE", "682": "SA",
    "414": "KW", "634": "QA", "702": "SG", "458": "MY",
    "392": "JP", "410": "KR", "710": "ZA", "076": "BR",
    "484": "MX", "616": "PL", "752": "SE", "208": "DK",
    "756": "CH", "040": "AT", "056": "BE", "246": "FI",
}

# HS codes: 4-digit headings for brass/metal decor
HS_CODES = ["7418", "7419", "8306", "9405", "6913"]


class UnComtradeScraper(BaseScraper):
    """
    Comtrade provides country-level aggregate trade data.
    We use it to identify which countries are large importers of brass goods,
    then generate aggregate 'market' buyer records for each country.

    For company-level data, cross-reference with shipment sources (Volza/Panjiva).
    """
    source_name = "un_comtrade"
    requests_per_second = 0.5  # free tier: conservative

    async def scrape(self) -> AsyncGenerator[RawRecord, None]:
        for hs_code in HS_CODES:
            async for record in self._fetch_hs(hs_code):
                yield record
                await asyncio.sleep(0.1)

    async def _fetch_hs(self, hs_code: str) -> AsyncGenerator[RawRecord, None]:
        params = {
            "reporterCode": ",".join(REPORTER_CODES.keys()),
            "period": "2023,2022,2021",
            "partnerCode": "356",  # India as exporter
            "cmdCode": hs_code,
            "flowCode": "M",  # imports
            "maxRecords": 500,
            "format": "JSON",
            "breakdownMode": "classic",
        }
        if settings.un_comtrade_api_key:
            params["subscription-key"] = settings.un_comtrade_api_key

        try:
            resp = await self.get(COMTRADE_API, params=params)
        except Exception as exc:
            log.error("comtrade.fetch_error", hs=hs_code, error=str(exc))
            return

        data_set = resp.get("data", [])
        for row in data_set:
            reporter_code = str(row.get("reporterCode", "")).zfill(3)
            country_code = REPORTER_CODES.get(reporter_code)
            if not country_code:
                continue

            trade_value = self._safe_float(row.get("primaryValue"))
            if not trade_value or trade_value < 10_000:
                continue

            reporter_desc = row.get("reporterDesc", "")
            year = row.get("period", "")

            yield RawRecord(
                external_id=f"comtrade_{reporter_code}_{hs_code}_{year}",
                data_source=self.source_name,
                company_name=f"{reporter_desc} Market Importers",
                country_code=country_code,
                country_name=reporter_desc,
                hs_codes=[hs_code],
                buyer_type="importer",
                estimated_annual_volume_usd=trade_value,
                volume_currency="USD",
                last_import_date=f"{year}-12-31" if year else None,
                confidence_score=0.60,  # aggregate, not company-level
                raw_data=row,
                product_categories=[f"HS:{hs_code}"],
            )
