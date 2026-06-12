"""
CRM module models.
Imports Base from src.core.models to share the same metadata / engine.
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, Enum,
    Index, Integer, Numeric, SmallInteger, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.core.models import Base


# ── Enumerations ──────────────────────────────────────────────────────────────

class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"
    DORMANT = "dormant"


class LeadSource(str, enum.Enum):
    DATABASE = "database"
    REFERRAL = "referral"
    TRADE_FAIR = "trade_fair"
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    B2B_PLATFORM = "b2b_platform"
    OTHER = "other"


class LeadPriority(str, enum.Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class InteractionType(str, enum.Enum):
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"
    TRADE_FAIR = "trade_fair"
    SAMPLE_SENT = "sample_sent"
    QUOTE_SENT = "quote_sent"
    PO_RECEIVED = "po_received"
    OTHER = "other"


class InteractionOutcome(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    NO_RESPONSE = "no_response"


class OpportunityStage(str, enum.Enum):
    PROSPECTING = "prospecting"
    QUALIFICATION = "qualification"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


class SampleStatus(str, enum.Enum):
    PREPARING = "preparing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    REJECTED = "rejected"
    APPROVED = "approved"
    PENDING_FEEDBACK = "pending_feedback"


class QuotationStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVISED = "revised"


class POStatus(str, enum.Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    IN_PRODUCTION = "in_production"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ProductionStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PRODUCTION = "in_production"
    QUALITY_CHECK = "quality_check"
    READY_TO_SHIP = "ready_to_ship"
    SHIPPED = "shipped"
    DELIVERED = "delivered"


class Incoterms(str, enum.Enum):
    EXW = "EXW"
    FCA = "FCA"
    FOB = "FOB"
    CFR = "CFR"
    CIF = "CIF"
    DAP = "DAP"
    DDP = "DDP"


class FollowUpType(str, enum.Enum):
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    SEND_SAMPLE = "send_sample"
    SEND_QUOTE = "send_quote"
    FOLLOW_UP = "follow_up"
    CHECK_IN = "check_in"


class FollowUpPriority(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ── Lead ──────────────────────────────────────────────────────────────────────

class Lead(Base):
    __tablename__ = "crm_leads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True, index=True
    )
    canonical_buyer_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)

    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[Optional[str]] = mapped_column(String(3))
    country_name: Mapped[Optional[str]] = mapped_column(String(128))

    # Primary contact
    contact_name: Mapped[Optional[str]] = mapped_column(Text)
    contact_title: Mapped[Optional[str]] = mapped_column(String(128))
    contact_email: Mapped[Optional[str]] = mapped_column(Text)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    contact_linkedin: Mapped[Optional[str]] = mapped_column(Text)
    contact_whatsapp: Mapped[Optional[str]] = mapped_column(String(50))

    status: Mapped[str] = mapped_column(
        Enum(LeadStatus, name="lead_status_enum"),
        default=LeadStatus.NEW, index=True
    )
    source: Mapped[str] = mapped_column(
        Enum(LeadSource, name="lead_source_enum"),
        default=LeadSource.DATABASE
    )
    priority: Mapped[str] = mapped_column(
        Enum(LeadPriority, name="lead_priority_enum"),
        default=LeadPriority.WARM, index=True
    )

    assigned_to: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    product_interest: Mapped[Optional[dict]] = mapped_column(JSONB)
    estimated_value_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    last_contact_date: Mapped[Optional[date]] = mapped_column(Date)
    expected_close_date: Mapped[Optional[date]] = mapped_column(Date)

    # Denormalized counters (updated by triggers or app logic)
    notes_count: Mapped[int] = mapped_column(Integer, default=0)
    interactions_count: Mapped[int] = mapped_column(Integer, default=0)
    open_followups: Mapped[int] = mapped_column(Integer, default=0)

    tags: Mapped[Optional[dict]] = mapped_column(JSONB)
    extra: Mapped[Optional[dict]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_crm_leads_status_priority", "status", "priority"),
        Index("ix_crm_leads_assigned", "assigned_to"),
        Index("ix_crm_leads_company", "company_name"),
    )


# ── Contact ───────────────────────────────────────────────────────────────────

class Contact(Base):
    __tablename__ = "crm_contacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    canonical_buyer_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(128))
    department: Mapped[Optional[str]] = mapped_column(String(128))
    email: Mapped[Optional[str]] = mapped_column(Text, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    whatsapp: Mapped[Optional[str]] = mapped_column(String(50))
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_contact_method: Mapped[Optional[str]] = mapped_column(String(20))
    language: Mapped[Optional[str]] = mapped_column(String(10))
    timezone: Mapped[Optional[str]] = mapped_column(String(64))
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False)

    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Contact History ───────────────────────────────────────────────────────────

class ContactHistory(Base):
    __tablename__ = "crm_contact_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)

    interaction_type: Mapped[str] = mapped_column(
        Enum(InteractionType, name="interaction_type_enum"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10), default="outbound")
    subject: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    outcome: Mapped[Optional[str]] = mapped_column(
        Enum(InteractionOutcome, name="interaction_outcome_enum")
    )
    next_action: Mapped[Optional[str]] = mapped_column(Text)
    duration_minutes: Mapped[Optional[int]] = mapped_column(SmallInteger)
    interacted_by: Mapped[Optional[str]] = mapped_column(String(128))
    attachments: Mapped[Optional[dict]] = mapped_column(JSONB)

    interacted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_crm_history_lead_date", "lead_id", "interacted_at"),
    )


# ── Note ─────────────────────────────────────────────────────────────────────

class Note(Base):
    __tablename__ = "crm_notes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(String(32), default="general")
    created_by: Mapped[Optional[str]] = mapped_column(String(128))
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Follow-up ─────────────────────────────────────────────────────────────────

class FollowUp(Base):
    __tablename__ = "crm_followups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    follow_up_type: Mapped[str] = mapped_column(
        Enum(FollowUpType, name="followup_type_enum"),
        default=FollowUpType.FOLLOW_UP
    )
    priority: Mapped[str] = mapped_column(
        Enum(FollowUpPriority, name="followup_priority_enum"),
        default=FollowUpPriority.MEDIUM, index=True
    )
    assigned_to: Mapped[Optional[str]] = mapped_column(String(128))
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    outcome_notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_crm_followups_due", "scheduled_at", "is_completed"),
    )


# ── Opportunity ───────────────────────────────────────────────────────────────

class Opportunity(Base):
    __tablename__ = "crm_opportunities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid4()), unique=True, index=True
    )
    lead_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(
        Enum(OpportunityStage, name="opportunity_stage_enum"),
        default=OpportunityStage.PROSPECTING, index=True
    )
    probability_pct: Mapped[int] = mapped_column(SmallInteger, default=20)
    estimated_value_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    products: Mapped[Optional[dict]] = mapped_column(JSONB)
    quantity_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    incoterms: Mapped[Optional[str]] = mapped_column(
        Enum(Incoterms, name="incoterms_enum")
    )
    payment_terms: Mapped[Optional[str]] = mapped_column(String(128))

    expected_close_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_close_date: Mapped[Optional[date]] = mapped_column(Date)
    won_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    lost_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    lost_reason: Mapped[Optional[str]] = mapped_column(Text)

    assigned_to: Mapped[Optional[str]] = mapped_column(String(128))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_crm_opp_stage_value", "stage", "estimated_value_usd"),
    )


# ── Sample ────────────────────────────────────────────────────────────────────

class Sample(Base):
    __tablename__ = "crm_samples"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sample_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    lead_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)

    products: Mapped[Optional[dict]] = mapped_column(JSONB)
    quantity_pieces: Mapped[Optional[int]] = mapped_column(Integer)
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3))

    courier: Mapped[Optional[str]] = mapped_column(String(64))
    tracking_number: Mapped[Optional[str]] = mapped_column(String(128))
    sent_date: Mapped[Optional[date]] = mapped_column(Date)
    estimated_delivery: Mapped[Optional[date]] = mapped_column(Date)
    delivered_date: Mapped[Optional[date]] = mapped_column(Date)

    status: Mapped[str] = mapped_column(
        Enum(SampleStatus, name="sample_status_enum"),
        default=SampleStatus.PREPARING, index=True
    )

    cost_inr: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    paid_by_buyer: Mapped[bool] = mapped_column(Boolean, default=False)

    feedback: Mapped[Optional[str]] = mapped_column(Text)
    feedback_date: Mapped[Optional[date]] = mapped_column(Date)
    approved_for_bulk: Mapped[Optional[bool]] = mapped_column(Boolean)

    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Quotation ─────────────────────────────────────────────────────────────────

class Quotation(Base):
    __tablename__ = "crm_quotations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    quotation_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    lead_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)

    # Line items: [{product, hs_code, qty_pcs, weight_kg, unit_price, total}]
    line_items: Mapped[Optional[dict]] = mapped_column(JSONB)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    total_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    incoterms: Mapped[Optional[str]] = mapped_column(
        Enum(Incoterms, name="incoterms_enum")
    )
    payment_terms: Mapped[Optional[str]] = mapped_column(String(256))
    validity_days: Mapped[int] = mapped_column(SmallInteger, default=30)
    delivery_weeks: Mapped[Optional[int]] = mapped_column(SmallInteger)
    port_of_loading: Mapped[Optional[str]] = mapped_column(String(128))
    port_of_discharge: Mapped[Optional[str]] = mapped_column(String(128))
    packing_details: Mapped[Optional[str]] = mapped_column(Text)
    special_terms: Mapped[Optional[str]] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        Enum(QuotationStatus, name="quotation_status_enum"),
        default=QuotationStatus.DRAFT, index=True
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)

    profitability: Mapped[Optional[dict]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Purchase Order ────────────────────────────────────────────────────────────

class PurchaseOrder(Base):
    __tablename__ = "crm_purchase_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(String(128), nullable=False)
    our_reference: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    lead_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    opportunity_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    quotation_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)

    # Line items: [{product, hs_code, qty_pcs, weight_kg, unit_price, total}]
    line_items: Mapped[Optional[dict]] = mapped_column(JSONB)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    total_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    # Payment
    advance_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    advance_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    advance_received_date: Mapped[Optional[date]] = mapped_column(Date)
    balance_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    balance_due_date: Mapped[Optional[date]] = mapped_column(Date)
    balance_received_date: Mapped[Optional[date]] = mapped_column(Date)
    payment_terms: Mapped[Optional[str]] = mapped_column(String(256))
    lc_number: Mapped[Optional[str]] = mapped_column(String(128))

    # Logistics
    incoterms: Mapped[Optional[str]] = mapped_column(
        Enum(Incoterms, name="incoterms_enum")
    )
    shipping_port: Mapped[Optional[str]] = mapped_column(String(128))
    destination_port: Mapped[Optional[str]] = mapped_column(String(128))
    country_of_destination: Mapped[Optional[str]] = mapped_column(String(3))
    bl_number: Mapped[Optional[str]] = mapped_column(String(128))
    container_number: Mapped[Optional[str]] = mapped_column(String(64))

    # Production timeline
    production_status: Mapped[str] = mapped_column(
        Enum(ProductionStatus, name="production_status_enum"),
        default=ProductionStatus.PENDING, index=True
    )
    expected_production_days: Mapped[Optional[int]] = mapped_column(SmallInteger)
    production_start_date: Mapped[Optional[date]] = mapped_column(Date)
    production_end_date: Mapped[Optional[date]] = mapped_column(Date)
    shipment_date: Mapped[Optional[date]] = mapped_column(Date)
    delivery_date: Mapped[Optional[date]] = mapped_column(Date)

    status: Mapped[str] = mapped_column(
        Enum(POStatus, name="po_status_enum"),
        default=POStatus.NEW, index=True
    )

    documents: Mapped[Optional[dict]] = mapped_column(JSONB)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_crm_po_status", "status", "production_status"),
        UniqueConstraint("po_number", "lead_id", name="uq_po_number_lead"),
    )
