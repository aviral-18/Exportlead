"""
Outreach email generation engine.

Produces personalised, professional emails for brass export outreach.
All templates are specific to Moradabad craftsmanship and are structured
to move buyers through the funnel: awareness → interest → quote → PO.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

# ── Sender defaults (override via settings or per-campaign) ──────────────────
DEFAULT_SENDER = {
    "name": "Export Manager",
    "title": "Head of International Sales",
    "company": "Moradabad Brass Crafts",
    "email": "exports@moradabadbrass.com",
    "phone": "+91-591-2410000",
    "website": "https://www.moradabadbrass.com",
    "city": "Moradabad, Uttar Pradesh, India",
}

# ── Price range hints by buyer volume tier ───────────────────────────────────
_PRICE_HINTS: dict[str, str] = {
    "large":  "USD 3.50–28 per piece (FOB Mundra/JNPT)",
    "medium": "USD 5–35 per piece (FOB Mundra/JNPT)",
    "small":  "USD 6–45 per piece (FOB Mundra/JNPT)",
}

_MOQ_HINTS: dict[str, str] = {
    "large":  "500 pieces per design (LCL from 50 cartons)",
    "medium": "200–500 pieces per design",
    "small":  "100 pieces per design for trial orders",
}

# ── Current trade fair schedule ───────────────────────────────────────────────
_TRADE_FAIRS: list[dict] = [
    {"name": "IHGF Delhi Fair (Autumn)", "months": [9, 10], "location": "Greater Noida, India"},
    {"name": "Ambiente Frankfurt", "months": [2],           "location": "Frankfurt, Germany"},
    {"name": "NY Now — Winter",    "months": [1, 2],        "location": "New York, USA"},
    {"name": "Canton Fair",        "months": [4, 10],       "location": "Guangzhou, China"},
    {"name": "IHGF Delhi Fair (Spring)", "months": [3, 4],  "location": "Greater Noida, India"},
    {"name": "Maison & Objet",     "months": [1, 9],        "location": "Paris, France"},
]


@dataclass
class GeneratedEmail:
    subject: str
    body_text: str
    body_html: str
    template_name: str
    language: str
    personalization: dict


def _tier(vol: float) -> str:
    if vol >= 20_000_000:
        return "large"
    if vol >= 2_000_000:
        return "medium"
    return "small"


def _upcoming_fair(month: int) -> Optional[dict]:
    for fair in _TRADE_FAIRS:
        if month in fair["months"] or (month + 1) % 12 in fair["months"]:
            return fair
    return None


def _html_wrap(text: str) -> str:
    lines = text.strip().split("\n")
    paras = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            paras.append(f"<p>{stripped}</p>")
        else:
            paras.append("<br/>")
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#333;line-height:1.6;max-width:600px;margin:auto;padding:20px;">
{"".join(paras)}
</body>
</html>"""


