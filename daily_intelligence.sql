SELECT current_database(), current_schema();
SELECT id, name, category, trust_tier, active
FROM sources
ORDER BY id;

--Checking the number of articles
SELECT COUNT(*) FROM articles;

--limiting the articles to 20
SELECT
    a.id,
    s.name AS source,
    a.title,
    a.published_at
FROM articles a
JOIN sources s
    ON a.source_id = s.id
ORDER BY a.published_at DESC
LIMIT 20;

--1. Number of articles by source
SELECT
    s.name,
    COUNT(*) AS articles
FROM articles a
JOIN sources s
    ON a.source_id = s.id
GROUP BY s.name
ORDER BY articles DESC;

--2. Check date coverage
SELECT
    s.name,
    MIN(a.published_at) AS oldest_article,
    MAX(a.published_at) AS newest_article,
    COUNT(*) AS articles
FROM articles a
JOIN sources s
    ON a.source_id = s.id
GROUP BY s.name
ORDER BY s.name;

--3. Check for duplicate canonical URLs
SELECT
    canonical_url,
    COUNT(*)
FROM articles
GROUP BY canonical_url
HAVING COUNT(*) > 1;

--4. Check missing fields
SELECT
    COUNT(*) AS total_articles,
    COUNT(*) FILTER (WHERE title IS NULL OR title = '') AS missing_title,
    COUNT(*) FILTER (WHERE canonical_url IS NULL OR canonical_url = '') AS missing_url,
    COUNT(*) FILTER (WHERE published_at IS NULL) AS missing_date,
    COUNT(*) FILTER (WHERE raw_summary IS NULL OR raw_summary = '') AS missing_summary
FROM articles;

SELECT
    s.name,
    a.title,
    a.published_at,
    a.canonical_url
FROM articles a
JOIN sources s
    ON a.source_id = s.id
WHERE a.published_at > NOW()
ORDER BY a.published_at;

--This query will expose all registered sources even when their article count is zero:
SELECT
    s.id,
    s.name,
    s.feed_url,
    s.active,
    COUNT(a.id) AS stored_articles
FROM sources s
LEFT JOIN articles a
    ON a.source_id = s.id
GROUP BY
    s.id,
    s.name,
    s.feed_url,
    s.active
ORDER BY stored_articles DESC;

--Check for OpenAI articels 
SELECT
    DATE_TRUNC('year', published_at) AS year,
    COUNT(*) AS articles
FROM articles a
JOIN sources s ON a.source_id = s.id
WHERE s.name = 'OpenAI'
GROUP BY DATE_TRUNC('year', published_at)
ORDER BY year;
--Checking the sources there type, active or not, and category
SELECT
    id,
    name,
    source_type,
    active,
    category
FROM sources
ORDER BY id;

--new Google source exists in PostgreSQL:
SELECT
    s.name,
    s.source_type,
    s.active,
    COUNT(a.id) AS stored_articles
FROM sources s
LEFT JOIN articles a
    ON a.source_id = s.id
GROUP BY
    s.id,
    s.name,
    s.source_type,
    s.active
ORDER BY stored_articles DESC;

SELECT COUNT(*) FROM articles;
SELECT
    s.name,
    COUNT(a.id) AS stored_articles
FROM sources s
LEFT JOIN articles a ON a.source_id = s.id
GROUP BY s.id, s.name
ORDER BY stored_articles DESC;

ALTER TABLE articles
ADD COLUMN IF NOT EXISTS primary_category VARCHAR(100);

ALTER TABLE articles
ADD COLUMN IF NOT EXISTS regions TEXT;

ALTER TABLE articles
ADD COLUMN IF NOT EXISTS groups TEXT;

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'articles'
ORDER BY ordinal_position;