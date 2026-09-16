from datetime import datetime, date, timezone
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db import Base


class Country(Base):
    __tablename__ = "countries"

    code = Column(String(10), primary_key=True)
    name = Column(Text, nullable=False)
    region = Column(Text, nullable=True)
    is_brics = Column(Boolean, nullable=False, server_default="false", default=False)
    is_g7 = Column(Boolean, nullable=False, server_default="false", default=False)
    is_g20 = Column(Boolean, nullable=False, server_default="false", default=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    articles = relationship("Article", secondary="article_countries", back_populates="countries")
    sources = relationship("Source", back_populates="country")


class ArticleCountry(Base):
    __tablename__ = "article_countries"

    article_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    country_code = Column(
        String(10),
        ForeignKey("countries.code", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (PrimaryKeyConstraint("article_id", "country_code"),)


class Source(Base):
    __tablename__ = "sources"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    feed_url = Column(Text, nullable=True)
    website_url = Column(Text, nullable=True)
    source_type = Column(Text, nullable=False, server_default="rss", default="rss")
    source_family = Column(Text, nullable=False, server_default="news", default="news")
    category = Column(Text, nullable=True)
    trust_tier = Column(Text, nullable=False, server_default="useful", default="useful")
    active = Column(Boolean, nullable=False, server_default="true", default=True)
    replacement_candidate = Column(Boolean, nullable=False, server_default="false", default=False)
    provenance = Column(Text, nullable=False, server_default="independent", default="independent")
    country_code = Column(String(10), ForeignKey("countries.code"), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    country = relationship("Country", back_populates="sources")
    articles = relationship("Article", back_populates="source", cascade="all, delete-orphan")


class Article(Base):
    __tablename__ = "articles"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    source_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("sources.id"), nullable=True)
    title = Column(Text, nullable=False)
    canonical_url = Column(Text, nullable=False, unique=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    collected_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    raw_summary = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    title_fingerprint = Column(Text, nullable=True)
    language = Column(Text, server_default="en", default="en")

    # Part 1 Taxonomy & Metadata Extension
    primary_category = Column(Text, nullable=True)
    regions = Column(Text, nullable=True)
    groups = Column(Text, nullable=True)
    content_type = Column(Text, nullable=False, server_default="article", default="article")

    source = relationship("Source", back_populates="articles")
    countries = relationship("Country", secondary="article_countries", back_populates="articles")
    saved_info = relationship("SavedArticle", back_populates="article", uselist=False, cascade="all, delete-orphan")
    ai_outputs = relationship("ArticleAIOutput", back_populates="article", cascade="all, delete-orphan")


class SavedArticle(Base):
    __tablename__ = "saved_articles"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    article_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("articles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    saved_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    is_read = Column(Boolean, nullable=False, server_default="false", default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)

    article = relationship("Article", back_populates="saved_info")



class DailyEdition(Base):
    __tablename__ = "daily_editions"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    edition_date = Column(Date, nullable=False)
    algorithm_version = Column(Text, nullable=False, server_default="edition_v1", default="edition_v1")
    status = Column(Text, nullable=False, server_default="DRAFT", default="DRAFT") # DRAFT, GENERATED, PUBLISHED, ARCHIVED
    readiness = Column(Text, nullable=False, server_default="PREPARING", default="PREPARING") # PREPARING, READY
    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    lead_article_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
    )
    lead_event_cluster_id = Column(
        String(100),
        ForeignKey("event_clusters.cluster_id", ondelete="SET NULL"),
        nullable=True,
    )
    article_count = Column(Integer, nullable=False, server_default="0", default=0)
    event_count = Column(Integer, nullable=False, server_default="0", default=0)
    metadata_json = Column(JSON, nullable=True)
    audit_json = Column(JSON, nullable=True)

    lead_article = relationship("Article", foreign_keys=[lead_article_id])
    lead_event_cluster = relationship("EventCluster", foreign_keys=[lead_event_cluster_id])
    edition_articles = relationship(
        "EditionArticle",
        back_populates="edition",
        cascade="all, delete-orphan",
        order_by="EditionArticle.position",
    )
    edition_events = relationship(
        "EditionEvent",
        back_populates="edition",
        cascade="all, delete-orphan",
        order_by="EditionEvent.position",
    )
    brief = relationship("EditionBrief", back_populates="edition", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint(
            "edition_date",
            "algorithm_version",
            name="uix_daily_edition_date_version",
        ),
    )


class EditionArticle(Base):
    __tablename__ = "daily_edition_articles"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    edition_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("daily_editions.id", ondelete="CASCADE"),
        nullable=False,
    )
    article_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    section = Column(Text, nullable=False)
    position = Column(Integer, nullable=False, server_default="1", default=1)
    edition_score = Column(Float, nullable=False, server_default="0.0", default=0.0)
    selection_reason = Column(Text, nullable=True)
    selection_reason_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    edition = relationship("DailyEdition", back_populates="edition_articles")
    article = relationship("Article")

    __table_args__ = (
        UniqueConstraint("edition_id", "article_id", name="uix_edition_article_unique"),
    )


class EditionEvent(Base):
    __tablename__ = "edition_events"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    edition_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("daily_editions.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_cluster_id = Column(
        String(100),
        ForeignKey("event_clusters.cluster_id", ondelete="CASCADE"),
        nullable=False,
    )
    section = Column(Text, nullable=False)
    role = Column(Text, nullable=False, server_default="SECTION", default="SECTION")
    position = Column(Integer, nullable=False, server_default="1", default=1)
    event_score = Column(Float, nullable=False, server_default="0.0", default=0.0)
    selection_reason = Column(Text, nullable=True)
    selection_reason_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    edition = relationship("DailyEdition", back_populates="edition_events")
    event_cluster = relationship("EventCluster")
    editorial_prose = relationship("EventEditorialProse", back_populates="edition_event", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("edition_id", "event_cluster_id", name="uix_edition_event_unique"),
    )


class EventEditorialProse(Base):
    __tablename__ = "event_editorial_prose"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    edition_event_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("edition_events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    event_cluster_id = Column(String(100), nullable=False)
    headline = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    why_it_matters = Column(Text, nullable=True)
    watch_next_json = Column(JSON, nullable=True)
    evidence_article_ids = Column(JSON, nullable=True)
    status = Column(Text, nullable=False, server_default="SUCCESS", default="SUCCESS") # SUCCESS, FALLBACK, FAILED
    model = Column(Text, nullable=False, server_default="qwen3.5:4b", default="qwen3.5:4b")
    prompt_version = Column(Text, nullable=False, server_default="editorial_event_v1", default="editorial_event_v1")
    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    edition_event = relationship("EditionEvent", back_populates="editorial_prose")


class EditionBrief(Base):
    __tablename__ = "daily_edition_briefs"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    edition_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("daily_editions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    brief_text = Column(Text, nullable=False)
    key_themes_json = Column(JSON, nullable=True)
    model = Column(Text, nullable=False, server_default="qwen3.5:4b", default="qwen3.5:4b")
    prompt_version = Column(Text, nullable=False, server_default="editorial_edition_v1", default="editorial_edition_v1")
    status = Column(Text, nullable=False, server_default="SUCCESS", default="SUCCESS")
    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    edition = relationship("DailyEdition", back_populates="brief")


class ArticleAIOutput(Base):
    __tablename__ = "article_ai_outputs"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    article_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(Text, nullable=False, server_default="ollama", default="ollama")
    model = Column(Text, nullable=False, server_default="qwen3.5:4b", default="qwen3.5:4b")
    task = Column(Text, nullable=False, server_default="article_analysis", default="article_analysis")
    prompt_version = Column(Text, nullable=False, server_default="v1", default="v1")
    output_json = Column(JSON, nullable=True)
    summary = Column(Text, nullable=True)
    primary_category = Column(Text, nullable=True)
    is_relevant = Column(Boolean, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    importance_score = Column(Integer, nullable=True)
    relevance_score = Column(Integer, nullable=True)
    status = Column(Text, nullable=False, server_default="success", default="success")
    processed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    processing_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    article = relationship("Article", back_populates="ai_outputs")

    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "provider",
            "model",
            "task",
            "prompt_version",
            name="uix_article_ai_output_provider_model_task_version",
        ),
    )


class EventCluster(Base):
    __tablename__ = "event_clusters"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    cluster_id = Column(String(100), nullable=False, unique=True)
    canonical_title = Column(Text, nullable=False)
    primary_article_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("articles.id", ondelete="SET NULL"), nullable=True)
    category = Column(Text, nullable=False)
    distinct_source_count = Column(Integer, nullable=False, default=1)
    article_count = Column(Integer, nullable=False, default=1)
    cluster_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    earliest_article_at = Column(DateTime(timezone=True), nullable=True)
    latest_article_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSON, nullable=True)

    primary_article = relationship("Article", foreign_keys=[primary_article_id])
    cluster_articles = relationship("EventClusterArticle", back_populates="event_cluster", cascade="all, delete-orphan")
    event_entities = relationship("EventEntity", back_populates="event_cluster", cascade="all, delete-orphan")



class EventClusterArticle(Base):
    __tablename__ = "event_cluster_articles"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    cluster_id = Column(String(100), ForeignKey("event_clusters.cluster_id", ondelete="CASCADE"), nullable=False)
    article_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False)
    article_relationship = Column(Text, nullable=False, default="SUPPORTING")
    similarity_score = Column(Float, nullable=False, default=1.0)
    reason_json = Column(JSON, nullable=True)

    event_cluster = relationship("EventCluster", back_populates="cluster_articles")
    article = relationship("Article")

    __table_args__ = (
        UniqueConstraint("cluster_id", "article_id", name="uix_cluster_article_unique"),
    )


class Entity(Base):
    __tablename__ = "entities"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    canonical_name = Column(Text, nullable=False)
    normalized_name = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    slug = Column(Text, nullable=False, unique=True)
    country_code = Column(String(10), nullable=True)
    external_ids = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    aliases = relationship("EntityAlias", back_populates="entity", cascade="all, delete-orphan")
    mentions = relationship("EntityMention", back_populates="entity", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("normalized_name", "entity_type", name="uix_entity_name_type"),
    )


class EntityAlias(Base):
    __tablename__ = "entity_aliases"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    entity_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias = Column(Text, nullable=False)
    normalized_alias = Column(Text, nullable=False)
    alias_type = Column(Text, nullable=False, server_default="KNOWN_ALIAS", default="KNOWN_ALIAS")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    entity = relationship("Entity", back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("entity_id", "normalized_alias", name="uix_entity_alias"),
    )


class EntityMention(Base):
    __tablename__ = "entity_mentions"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    entity_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    article_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    surface_form = Column(Text, nullable=False)
    raw_entity_type = Column(Text, nullable=False)
    resolved_entity_type = Column(Text, nullable=False)
    confidence_class = Column(Text, nullable=False, server_default="HIGH", default="HIGH")
    extraction_method = Column(Text, nullable=False, server_default="AI_OUTPUT_EXISTING", default="AI_OUTPUT_EXISTING")
    extractor_version = Column(Text, nullable=False, server_default="entity_extractor_v1", default="entity_extractor_v1")
    context_snippet = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    entity = relationship("Entity", back_populates="mentions")
    article = relationship("Article")

    __table_args__ = (
        UniqueConstraint("entity_id", "article_id", name="uix_entity_article_mention"),
    )


class EventEntity(Base):
    __tablename__ = "event_entities"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    event_cluster_id = Column(
        String(100),
        ForeignKey("event_clusters.cluster_id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String(50), nullable=False, server_default="MENTIONED", default="MENTIONED")
    confidence_class = Column(String(20), nullable=False, server_default="HIGH", default="HIGH")
    link_method = Column(String(50), nullable=False)
    supporting_mention_count = Column(Integer, nullable=False, server_default="1", default=1)
    supporting_article_count = Column(Integer, nullable=False, server_default="1", default=1)
    distinct_source_count = Column(Integer, nullable=False, server_default="1", default=1)
    evidence_class = Column(String(50), nullable=False, server_default="SUPPORTING_ONLY", default="SUPPORTING_ONLY")
    provenance_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    event_cluster = relationship("EventCluster", back_populates="event_entities")
    entity = relationship("Entity")

    __table_args__ = (
        UniqueConstraint("event_cluster_id", "entity_id", "role", name="uix_event_entity_role"),
    )


class Signal(Base):
    __tablename__ = "signals"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    signal_type = Column(String(50), nullable=False)
    subject_type = Column(String(50), nullable=False)
    subject_key = Column(String(100), nullable=False)
    entity_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
    )
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, server_default="ACTIVE", default="ACTIVE")
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    comparison_start = Column(DateTime(timezone=True), nullable=True)
    comparison_end = Column(DateTime(timezone=True), nullable=True)
    event_count = Column(Integer, nullable=False, server_default="0", default=0)
    entity_count = Column(Integer, nullable=False, server_default="0", default=0)
    source_count = Column(Integer, nullable=False, server_default="0", default=0)
    trigger_method = Column(String(50), nullable=False)
    generator_version = Column(String(50), nullable=False, server_default="signal_generator_v1", default="signal_generator_v1")
    fingerprint = Column(String(128), nullable=False, unique=True)
    audit_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    entity = relationship("Entity")
    evidence = relationship("SignalEvidence", back_populates="signal", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("fingerprint", name="uix_signal_fingerprint"),
    )


class SignalEvidence(Base):
    __tablename__ = "signal_evidence"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    signal_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("signals.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_cluster_id = Column(
        String(100),
        ForeignKey("event_clusters.cluster_id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
    )
    article_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_role = Column(String(50), nullable=False, server_default="PRIMARY_EVENT", default="PRIMARY_EVENT")
    evidence_reason = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    signal = relationship("Signal", back_populates="evidence")
    event_cluster = relationship("EventCluster")
    entity = relationship("Entity")
    article = relationship("Article")



