"""
Outreach module database models.
Manages email campaigns, individual emails, and reply tracking.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.models import Base


class OutreachCampaign(Base):
    __tablename__ = "outreach_campaigns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    campaign_type: Mapped[str] = mapped_column(String(32), default="cold_outreach")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    target_country: Mapped[Optional[str]] = mapped_column(String(3), index=True)
    target_buyer_type: Mapped[Optional[str]] = mapped_column(String(64))
    target_tier: Mapped[Optional[str]] = mapped_column(String(2))
    min_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    template_name: Mapped[Optional[str]] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(5), default="en")
    emails_sent: Mapped[int] = mapped_column(Integer, default=0)
    emails_opened: Mapped[int] = mapped_column(Integer, default=0)
    emails_clicked: Mapped[int] = mapped_column(Integer, default=0)
    replies_received: Mapped[int] = mapped_column(Integer, default=0)
    positive_replies: Mapped[int] = mapped_column(Integer, default=0)
    crm_leads_created: Mapped[int] = mapped_column(Integer, default=0)
    open_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    reply_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    conversion_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    start_date: Mapped[Optional[str]] = mapped_column(String(10))
    end_date: Mapped[Optional[str]] = mapped_column(String(10))
    created_by: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())


class OutreachEmail(Base):
    __tablename__ = "outreach_emails"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    campaign_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    lead_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    canonical_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    to_email: Mapped[str] = mapped_column(String(512), nullable=False)
    to_name: Mapped[Optional[str]] = mapped_column(String(256))
    to_company: Mapped[Optional[str]] = mapped_column(String(512))
    to_country: Mapped[Optional[str]] = mapped_column(String(3))
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[Optional[str]] = mapped_column(Text)
    template_name: Mapped[Optional[str]] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(5), default="en")
    personalization_json: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_received: Mapped[bool] = mapped_column(Boolean, default=False)
    reply_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    bounce_reason: Mapped[Optional[str]] = mapped_column(String(256))
    message_id: Mapped[Optional[str]] = mapped_column(String(256), unique=True)
    tracking_pixel_id: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())


class EmailReply(Base):
    __tablename__ = "email_replies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    outreach_email_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    campaign_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    lead_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    from_email: Mapped[str] = mapped_column(String(512), nullable=False)
    from_name: Mapped[Optional[str]] = mapped_column(String(256))
    subject: Mapped[Optional[str]] = mapped_column(String(512))
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Sentiment: positive / negative / neutral / not_interested
    sentiment: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    # Intent: interested / requesting_quote / requesting_sample / asking_price / negotiating / meeting / lost / unsubscribe
    intent: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    extracted_signals_json: Mapped[Optional[str]] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    crm_history_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    auto_response_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
