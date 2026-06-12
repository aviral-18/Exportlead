"""Initial schema with partitioned raw_buyers table.

Revision ID: 001
Revises:
Create Date: 2026-06-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gin")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")

    # ── Enum types ────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE data_source_enum AS ENUM (
                'volza','import_yeti','un_comtrade','trade_map','export_genius',
                'datamyne','panjiva','india_export_data',
                'alibaba','global_sources','tradekey','ec21','eworldtrade',
                'tradeindia','indiamart','made_in_china',
                'sam_gov','ted_europa','ungm','world_bank','adb',
                'ambiente','maison_objet','ny_now','ihgf'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE buyer_type_enum AS ENUM (
                'importer','distributor','wholesaler','retailer',
                'procurement_agency','hospitality','sourcing_company',
                'oem','government','ngo','unknown'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE import_frequency_enum AS ENUM (
                'daily','weekly','monthly','quarterly','annual','sporadic','unknown'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE ingestion_status_enum AS ENUM (
                'pending','running','completed','failed','partial'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    # ── raw_buyers — partitioned by HASH(id), 32 partitions ──────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS raw_buyers (
            id                          BIGSERIAL,
            external_id                 TEXT,
            data_source                 data_source_enum NOT NULL,
            ingestion_run_id            BIGINT,
            company_name                TEXT NOT NULL,
            company_name_normalized     TEXT,
            company_name_tokens         TEXT,
            country_code                CHAR(3),
            country_name                TEXT,
            state_province              TEXT,
            city                        TEXT,
            postal_code                 VARCHAR(32),
            address                     TEXT,
            website                     TEXT,
            website_domain              VARCHAR(256),
            email                       TEXT[],
            phone                       TEXT[],
            contact_person              TEXT,
            product_categories          TEXT[],
            hs_codes                    TEXT[],
            product_description         TEXT,
            buyer_type                  buyer_type_enum,
            import_frequency            import_frequency_enum,
            estimated_annual_volume_usd NUMERIC(20,2),
            volume_currency             VARCHAR(3),
            last_import_date            DATE,
            first_import_date           DATE,
            total_shipments             INTEGER,
            total_suppliers             INTEGER,
            confidence_score            NUMERIC(5,4) DEFAULT 0.5,
            is_duplicate                BOOLEAN DEFAULT FALSE,
            canonical_id                BIGINT,
            raw_data                    JSONB,
            created_at                  TIMESTAMPTZ DEFAULT NOW(),
            updated_at                  TIMESTAMPTZ DEFAULT NOW()
        ) PARTITION BY HASH (id)
    """)

    # Create 32 hash partitions
    for i in range(32):
        op.execute(f"""
            CREATE TABLE IF NOT EXISTS raw_buyers_p{i:02d}
            PARTITION OF raw_buyers
            FOR VALUES WITH (modulus 32, remainder {i})
        """)

    # Primary key across all partitions
    op.execute("""
        ALTER TABLE raw_buyers ADD CONSTRAINT raw_buyers_pkey
        PRIMARY KEY (id)
    """)

    # ── Indexes on raw_buyers ─────────────────────────────────────────────────
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_raw_buyers_source_external
        ON raw_buyers (data_source, external_id)
        WHERE external_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_raw_buyers_country_type
        ON raw_buyers (country_code, buyer_type)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_raw_buyers_domain
        ON raw_buyers (website_domain)
        WHERE website_domain IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_raw_buyers_canonical
        ON raw_buyers (canonical_id)
        WHERE canonical_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_raw_buyers_name_trgm
        ON raw_buyers USING GIN (company_name_normalized gin_trgm_ops)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_raw_buyers_hs_codes
        ON raw_buyers USING GIN (hs_codes)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_raw_buyers_categories
        ON raw_buyers USING GIN (product_categories)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_raw_buyers_last_import
        ON raw_buyers (last_import_date)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_raw_buyers_data_source
        ON raw_buyers (data_source)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_raw_buyers_is_duplicate
        ON raw_buyers (is_duplicate)
        WHERE is_duplicate = FALSE
    """)

    # updated_at trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ language 'plpgsql'
    """)
    op.execute("""
        CREATE TRIGGER update_raw_buyers_updated_at
        BEFORE UPDATE ON raw_buyers
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)

    # ── canonical_buyers ──────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS canonical_buyers (
            id                          BIGSERIAL PRIMARY KEY,
            uuid                        UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
            company_name                TEXT NOT NULL,
            company_name_normalized     TEXT,
            trade_name                  TEXT,
            country_code                CHAR(3),
            country_name                TEXT,
            state_province              TEXT,
            city                        TEXT,
            address                     TEXT,
            website                     TEXT,
            website_domain              VARCHAR(256) UNIQUE,
            email                       TEXT[],
            phone                       TEXT[],
            product_categories          TEXT[],
            hs_codes                    TEXT[],
            buyer_type                  buyer_type_enum,
            import_frequency            import_frequency_enum,
            estimated_annual_volume_usd NUMERIC(20,2),
            last_import_date            DATE,
            first_import_date           DATE,
            total_shipments             INTEGER,
            source_count                INTEGER DEFAULT 1,
            data_sources                TEXT[],
            confidence_score            NUMERIC(5,4) DEFAULT 0.5,
            is_verified                 BOOLEAN DEFAULT FALSE,
            is_active                   BOOLEAN DEFAULT TRUE,
            linkedin_url                TEXT,
            description                 TEXT,
            employee_count              INTEGER,
            annual_revenue_usd          NUMERIC(20,2),
            founded_year                SMALLINT,
            extra                       JSONB,
            created_at                  TIMESTAMPTZ DEFAULT NOW(),
            updated_at                  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_canonical_name_trgm
        ON canonical_buyers USING GIN (company_name_normalized gin_trgm_ops)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_canonical_hs_codes
        ON canonical_buyers USING GIN (hs_codes)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_canonical_country_type
        ON canonical_buyers (country_code, buyer_type)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_canonical_confidence
        ON canonical_buyers (confidence_score DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_canonical_active
        ON canonical_buyers (is_active)
        WHERE is_active = TRUE
    """)
    op.execute("""
        CREATE TRIGGER update_canonical_buyers_updated_at
        BEFORE UPDATE ON canonical_buyers
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)

    # ── buyer_source_links ────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS buyer_source_links (
            id               BIGSERIAL PRIMARY KEY,
            canonical_id     BIGINT NOT NULL REFERENCES canonical_buyers(id) ON DELETE CASCADE,
            raw_buyer_id     BIGINT NOT NULL,
            data_source      VARCHAR(64) NOT NULL,
            match_confidence NUMERIC(5,4),
            created_at       TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_link_canonical_raw UNIQUE (canonical_id, raw_buyer_id)
        )
    """)
    op.execute("CREATE INDEX ix_links_canonical ON buyer_source_links (canonical_id)")
    op.execute("CREATE INDEX ix_links_raw ON buyer_source_links (raw_buyer_id)")

    # ── dedup_candidates ──────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS dedup_candidates (
            id              BIGSERIAL PRIMARY KEY,
            id_a            BIGINT NOT NULL,
            id_b            BIGINT NOT NULL,
            name_similarity NUMERIC(5,4),
            domain_match    BOOLEAN DEFAULT FALSE,
            country_match   BOOLEAN DEFAULT FALSE,
            combined_score  NUMERIC(5,4),
            resolved        BOOLEAN DEFAULT FALSE,
            is_match        BOOLEAN,
            reviewed_by     VARCHAR(128),
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_dedup_pair UNIQUE (id_a, id_b)
        )
    """)
    op.execute("CREATE INDEX ix_dedup_score ON dedup_candidates (combined_score DESC)")
    op.execute("""
        CREATE INDEX ix_dedup_unresolved ON dedup_candidates (resolved)
        WHERE resolved = FALSE
    """)

    # ── ingestion_runs ────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_runs (
            id               BIGSERIAL PRIMARY KEY,
            data_source      VARCHAR(64) NOT NULL,
            status           ingestion_status_enum DEFAULT 'pending',
            records_fetched  INTEGER DEFAULT 0,
            records_inserted INTEGER DEFAULT 0,
            records_updated  INTEGER DEFAULT 0,
            records_skipped  INTEGER DEFAULT 0,
            error_message    TEXT,
            metadata         JSONB,
            started_at       TIMESTAMPTZ,
            completed_at     TIMESTAMPTZ,
            created_at       TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_runs_source ON ingestion_runs (data_source)")
    op.execute("CREATE INDEX ix_runs_status ON ingestion_runs (status)")

    # ── scraper_checkpoints ───────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS scraper_checkpoints (
            id                   SERIAL PRIMARY KEY,
            data_source          VARCHAR(64) NOT NULL UNIQUE,
            checkpoint_data      JSONB NOT NULL,
            last_successful_page INTEGER,
            updated_at           TIMESTAMPTZ DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    for i in range(32):
        op.execute(f"DROP TABLE IF EXISTS raw_buyers_p{i:02d} CASCADE")
    op.execute("DROP TABLE IF EXISTS raw_buyers CASCADE")
    op.execute("DROP TABLE IF EXISTS canonical_buyers CASCADE")
    op.execute("DROP TABLE IF EXISTS buyer_source_links CASCADE")
    op.execute("DROP TABLE IF EXISTS dedup_candidates CASCADE")
    op.execute("DROP TABLE IF EXISTS ingestion_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS scraper_checkpoints CASCADE")
    op.execute("DROP TYPE IF EXISTS data_source_enum")
    op.execute("DROP TYPE IF EXISTS buyer_type_enum")
    op.execute("DROP TYPE IF EXISTS import_frequency_enum")
    op.execute("DROP TYPE IF EXISTS ingestion_status_enum")
