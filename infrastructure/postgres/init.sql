-- PostgreSQL initialization: extensions + performance settings
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Optimized full-text search configuration for trade data
CREATE TEXT SEARCH CONFIGURATION brass_en (COPY = english);