def generate(
    template_name: str,
    buyer: Any,
    sender: Optional[dict] = None,
    language: str = "en",
    custom_vars: Optional[dict] = None,
) -> GeneratedEmail:
    """
    Generate a personalised outreach email.

    template_name options:
      initial_introduction | warm_followup | trade_fair |
      sample_offer | quote_followup | emerging_importer | re_engagement
    """
    def _g(obj, attr, default=None):
        if hasattr(obj, attr):
            return getattr(obj, attr)
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return default

    s = {**DEFAULT_SENDER, **(sender or {})}
    cv = custom_vars or {}

    company_name = _g(buyer, "company_name") or "Your Company"
    contact_name = _g(buyer, "contact_name") or "Procurement Team"
    country_name = _g(buyer, "country_name") or "your country"
    country_code = (_g(buyer, "country_code") or "US").upper()
    buyer_type = (_g(buyer, "buyer_type") or "importer").lower()
    vol = float(_g(buyer, "estimated_annual_volume_usd") or 0)
    tier = _tier(vol)
    cats = _g(buyer, "product_categories_json") or "[]"
    if isinstance(cats, str):
        try:
            cats = json.loads(cats)
        except Exception:
            cats = []
    cat_str = ", ".join(cats[:3]) if cats else "brass home decor and handicrafts"

    price_hint = cv.get("price_hint") or _PRICE_HINTS[tier]
    moq_hint = cv.get("moq_hint") or _MOQ_HINTS[tier]
    month = date.today().month

    personalization = {
        "company_name": company_name,
        "contact_name": contact_name,
        "country_name": country_name,
        "buyer_type": buyer_type,
        "product_categories": cat_str,
        "price_hint": price_hint,
        "moq_hint": moq_hint,
        "tier": tier,
    }

    fn = _TEMPLATE_MAP.get(template_name)
    if fn is None:
        fn = _TEMPLATE_MAP["initial_introduction"]

    subject, body = fn(
        company_name=company_name,
        contact_name=contact_name,
        country_name=country_name,
        country_code=country_code,
        buyer_type=buyer_type,
        cat_str=cat_str,
        price_hint=price_hint,
        moq_hint=moq_hint,
        tier=tier,
        sender=s,
        month=month,
        cv=cv,
    )

    return GeneratedEmail(
        subject=subject,
        body_text=body,
        body_html=_html_wrap(body),
        template_name=template_name,
        language=language,
        personalization=personalization,
    )


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATES
# ═════════════════════════════════════════════════════════════════════════════

def _tpl_initial_introduction(**kw) -> tuple[str, str]:
    s = kw["sender"]
    fair = _upcoming_fair(kw["month"])
    fair_line = (
        f"\nWe will also be exhibiting at {fair['name']} in {fair['location']} — "
        f"it would be a pleasure to meet in person and showcase our range."
        if fair else ""
    )
    subject = (
        f"Premium Brass Handicrafts from Moradabad — "
        f"Exclusive Sourcing Opportunity for {kw['company_name']}"
    )
    body = f"""Dear {kw['contact_name']},

I hope this message finds you well.

My name is {s['name']}, {s['title']} at {s['company']}, a leading manufacturer and exporter of premium brass handicrafts, home décor, religious artifacts, and hotelware from Moradabad, India — the world's brass capital with over 400 years of craft heritage.

Having followed {kw['company_name']}'s impressive growth in the {kw['buyer_type']} segment across {kw['country_name']}, I believe there is a compelling synergy between your sourcing requirements in {kw['cat_str']} and our manufacturing capabilities.

Here is why {kw['country_name']}-based buyers choose Moradabad:

• Competitive FOB pricing: {kw['price_hint']}
• MOQ: {kw['moq_hint']}
• ISO 9001:2015 certified facilities with in-house quality control
• Custom designs, private labelling, and brand-specific packaging
• Lead time: 30–45 days for repeat orders; 45–60 days for new designs
• Reliable shipments via JNPT / Mundra Port with full export documentation
• Government incentives (RoDTEP + Duty Drawback) passed on to keep prices sharp{fair_line}

I would love to share our latest product catalogue (200+ designs across {kw['cat_str']}) and arrange a brief video call at your convenience.

Would you be available for a 20-minute introductory call this week or next?

Warm regards,

{s['name']}
{s['title']}
{s['company']} | {s['city']}
Email: {s['email']} | Phone/WhatsApp: {s['phone']}
Website: {s['website']}"""
    return subject, body


def _tpl_warm_followup(**kw) -> tuple[str, str]:
    s = kw["sender"]
    subject = f"Following Up — Brass Sourcing Opportunity for {kw['company_name']}"
    body = f"""Dear {kw['contact_name']},

I wanted to follow up on my earlier note regarding premium brass handicrafts and home décor from Moradabad, India.

I understand you receive many supplier enquiries, so I will keep this brief. Since my last message, we have added 45 new designs to our catalogue specifically curated for the {kw['country_name']} market — including trending items in {kw['cat_str']}.

What has resonated most with {kw['buyer_type']}s in {kw['country_name']}:

• Brass lanterns and candle holders — margin-rich, high visual impact
• Decorative figurines and religious artifacts — consistent repeat orders
• Hotel amenity ranges — bespoke monogramming available

Our pricing remains at {kw['price_hint']}, and we can arrange complimentary samples for shortlisted designs.

Would a quick call work? I am available most days between 9 AM – 6 PM IST (GMT+5:30), which overlaps comfortably with business hours in {kw['country_name']}.

Best regards,

{s['name']}
{s['title']} | {s['company']}
{s['email']} | {s['phone']}"""
    return subject, body


