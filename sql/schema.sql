-- Initial MVP schema.
-- We will evolve this with Alembic once the first models are final.

CREATE TABLE IF NOT EXISTS sources (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    feed_url TEXT,
    website_url TEXT,
    source_type TEXT NOT NULL DEFAULT 'rss',
    category TEXT,
    trust_tier TEXT NOT NULL DEFAULT 'useful',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS articles (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES sources(id),
    title TEXT NOT NULL,
    canonical_url TEXT NOT NULL UNIQUE,
    published_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_summary TEXT,
    extracted_text TEXT,
    title_fingerprint TEXT,
    language TEXT DEFAULT 'en'
);

CREATE INDEX IF NOT EXISTS idx_articles_published_at
    ON articles (published_at DESC);

CREATE INDEX IF NOT EXISTS idx_articles_source_id
    ON articles (source_id);

CREATE INDEX IF NOT EXISTS idx_articles_title_fingerprint
    ON articles (title_fingerprint);

CREATE TABLE IF NOT EXISTS daily_editions (
    id BIGSERIAL PRIMARY KEY,
    edition_date DATE NOT NULL UNIQUE,
    title TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS edition_articles (
    edition_id BIGINT NOT NULL REFERENCES daily_editions(id) ON DELETE CASCADE,
    article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    rank INTEGER,
    PRIMARY KEY (edition_id, article_id)
);

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

SELECT current_database();
SELECT current_schema();

SELECT
    id,
    name,
    category,
    trust_tier,
    active
FROM sources
ORDER BY id;