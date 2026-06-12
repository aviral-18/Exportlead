"""Real-time event types and push helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.realtime.manager import ws_manager


class EventType(str, Enum):
    # Buyer events
    buyer_discovered = "buyer.discovered"
    buyer_scored = "buyer.scored"
    buyer_emerging = "buyer.emerging"
    # Opportunity events
    opportunity_created = "opportunity.created"
    opportunity_updated = "opportunity.updated"
    opportunity_ranked = "opportunity.ranked"
    # CRM events
    lead_status_changed = "lead.status_changed"
    followup_due = "followup.due"
    deal_probability_updated = "deal.probability_updated"
    # Outreach events
    email_replied = "email.replied"
    campaign_launched = "campaign.launched"
    # Pipeline events
    discovery_run_complete = "discovery.run_complete"
    forecast_updated = "forecast.updated"
    # System events
    notification = "system.notification"
    pipeline_status = "pipeline.status"


async def push_event(
    event_type: EventType,
    data: dict[str, Any],
    channel: str = "global",
) -> None:
    """Broadcast a typed event to all clients on a channel."""
    payload = {
        "event": event_type.value,
        "data": data,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    await ws_manager.broadcast(payload, channel=channel)


async def push_notification(
    title: str,
    message: str,
    level: str = "info",
    channel: str = "global",
) -> None:
    await push_event(
        EventType.notification,
        {"title": title, "message": message, "level": level},
        channel=channel,
    )