def _tpl_trade_fair(**kw) -> tuple[str, str]:
    s = kw["sender"]
    month = kw["month"]
    fair = _upcoming_fair(month)
    fair_name = fair["name"] if fair else "the upcoming trade fair"
    fair_loc = fair["location"] if fair else ""
    subject = f"Meet {kw['company_name']} at {fair_name} — Moradabad Brass Showcase"
    body = f"""Dear {kw['contact_name']},

I am reaching out ahead of {fair_name}{' in ' + fair_loc if fair_loc else ''}, where our team will be presenting our latest brass handicraft and home décor collections.

Given {kw['company_name']}'s strong presence in {kw['cat_str']}, I believe our new season range — featuring bold artisan finishes, contemporary silhouettes on traditional forms, and competitive FOB pricing — will be directly relevant to your buying plans.

At the fair, we will be showcasing:

• NEW: Antique brass finish festive lighting collection (150+ SKUs)
• Hotel amenity programme: bespoke brass accessories with custom branding
• Garden and outdoor décor: weather-treated brass with powder-coat finishes
• Religious artifacts: Export-compliant packaging for {kw['country_name']} import requirements

Pricing: {kw['price_hint']}

I would like to schedule a dedicated 30-minute appointment at our booth. Pre-booked meetings get priority viewing of our exclusive new launches before the general floor opens.

Could you let me know your availability? I can share our booth number and a digital look-book immediately upon confirmation.

Looking forward to meeting you in person.

Warm regards,

{s['name']}
{s['title']} | {s['company']}
{s['email']} | {s['phone']}"""
    return subject, body


def _tpl_sample_offer(**kw) -> tuple[str, str]:
    s = kw["sender"]
    subject = f"Complimentary Brass Samples for {kw['company_name']} — No Obligation"
    body = f"""Dear {kw['contact_name']},

Thank you for your interest in our brass product range from Moradabad, India.

I am pleased to offer {kw['company_name']} a complimentary sample set — a curated selection of our best-performing designs in {kw['cat_str']}, shipped to your address in {kw['country_name']} at no charge.

The sample set includes:

• 5–8 pieces across our most popular categories
• Specifications card with HS codes, dimensions, weight, and FOB price
• Custom finish options (antique brass, lacquered, nickel, copper tone)
• Care and packaging inserts compatible with {kw['country_name']} retail requirements

Shipping is DHL Express — estimated 3–5 business days to {kw['country_name']}. We only ask that you provide feedback within 2–3 weeks so we can refine the selection for any bulk order discussion.

To receive your sample set, please reply with:
1. Delivery address
2. Any specific designs or categories you would like prioritised
3. Your preferred finish(es)

We have shipped samples to {kw['buyer_type']}s across 40+ countries. Buyers who move to bulk orders typically place their first container within 60 days of sample approval.

I look forward to your confirmation.

Best regards,

{s['name']}
{s['title']} | {s['company']}
{s['email']} | WhatsApp: {s['phone']}
{s['website']}"""
    return subject, body


def _tpl_quote_followup(**kw) -> tuple[str, str]:
    s = kw["sender"]
    ref = kw["cv"].get("quotation_number", "our recent quotation")
    days = kw["cv"].get("validity_days", 30)
    subject = f"Checking In — Quotation {ref} for {kw['company_name']}"
    body = f"""Dear {kw['contact_name']},

I wanted to touch base regarding {ref} we sent across recently for your brass and home décor requirements.

I understand procurement decisions of this nature require thorough evaluation — I simply wanted to ensure:

1. The quotation reached the right person and all documentation is clear
2. Any questions around HS codes, duty implications for {kw['country_name']}, or product specifications have been addressed
3. You are aware that the current pricing is valid for {days} days from issue date

If there is anything we can adjust — whether delivery timeline, packing standards, payment terms, or design modifications — I am happy to discuss and revise accordingly.

For context, {kw['buyer_type']}s in {kw['country_name']} have been particularly responsive to our:
• Net 30/60 LC terms for first orders
• Phased delivery: 40% advance, balance on BL copy
• Sample batch included with first commercial shipment at no extra charge

A brief call (15 minutes) would help me understand any hesitation and ensure this quotation truly meets your needs.

Please let me know your thoughts at your convenience.

Best regards,

{s['name']}
{s['title']} | {s['company']}
{s['email']} | {s['phone']}"""
    return subject, body


