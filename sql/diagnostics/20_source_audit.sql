-- ============================================================
-- Source registry / ingestion coverage
-- ============================================================

SELECT
    id,
    name,
    source_type,
    category,
    trust_tier,
    active
FROM sources
ORDER BY id;

SELECT
    s.id,
    s.name,
    s.feed_url,
    s.source_type,
    s.active,
    COUNT(a.id) AS stored_articles
FROM sources s
LEFT JOIN articles a
    ON a.source_id = s.id
GROUP BY
    s.id,
    s.name,
    s.feed_url,
    s.source_type,
    s.active
ORDER BY stored_articles DESC, s.name;

SELECT
    s.name,
    COUNT(*) AS article_count
FROM articles a
JOIN sources s
    ON a.source_id = s.id
GROUP BY s.name
ORDER BY article_count DESC;

SELECT
    s.name,
    MIN(a.published_at) AS oldest_article,
    MAX(a.published_at) AS newest_article,
    COUNT(*) AS article_count
FROM articles a
JOIN sources s
    ON a.source_id = s.id
GROUP BY s.name
ORDER BY s.name;
