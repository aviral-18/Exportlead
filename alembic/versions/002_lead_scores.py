"""Add lead_scores table

Revision ID: 002_lead_scores
Revises: 001_initial_schema
Create Date: 2026-06-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "002_lead_scores"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_scores",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("canonical_id", sa.BigInteger(), nullable=False),
        sa.Column("india_import_probability", sa.Numeric(6, 2), nullable=True),
        sa.Column("supplier_switch_probability", sa.Numeric(6, 2), nullable=True),
        sa.Column("product_fit_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("growth_trend_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("new_importer_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("import_activity_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("composite_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("tier", sa.String(1), nullable=True),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_id", name="uq_lead_scores_canonical"),
        sa.ForeignKeyConstraint(
            ["canonical_id"],
            ["canonical_buyers.id"],
            name="fk_lead_scores_canonical",
            ondelete="CASCADE",
        ),
    )

    op.create_index("ix_lead_scores_canonical_id", "lead_scores", ["canonical_id"], unique=True)
    op.create_index("ix_lead_scores_composite", "lead_scores", ["composite_score"])
    op.create_index("ix_lead_scores_india_prob", "lead_scores", ["india_import_probability"])
    op.create_index("ix_lead_scores_growth", "lead_scores", ["growth_trend_score"])
    op.create_index("ix_lead_scores_new_importer", "lead_scores", ["new_importer_score"])
    op.create_index("ix_lead_scores_tier", "lead_scores", ["tier"])


def downgrade() -> None:
    op.drop_table("lead_scores")
