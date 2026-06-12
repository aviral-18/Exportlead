"""
Data normalization pipeline.
Standardises company names, country codes, phone numbers, domains, HS codes
before they enter the deduplication / entity-resolution stages.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional
from urllib.parse import urlparse

import phonenumbers
import tldextract
from unidecode import unidecode

# ISO-3166 alpha-2 mapping (common names → code)
_COUNTRY_ALIASES: dict[str, str] = {
    "usa": "US", "united states": "US", "united states of america": "US",
    "u.s.a": "US", "u.s": "US",
    "uk": "GB", "united kingdom": "GB", "great britain": "GB",
    "england": "GB", "scotland": "GB", "wales": "GB",
    "germany": "DE", "deutschland": "DE",
    "france": "FR",
    "australia": "AU",
    "canada": "CA",
    "netherlands": "NL", "holland": "NL", "nederland": "NL",
    "belgium": "BE", "belgique": "BE",
    "italy": "IT", "italia": "IT",
    "spain": "ES", "españa": "ES",
    "uae": "AE", "united arab emirates": "AE", "dubai": "AE",
    "saudi arabia": "SA", "ksa": "SA",
    "kuwait": "KW",
    "qatar": "QA",
    "singapore": "SG",
    "malaysia": "MY",
    "japan": "JP",
    "south korea": "KR", "korea": "KR",
    "south africa": "ZA",
    "brazil": "BR", "brasil": "BR",
    "mexico": "MX", "méxico": "MX",
    "poland": "PL", "polska": "PL",
    "sweden": "SE",
    "denmark": "DK",
    "norway": "NO",
    "finland": "FI",
    "switzerland": "CH", "schweiz": "CH",
    "austria": "AT", "österreich": "AT",
    "china": "CN", "prc": "CN",
    "india": "IN",
    "international": None,
}

# Legal suffixes to strip from company names
_LEGAL_SUFFIXES = re.compile(
    r"\b(llc|ltd|limited|inc|corp|corporation|gmbh|co\.|pvt|s\.a\.|sa|ag|nv|bv|"
    r"pty|plc|srl|s\.r\.l|s\.p\.a|oü|as|ab|oy|aps|sas|eurl|snc|sc|"
    r"sole proprietor|trading|enterprises|international|company|group|holdings|"
    r"imports|exports|solutions|services|industries|manufacturing|mfg)\b\.?",
    re.IGNORECASE,
)

# Noise tokens that appear in trade data and shouldn't affect matching
_NOISE_TOKENS = re.compile(
    r"\b(and|the|of|for|&|a|an|or)\b",
    re.IGNORECASE,
)


def normalise_company_name(name: str) -> str:
    """
    Returns a standardised lowercase token string for fuzzy matching.
    Steps: unicode→ascii, lowercase, strip legal suffixes, remove noise.
    """
    if not name:
        return ""
    # Transliterate unicode to closest ASCII
    name = unidecode(name)
    # Lowercase
    name = name.lower()
    # Remove punctuation except spaces
    name = re.sub(r"[^\w\s]", " ", name)
    # Strip legal suffixes
    name = _LEGAL_SUFFIXES.sub(" ", name)
    # Remove noise tokens
    name = _NOISE_TOKENS.sub(" ", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


def normalise_country_code(
    country_name: Optional[str],
    country_code: Optional[str],
) -> Optional[str]:
    """Return a validated ISO-3166 alpha-2 code."""
    if country_code and len(country_code) == 2:
        return country_code.upper()
    if country_name:
        key = country_name.lower().strip()
        mapped = _COUNTRY_ALIASES.get(key)
        if mapped:
            return mapped
        # Partial match fallback
        for alias, code in _COUNTRY_ALIASES.items():
            if alias in key or key in alias:
                return code
    return None


def extract_domain(website: Optional[str]) -> Optional[str]:
    """Extract registrable domain from a URL (strips subdomain + path)."""
    if not website:
        return None
    if not website.startswith(("http://", "https://")):
        website = "https://" + website
    extracted = tldextract.extract(website)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}".lower()
    return None


def normalise_phone(phone: str, country_code: Optional[str] = None) -> Optional[str]:
    """Return E.164 formatted phone number or None."""
    try:
        region = country_code or "US"
        parsed = phonenumbers.parse(phone, region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
    except phonenumbers.NumberParseException:
        pass
    # Best-effort: remove non-numeric chars and return
    digits = re.sub(r"[^\d+]", "", phone)
    return digits if len(digits) >= 7 else None


def normalise_hs_code(hs: str) -> str:
    """Strip dots and normalise to 4/6/8-digit format."""
    return re.sub(r"[^\d]", "", hs)[:8]


def normalise_record(record: dict) -> dict:
    """
    Apply all normalisation functions to a raw record dict.
    Modifies and returns the dict in place.
    """
    # Company name
    if record.get("company_name"):
        record["company_name_normalized"] = normalise_company_name(
            record["company_name"]
        )

    # Country
    record["country_code"] = normalise_country_code(
        record.get("country_name"), record.get("country_code")
    )

    # Domain
    if record.get("website"):
        record["website_domain"] = extract_domain(record["website"])

    # Phones
    phones = record.get("phone") or []
    record["phone"] = [
        n for p in phones
        if (n := normalise_phone(p, record.get("country_code")))
    ]

    # HS codes
    if record.get("hs_codes"):
        record["hs_codes"] = [
            normalise_hs_code(h) for h in record["hs_codes"] if h
        ]

    # Volume: ensure float
    vol = record.get("estimated_annual_volume_usd")
    if vol is not None:
        try:
            record["estimated_annual_volume_usd"] = float(vol)
        except (TypeError, ValueError):
            record["estimated_annual_volume_usd"] = None

    return record
