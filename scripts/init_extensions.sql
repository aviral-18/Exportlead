-- PostgreSQL extensions required by BrassExport Intelligence
-- Run automatically on first container start via docker-entrypoint-initdb.d

CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- fuzzy string matching
CREATE EXTENSION IF NOT EXISTS btree_gin;       -- combined GIN indexes
CREATE EXTENSION IF NOT EXISTS pg_stat_statements; -- query performance
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";    -- UUID generation fallback
CREATE EXTENSION IF NOT EXISTS unaccent;       -- accent-insensitive search

-- Set similarity threshold for trigram index (lower = more results)
SET pg_trgm.similarity_threshold = 0.3;

-- Optimise for large dataset
ALTER SYSTEM SET work_mem = '64MB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';
ALTER SYSTEM SET random_page_cost = 1.1;
