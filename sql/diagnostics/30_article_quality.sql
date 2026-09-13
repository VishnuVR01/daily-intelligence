-- ============================================================
-- Article quality / integrity checks
-- ============================================================

SELECT
    a.id,
    s.name AS source,
    a.title,
    a.published_at
FROM articles a
JOIN sources s
    ON a.source_id = s.id
ORDER BY a.published_at DESC NULLS LAST
LIMIT 20;

SELECT
    canonical_url,
    COUNT(*) AS duplicate_count
FROM articles
GROUP BY canonical_url
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

SELECT
    COUNT(*) AS total_articles,
    COUNT(*) FILTER (
        WHERE title IS NULL OR BTRIM(title) = ''
    ) AS missing_title,
    COUNT(*) FILTER (
        WHERE canonical_url IS NULL OR BTRIM(canonical_url) = ''
    ) AS missing_url,
    COUNT(*) FILTER (
        WHERE published_at IS NULL
    ) AS missing_published_at,
    COUNT(*) FILTER (
        WHERE raw_summary IS NULL OR BTRIM(raw_summary) = ''
    ) AS missing_summary
FROM articles;

SELECT
    a.id,
    s.name AS source,
    a.title,
    a.published_at,
    a.canonical_url
FROM articles a
JOIN sources s
    ON a.source_id = s.id
WHERE a.published_at > NOW()
ORDER BY a.published_at;
