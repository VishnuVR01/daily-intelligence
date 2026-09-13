-- ============================================================
-- Focused content / source investigations
-- ============================================================

SELECT
    DATE_TRUNC('year', a.published_at) AS year,
    COUNT(*) AS article_count
FROM articles a
JOIN sources s
    ON a.source_id = s.id
WHERE s.name = 'OpenAI'
GROUP BY DATE_TRUNC('year', a.published_at)
ORDER BY year;

-- Reusable source lookup template:
--
-- SELECT
--     a.id,
--     a.title,
--     a.published_at,
--     a.canonical_url
-- FROM articles a
-- JOIN sources s
--     ON a.source_id = s.id
-- WHERE s.name = 'SOURCE_NAME'
-- ORDER BY a.published_at DESC NULLS LAST;
