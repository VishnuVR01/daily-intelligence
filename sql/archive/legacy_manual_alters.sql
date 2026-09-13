-- ============================================================
-- LEGACY / DO NOT RUN ON THE CURRENT DATABASE
-- ============================================================
-- These statements were previously used manually while the schema
-- was evolving.
--
-- The project now uses Alembic migrations. Future schema changes
-- must be represented by an Alembic revision instead.
-- ============================================================

ALTER TABLE articles
ADD COLUMN IF NOT EXISTS primary_category VARCHAR(100);

ALTER TABLE articles
ADD COLUMN IF NOT EXISTS regions TEXT;

ALTER TABLE articles
ADD COLUMN IF NOT EXISTS groups TEXT;
