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
    status = Column(Text, nullable=False, server_default="published", default="published")
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
    article_count = Column(Integer, nullable=False, server_default="0", default=0)
    metadata_json = Column(JSON, nullable=True)

    lead_article = relationship("Article", foreign_keys=[lead_article_id])
    edition_articles = relationship(
        "EditionArticle",
        back_populates="edition",
        cascade="all, delete-orphan",
        order_by="EditionArticle.position",
    )

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
