-- ============================================================
-- Database health / identity checks
-- ============================================================

SELECT
    current_database() AS database_name,
    current_schema() AS schema_name;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

SELECT COUNT(*) AS total_articles
FROM articles;

SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'articles'
ORDER BY ordinal_position;