def _tpl_emerging_importer(**kw) -> tuple[str, str]:
    s = kw["sender"]
    subject = (
        f"Welcome to the Global Brass Market — "
        f"A Dedicated Partner for {kw['company_name']}"
    )
    body = f"""Dear {kw['contact_name']},

Congratulations on establishing {kw['company_name']}'s presence in {kw['cat_str']} imports — it is an exciting segment with strong and growing demand in {kw['country_name']}.

As a manufacturer that has been supplying {kw['buyer_type']}s for over two decades, we understand the challenges of sourcing from a new market: quality consistency, reliable lead times, clear documentation, and supplier accountability.

We would like to be your first choice for Moradabad brass.

Here is what we offer specifically for new importers:

• Dedicated account manager based in India, available during your business hours
• Pre-shipment quality inspection reports with photographic evidence
• Full export documentation: BL, Packing List, Invoice, Certificate of Origin, RCMC
• Competitive pricing: {kw['price_hint']}
• Small trial order facility: {kw['moq_hint']}
• WhatsApp production updates throughout manufacturing

For your first order, we suggest a trial shipment of 3–5 designs in your core {kw['cat_str']} category. This allows you to validate quality, transit time, and market reception before committing to larger volumes.

I have attached our New Importer Guide which covers HS code classification, duty rates for {kw['country_name']}, and common pitfalls to avoid.

Would you be open to a quick call this week? I can have a catalogue and indicative pricing in your inbox within the hour.

Warm regards,

{s['name']}
{s['title']} | {s['company']}
{s['email']} | WhatsApp: {s['phone']}
{s['website']}

P.S. We are ISO 9001:2015 certified and are registered with the Export Promotion Council for Handicrafts (EPCH), ensuring full compliance with international quality and documentation standards."""
    return subject, body


def _tpl_re_engagement(**kw) -> tuple[str, str]:
    s = kw["sender"]
    subject = f"Reconnecting — Brass Sourcing Update for {kw['company_name']}"
    body = f"""Dear {kw['contact_name']},

It has been a while since we last connected, and I wanted to reach out with some meaningful updates that may be relevant to your current sourcing plans.

Since our last conversation, we have:

• Expanded our manufacturing capacity by 35% — shorter lead times, now 28–40 days
• Launched a bespoke design service with 3D mockups delivered within 72 hours of brief
• Added 120 new designs in {kw['cat_str']} that have been performing exceptionally for {kw['buyer_type']}s in {kw['country_name']}
• Strengthened our compliance team — full REACH, RoHS, and California Prop 65 documentation available
• Current pricing: {kw['price_hint']} — unchanged from 18 months ago despite rising global freight

I suspect your brass sourcing requirements have evolved. I would welcome the opportunity to present a fresh proposal tailored to your current needs.

Could we schedule a 20-minute call? I can prepare a focused catalogue with pricing before our conversation.

Best regards,

{s['name']}
{s['title']} | {s['company']}
{s['email']} | {s['phone']}"""
    return subject, body


_TEMPLATE_MAP = {
    "initial_introduction": _tpl_initial_introduction,
    "warm_followup": _tpl_warm_followup,
    "trade_fair": _tpl_trade_fair,
    "sample_offer": _tpl_sample_offer,
    "quote_followup": _tpl_quote_followup,
    "emerging_importer": _tpl_emerging_importer,
    "re_engagement": _tpl_re_engagement,
}

AVAILABLE_TEMPLATES = list(_TEMPLATE_MAP.keys())
