"""Add CRM module tables

Revision ID: 003_crm
Revises: 002_lead_scores
Create Date: 2026-06-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_crm"
down_revision = "002_lead_scores"
branch_labels = None
depends_on = None

# ── Enum helpers ──────────────────────────────────────────────────────────────

def _enum(*values, name):
    return sa.Enum(*values, name=name)


def upgrade() -> None:
    # ── Enum types ─────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE lead_status_enum AS ENUM ('new','contacted','qualified','proposal','negotiation','won','lost','dormant')")
    op.execute("CREATE TYPE lead_source_enum AS ENUM ('database','referral','trade_fair','inbound','outbound','b2b_platform','other')")
    op.execute("CREATE TYPE lead_priority_enum AS ENUM ('hot','warm','cold')")
    op.execute("CREATE TYPE interaction_type_enum AS ENUM ('call','email','meeting','whatsapp','linkedin','trade_fair','sample_sent','quote_sent','po_received','other')")
    op.execute("CREATE TYPE interaction_outcome_enum AS ENUM ('positive','neutral','negative','no_response')")
    op.execute("CREATE TYPE opportunity_stage_enum AS ENUM ('prospecting','qualification','proposal','negotiation','won','lost')")
    op.execute("CREATE TYPE sample_status_enum AS ENUM ('preparing','shipped','delivered','rejected','approved','pending_feedback')")
    op.execute("CREATE TYPE quotation_status_enum AS ENUM ('draft','sent','viewed','accepted','rejected','expired','revised')")
    op.execute("CREATE TYPE po_status_enum AS ENUM ('new','confirmed','in_production','shipped','delivered','cancelled')")
    op.execute("CREATE TYPE production_status_enum AS ENUM ('pending','in_production','quality_check','ready_to_ship','shipped','delivered')")
    op.execute("CREATE TYPE incoterms_enum AS ENUM ('EXW','FCA','FOB','CFR','CIF','DAP','DDP')")
    op.execute("CREATE TYPE followup_type_enum AS ENUM ('call','email','meeting','send_sample','send_quote','follow_up','check_in')")
    op.execute("CREATE TYPE followup_priority_enum AS ENUM ('high','medium','low')")

    # ── crm_leads ──────────────────────────────────────────────────────────────
    op.create_table(
        "crm_leads",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(36), unique=True, nullable=False),
        sa.Column("canonical_buyer_id", sa.BigInteger(), nullable=True),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("country_code", sa.String(3)),
        sa.Column("country_name", sa.String(128)),
        sa.Column("contact_name", sa.Text()),
        sa.Column("contact_title", sa.String(128)),
        sa.Column("contact_email", sa.Text()),
        sa.Column("contact_phone", sa.String(50)),
        sa.Column("contact_linkedin", sa.Text()),
        sa.Column("contact_whatsapp", sa.String(50)),
        sa.Column("status", sa.Text(), nullable=False, server_default="new"),
        sa.Column("source", sa.Text(), nullable=False, server_default="database"),
        sa.Column("priority", sa.Text(), nullable=False, server_default="warm"),
        sa.Column("assigned_to", sa.String(128)),
        sa.Column("product_interest", sa.dialects.postgresql.JSONB()),
        sa.Column("estimated_value_usd", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(3), server_default="USD"),
        sa.Column("last_contact_date", sa.Date()),
        sa.Column("expected_close_date", sa.Date()),
        sa.Column("notes_count", sa.Integer(), server_default="0"),
        sa.Column("interactions_count", sa.Integer(), server_default="0"),
        sa.Column("open_followups", sa.Integer(), server_default="0"),
        sa.Column("tags", sa.dialects.postgresql.JSONB()),
        sa.Column("extra", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_leads_status", "crm_leads", ["status"])
    op.create_index("ix_crm_leads_priority", "crm_leads", ["priority"])
    op.create_index("ix_crm_leads_assigned", "crm_leads", ["assigned_to"])
    op.create_index("ix_crm_leads_canonical", "crm_leads", ["canonical_buyer_id"])

    # ── crm_contacts ───────────────────────────────────────────────────────────
    op.create_table(
        "crm_contacts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("canonical_buyer_id", sa.BigInteger()),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("title", sa.String(128)),
        sa.Column("department", sa.String(128)),
        sa.Column("email", sa.Text()),
        sa.Column("phone", sa.String(50)),
        sa.Column("whatsapp", sa.String(50)),
        sa.Column("linkedin_url", sa.Text()),
        sa.Column("is_primary", sa.Boolean(), server_default="false"),
        sa.Column("preferred_contact_method", sa.String(20)),
        sa.Column("language", sa.String(10)),
        sa.Column("timezone", sa.String(64)),
        sa.Column("do_not_contact", sa.Boolean(), server_default="false"),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_contacts_lead", "crm_contacts", ["lead_id"])
    op.create_index("ix_crm_contacts_email", "crm_contacts", ["email"])

    # ── crm_contact_history ────────────────────────────────────────────────────
    op.create_table(
        "crm_contact_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("contact_id", sa.BigInteger()),
        sa.Column("opportunity_id", sa.BigInteger()),
        sa.Column("interaction_type", sa.Text(), nullable=False),
        sa.Column("direction", sa.String(10), server_default="outbound"),
        sa.Column("subject", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("outcome", sa.Text()),
        sa.Column("next_action", sa.Text()),
        sa.Column("duration_minutes", sa.SmallInteger()),
        sa.Column("interacted_by", sa.String(128)),
        sa.Column("attachments", sa.dialects.postgresql.JSONB()),
        sa.Column("interacted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_history_lead", "crm_contact_history", ["lead_id"])
    op.create_index("ix_crm_history_date", "crm_contact_history", ["interacted_at"])

    # ── crm_notes ──────────────────────────────────────────────────────────────
    op.create_table(
        "crm_notes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("opportunity_id", sa.BigInteger()),
        sa.Column("contact_id", sa.BigInteger()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("note_type", sa.String(32), server_default="general"),
        sa.Column("created_by", sa.String(128)),
        sa.Column("is_pinned", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_notes_lead", "crm_notes", ["lead_id"])
    op.create_index("ix_crm_notes_pinned", "crm_notes", ["is_pinned"])

    # ── crm_followups ──────────────────────────────────────────────────────────
    op.create_table(
        "crm_followups",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("opportunity_id", sa.BigInteger()),
        sa.Column("contact_id", sa.BigInteger()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("follow_up_type", sa.Text(), server_default="follow_up"),
        sa.Column("priority", sa.Text(), server_default="medium"),
        sa.Column("assigned_to", sa.String(128)),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("is_completed", sa.Boolean(), server_default="false"),
        sa.Column("outcome_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_followups_lead", "crm_followups", ["lead_id"])
    op.create_index("ix_crm_followups_due", "crm_followups", ["scheduled_at", "is_completed"])

    # ── crm_opportunities ──────────────────────────────────────────────────────
    op.create_table(
        "crm_opportunities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(36), unique=True, nullable=False),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), server_default="prospecting"),
        sa.Column("probability_pct", sa.SmallInteger(), server_default="20"),
        sa.Column("estimated_value_usd", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(3), server_default="USD"),
        sa.Column("products", sa.dialects.postgresql.JSONB()),
        sa.Column("quantity_kg", sa.Numeric(12, 2)),
        sa.Column("incoterms", sa.Text()),
        sa.Column("payment_terms", sa.String(128)),
        sa.Column("expected_close_date", sa.Date()),
        sa.Column("actual_close_date", sa.Date()),
        sa.Column("won_at", sa.DateTime(timezone=True)),
        sa.Column("lost_at", sa.DateTime(timezone=True)),
        sa.Column("lost_reason", sa.Text()),
        sa.Column("assigned_to", sa.String(128)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_opp_lead", "crm_opportunities", ["lead_id"])
    op.create_index("ix_crm_opp_stage", "crm_opportunities", ["stage"])

    # ── crm_samples ────────────────────────────────────────────────────────────
    op.create_table(
        "crm_samples",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("sample_number", sa.String(64), unique=True, nullable=False),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("opportunity_id", sa.BigInteger()),
        sa.Column("products", sa.dialects.postgresql.JSONB()),
        sa.Column("quantity_pieces", sa.Integer()),
        sa.Column("weight_kg", sa.Numeric(8, 3)),
        sa.Column("courier", sa.String(64)),
        sa.Column("tracking_number", sa.String(128)),
        sa.Column("sent_date", sa.Date()),
        sa.Column("estimated_delivery", sa.Date()),
        sa.Column("delivered_date", sa.Date()),
        sa.Column("status", sa.Text(), server_default="preparing"),
        sa.Column("cost_inr", sa.Numeric(12, 2)),
        sa.Column("cost_usd", sa.Numeric(10, 2)),
        sa.Column("paid_by_buyer", sa.Boolean(), server_default="false"),
        sa.Column("feedback", sa.Text()),
        sa.Column("feedback_date", sa.Date()),
        sa.Column("approved_for_bulk", sa.Boolean()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_samples_lead", "crm_samples", ["lead_id"])
    op.create_index("ix_crm_samples_status", "crm_samples", ["status"])

    # ── crm_quotations ─────────────────────────────────────────────────────────
    op.create_table(
        "crm_quotations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("quotation_number", sa.String(64), unique=True, nullable=False),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("opportunity_id", sa.BigInteger()),
        sa.Column("line_items", sa.dialects.postgresql.JSONB()),
        sa.Column("currency", sa.String(3), server_default="USD"),
        sa.Column("total_value", sa.Numeric(18, 2)),
        sa.Column("incoterms", sa.Text()),
        sa.Column("payment_terms", sa.String(256)),
        sa.Column("validity_days", sa.SmallInteger(), server_default="30"),
        sa.Column("delivery_weeks", sa.SmallInteger()),
        sa.Column("port_of_loading", sa.String(128)),
        sa.Column("port_of_discharge", sa.String(128)),
        sa.Column("packing_details", sa.Text()),
        sa.Column("special_terms", sa.Text()),
        sa.Column("status", sa.Text(), server_default="draft"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.Date()),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("profitability", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_quot_lead", "crm_quotations", ["lead_id"])
    op.create_index("ix_crm_quot_status", "crm_quotations", ["status"])

    # ── crm_purchase_orders ────────────────────────────────────────────────────
    op.create_table(
        "crm_purchase_orders",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("po_number", sa.String(128), nullable=False),
        sa.Column("our_reference", sa.String(64), unique=True, nullable=False),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("opportunity_id", sa.BigInteger()),
        sa.Column("quotation_id", sa.BigInteger()),
        sa.Column("line_items", sa.dialects.postgresql.JSONB()),
        sa.Column("currency", sa.String(3), server_default="USD"),
        sa.Column("total_value", sa.Numeric(18, 2)),
        sa.Column("advance_pct", sa.Numeric(5, 2)),
        sa.Column("advance_amount", sa.Numeric(18, 2)),
        sa.Column("advance_received_date", sa.Date()),
        sa.Column("balance_amount", sa.Numeric(18, 2)),
        sa.Column("balance_due_date", sa.Date()),
        sa.Column("balance_received_date", sa.Date()),
        sa.Column("payment_terms", sa.String(256)),
        sa.Column("lc_number", sa.String(128)),
        sa.Column("incoterms", sa.Text()),
        sa.Column("shipping_port", sa.String(128)),
        sa.Column("destination_port", sa.String(128)),
        sa.Column("country_of_destination", sa.String(3)),
        sa.Column("bl_number", sa.String(128)),
        sa.Column("container_number", sa.String(64)),
        sa.Column("production_status", sa.Text(), server_default="pending"),
        sa.Column("expected_production_days", sa.SmallInteger()),
        sa.Column("production_start_date", sa.Date()),
        sa.Column("production_end_date", sa.Date()),
        sa.Column("shipment_date", sa.Date()),
        sa.Column("delivery_date", sa.Date()),
        sa.Column("status", sa.Text(), server_default="new"),
        sa.Column("documents", sa.dialects.postgresql.JSONB()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_crm_po_lead", "crm_purchase_orders", ["lead_id"])
    op.create_index("ix_crm_po_status", "crm_purchase_orders", ["status"])
    op.create_index("ix_crm_po_prod_status", "crm_purchase_orders", ["production_status"])
    op.create_unique_constraint("uq_po_number_lead", "crm_purchase_orders", ["po_number", "lead_id"])


def downgrade() -> None:
    for tbl in [
        "crm_purchase_orders", "crm_quotations", "crm_samples",
        "crm_opportunities", "crm_followups", "crm_notes",
        "crm_contact_history", "crm_contacts", "crm_leads",
    ]:
        op.drop_table(tbl)
    for enum in [
        "lead_status_enum", "lead_source_enum", "lead_priority_enum",
        "interaction_type_enum", "interaction_outcome_enum",
        "opportunity_stage_enum", "sample_status_enum",
        "quotation_status_enum", "po_status_enum", "production_status_enum",
        "incoterms_enum", "followup_type_enum", "followup_priority_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
