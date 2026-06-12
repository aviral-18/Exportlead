"""
004 — Growth engine, outreach, and intelligence tables.

Adds:
  - discovery_runs
  - growth_opportunities
  - daily_recommendations
  - emerging_importers
  - deal_probability_scores
  - export_forecasts
  - outreach_campaigns
  - outreach_emails
  - email_replies
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── discovery_runs ────────────────────────────────────────────────────────
    op.create_table(
        "discovery_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("sources_queried", sa.Integer(), server_default="0"),
        sa.Column("raw_records_scanned", sa.Integer(), server_default="0"),
        sa.Column("new_buyers_found", sa.Integer(), server_default="0"),
        sa.Column("existing_buyers_updated", sa.Integer(), server_default="0"),
        sa.Column("scored", sa.Integer(), server_default="0"),
        sa.Column("opportunities_created", sa.Integer(), server_default="0"),
        sa.Column("emerging_flagged", sa.Integer(), server_default="0"),
        sa.Column("top_opportunity_score", sa.Numeric(6, 2)),
        sa.Column("run_duration_seconds", sa.Numeric(10, 3)),
        sa.Column("error_message", sa.Text()),
        sa.Column("metadata_json", sa.Text()),
    )
    op.create_index("ix_discovery_runs_run_at", "discovery_runs", ["run_at"])

    # ── growth_opportunities ──────────────────────────────────────────────────
    op.create_table(
        "growth_opportunities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("canonical_id", sa.BigInteger(), sa.ForeignKey("canonical_buyers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("discovery_run_id", sa.BigInteger(), sa.ForeignKey("discovery_runs.id", ondelete="SET NULL")),
        sa.Column("opportunity_score", sa.Numeric(6, 2)),
        sa.Column("rank_position", sa.Integer()),
        sa.Column("country_code", sa.String(3)),
        sa.Column("buyer_type", sa.String(64)),
        sa.Column("estimated_value_usd", sa.Numeric(20, 2)),
        sa.Column("india_import_probability", sa.Numeric(6, 2)),
        sa.Column("product_fit_score", sa.Numeric(6, 2)),
        sa.Column("competitive_gap_score", sa.Numeric(6, 2)),
        sa.Column("market_timing_score", sa.Numeric(6, 2)),
        sa.Column("country_market_score", sa.Numeric(6, 2)),
        sa.Column("is_new_discovery", sa.Boolean(), server_default="false"),
        sa.Column("is_emerging", sa.Boolean(), server_default="false"),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reasoning", sa.Text()),
        sa.Column("market_signals_json", sa.Text()),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("crm_lead_id", sa.BigInteger()),
        sa.Column("dismissed_at", sa.DateTime(timezone=True)),
        sa.Column("added_to_crm_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_growth_opportunities_canonical_id", "growth_opportunities", ["canonical_id"])
    op.create_index("ix_growth_opportunities_opportunity_score", "growth_opportunities", ["opportunity_score"])
    op.create_index("ix_growth_opportunities_status", "growth_opportunities", ["status"])
    op.create_index("ix_growth_opportunities_country_code", "growth_opportunities", ["country_code"])

    # ── daily_recommendations ─────────────────────────────────────────────────
    op.create_table(
        "daily_recommendations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.String(10), nullable=False),
        sa.Column("discovery_run_id", sa.BigInteger()),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("canonical_id", sa.BigInteger(), sa.ForeignKey("canonical_buyers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_score", sa.Numeric(6, 2)),
        sa.Column("composite_lead_score", sa.Numeric(6, 2)),
        sa.Column("reasoning", sa.Text()),
        sa.Column("key_signals_json", sa.Text()),
        sa.Column("action_type", sa.String(32)),
        sa.Column("email_template", sa.String(64)),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("acted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_daily_recommendations_run_date", "daily_recommendations", ["run_date"])

    # ── emerging_importers ────────────────────────────────────────────────────
    op.create_table(
        "emerging_importers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("canonical_id", sa.BigInteger(), sa.ForeignKey("canonical_buyers.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("first_import_date", sa.String(10)),
        sa.Column("months_active", sa.Integer()),
        sa.Column("shipment_count", sa.Integer()),
        sa.Column("annual_volume_usd", sa.Numeric(20, 2)),
        sa.Column("growth_velocity_score", sa.Numeric(6, 2)),
        sa.Column("market_timing_score", sa.Numeric(6, 2)),
        sa.Column("overall_score", sa.Numeric(6, 2)),
        sa.Column("category", sa.String(64)),
        sa.Column("trend_json", sa.Text()),
        sa.Column("action_recommended", sa.String(64)),
        sa.Column("confidence", sa.String(16)),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("crm_lead_id", sa.BigInteger()),
    )
    op.create_index("ix_emerging_importers_canonical_id", "emerging_importers", ["canonical_id"], unique=True)

    # ── deal_probability_scores ───────────────────────────────────────────────
    op.create_table(
        "deal_probability_scores",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("opportunity_id", sa.BigInteger(), sa.ForeignKey("crm_opportunities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", sa.BigInteger()),
        sa.Column("probability_pct", sa.Numeric(5, 2)),
        sa.Column("confidence_level", sa.String(16)),
        sa.Column("days_to_close_est", sa.Integer()),
        sa.Column("expected_value_usd", sa.Numeric(20, 2)),
        sa.Column("weighted_value_usd", sa.Numeric(20, 2)),
        sa.Column("positive_signals_json", sa.Text()),
        sa.Column("risk_factors_json", sa.Text()),
        sa.Column("scoring_breakdown_json", sa.Text()),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_current", sa.Boolean(), server_default="true"),
    )
    op.create_index("ix_deal_probability_opportunity_id", "deal_probability_scores", ["opportunity_id"])
    op.create_index("ix_deal_probability_is_current", "deal_probability_scores", ["is_current"])

    # ── export_forecasts ──────────────────────────────────────────────────────
    op.create_table(
        "export_forecasts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("forecast_month", sa.String(7), nullable=False),
        sa.Column("base_case_usd", sa.Numeric(20, 2)),
        sa.Column("upside_case_usd", sa.Numeric(20, 2)),
        sa.Column("downside_case_usd", sa.Numeric(20, 2)),
        sa.Column("confirmed_usd", sa.Numeric(20, 2)),
        sa.Column("weighted_pipeline_usd", sa.Numeric(20, 2)),
        sa.Column("seasonal_factor", sa.Numeric(5, 4)),
        sa.Column("active_opportunities", sa.Integer()),
        sa.Column("avg_close_probability", sa.Numeric(5, 2)),
        sa.Column("opportunities_json", sa.Text()),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_current", sa.Boolean(), server_default="true"),
        sa.Column("notes", sa.Text()),
    )
    op.create_index("ix_export_forecasts_forecast_month", "export_forecasts", ["forecast_month"])
    op.create_index("ix_export_forecasts_is_current", "export_forecasts", ["is_current"])

    # ── outreach_campaigns ────────────────────────────────────────────────────
    op.create_table(
        "outreach_campaigns",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("campaign_type", sa.String(32), server_default="cold_outreach"),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("target_country", sa.String(3)),
        sa.Column("target_buyer_type", sa.String(64)),
        sa.Column("target_tier", sa.String(2)),
        sa.Column("min_score", sa.Numeric(5, 2)),
        sa.Column("template_name", sa.String(64)),
        sa.Column("language", sa.String(5), server_default="en"),
        sa.Column("emails_sent", sa.Integer(), server_default="0"),
        sa.Column("emails_opened", sa.Integer(), server_default="0"),
        sa.Column("emails_clicked", sa.Integer(), server_default="0"),
        sa.Column("replies_received", sa.Integer(), server_default="0"),
        sa.Column("positive_replies", sa.Integer(), server_default="0"),
        sa.Column("crm_leads_created", sa.Integer(), server_default="0"),
        sa.Column("open_rate", sa.Numeric(5, 2)),
        sa.Column("reply_rate", sa.Numeric(5, 2)),
        sa.Column("conversion_rate", sa.Numeric(5, 2)),
        sa.Column("start_date", sa.String(10)),
        sa.Column("end_date", sa.String(10)),
        sa.Column("created_by", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_outreach_campaigns_status", "outreach_campaigns", ["status"])
    op.create_index("ix_outreach_campaigns_target_country", "outreach_campaigns", ["target_country"])

    # ── outreach_emails ───────────────────────────────────────────────────────
    op.create_table(
        "outreach_emails",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("campaign_id", sa.BigInteger(), sa.ForeignKey("outreach_campaigns.id", ondelete="SET NULL")),
        sa.Column("lead_id", sa.BigInteger(), sa.ForeignKey("crm_leads.id", ondelete="SET NULL")),
        sa.Column("canonical_id", sa.BigInteger(), sa.ForeignKey("canonical_buyers.id", ondelete="SET NULL")),
        sa.Column("to_email", sa.String(512), nullable=False),
        sa.Column("to_name", sa.String(256)),
        sa.Column("to_company", sa.String(512)),
        sa.Column("to_country", sa.String(3)),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text()),
        sa.Column("template_name", sa.String(64)),
        sa.Column("language", sa.String(5), server_default="en"),
        sa.Column("personalization_json", sa.Text()),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
        sa.Column("clicked_at", sa.DateTime(timezone=True)),
        sa.Column("open_count", sa.Integer(), server_default="0"),
        sa.Column("click_count", sa.Integer(), server_default="0"),
        sa.Column("reply_received", sa.Boolean(), server_default="false"),
        sa.Column("reply_id", sa.BigInteger()),
        sa.Column("bounce_reason", sa.String(256)),
        sa.Column("message_id", sa.String(256), unique=True),
        sa.Column("tracking_pixel_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_outreach_emails_campaign_id", "outreach_emails", ["campaign_id"])
    op.create_index("ix_outreach_emails_lead_id", "outreach_emails", ["lead_id"])
    op.create_index("ix_outreach_emails_canonical_id", "outreach_emails", ["canonical_id"])
    op.create_index("ix_outreach_emails_status", "outreach_emails", ["status"])

    # ── email_replies ─────────────────────────────────────────────────────────
    op.create_table(
        "email_replies",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("outreach_email_id", sa.BigInteger(), sa.ForeignKey("outreach_emails.id", ondelete="SET NULL")),
        sa.Column("campaign_id", sa.BigInteger(), sa.ForeignKey("outreach_campaigns.id", ondelete="SET NULL")),
        sa.Column("lead_id", sa.BigInteger(), sa.ForeignKey("crm_leads.id", ondelete="SET NULL")),
        sa.Column("from_email", sa.String(512), nullable=False),
        sa.Column("from_name", sa.String(256)),
        sa.Column("subject", sa.String(512)),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("sentiment", sa.String(32)),
        sa.Column("intent", sa.String(32)),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("extracted_signals_json", sa.Text()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("is_processed", sa.Boolean(), server_default="false"),
        sa.Column("crm_history_id", sa.BigInteger()),
        sa.Column("auto_response_sent", sa.Boolean(), server_default="false"),
        sa.Column("auto_response_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_email_replies_outreach_email_id", "email_replies", ["outreach_email_id"])
    op.create_index("ix_email_replies_campaign_id", "email_replies", ["campaign_id"])
    op.create_index("ix_email_replies_lead_id", "email_replies", ["lead_id"])
    op.create_index("ix_email_replies_sentiment", "email_replies", ["sentiment"])
    op.create_index("ix_email_replies_intent", "email_replies", ["intent"])


def downgrade() -> None:
    for tbl in [
        "email_replies", "outreach_emails", "outreach_campaigns",
        "export_forecasts", "deal_probability_scores", "emerging_importers",
        "daily_recommendations", "growth_opportunities", "discovery_runs",
    ]:
        op.drop_table(tbl)
