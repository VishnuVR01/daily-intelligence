"""Add event_clusters, event_cluster_articles, edition_events, event_editorial_prose, daily_edition_briefs, pipeline_locks tables, and daily_editions Stage 3C columns

Revision ID: b8f9e0a1b2c3
Revises: b7a6f5e4d3c2
Create Date: 2026-09-15 22:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = 'b8f9e0a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'b7a6f5e4d3c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. event_clusters table
    if 'event_clusters' not in existing_tables:
        op.create_table(
            'event_clusters',
            sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
            sa.Column('cluster_id', sa.String(length=100), nullable=False),
            sa.Column('canonical_title', sa.Text(), nullable=False),
            sa.Column('primary_article_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('articles.id', ondelete='SET NULL'), nullable=True),
            sa.Column('category', sa.Text(), nullable=False),
            sa.Column('distinct_source_count', sa.Integer(), server_default='1', nullable=False),
            sa.Column('article_count', sa.Integer(), server_default='1', nullable=False),
            sa.Column('cluster_score', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('earliest_article_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('latest_article_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('metadata_json', sa.JSON(), nullable=True),
            sa.UniqueConstraint('cluster_id', name='uix_event_cluster_id'),
        )
        op.create_index('idx_event_clusters_cluster_id', 'event_clusters', ['cluster_id'])
        op.create_index('idx_event_clusters_category', 'event_clusters', ['category'])

    # 2. event_cluster_articles table
    if 'event_cluster_articles' not in existing_tables:
        op.create_table(
            'event_cluster_articles',
            sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
            sa.Column('cluster_id', sa.String(length=100), sa.ForeignKey('event_clusters.cluster_id', ondelete='CASCADE'), nullable=False),
            sa.Column('article_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
            sa.Column('is_primary', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('article_relationship', sa.Text(), server_default='SUPPORTING', nullable=False),
            sa.Column('similarity_score', sa.Float(), server_default='1.0', nullable=False),
            sa.Column('reason_json', sa.JSON(), nullable=True),
            sa.UniqueConstraint('cluster_id', 'article_id', name='uix_cluster_article_unique'),
        )
        op.create_index('idx_event_cluster_articles_cluster', 'event_cluster_articles', ['cluster_id'])
        op.create_index('idx_event_cluster_articles_article', 'event_cluster_articles', ['article_id'])

    # 3. edition_events table
    if 'edition_events' not in existing_tables:
        op.create_table(
            'edition_events',
            sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
            sa.Column('edition_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('daily_editions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('event_cluster_id', sa.String(length=100), sa.ForeignKey('event_clusters.cluster_id', ondelete='CASCADE'), nullable=False),
            sa.Column('section', sa.Text(), nullable=False),
            sa.Column('role', sa.Text(), server_default='SECTION', nullable=False),
            sa.Column('position', sa.Integer(), server_default='1', nullable=False),
            sa.Column('event_score', sa.Float(), server_default='0.0', nullable=False),
            sa.Column('selection_reason', sa.Text(), nullable=True),
            sa.Column('selection_reason_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.UniqueConstraint('edition_id', 'event_cluster_id', name='uix_edition_event_unique'),
        )
        op.create_index('idx_edition_events_edition', 'edition_events', ['edition_id'])
        op.create_index('idx_edition_events_cluster', 'edition_events', ['event_cluster_id'])

    # 4. event_editorial_prose table
    if 'event_editorial_prose' not in existing_tables:
        op.create_table(
            'event_editorial_prose',
            sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
            sa.Column('edition_event_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('edition_events.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('event_cluster_id', sa.String(length=100), nullable=False),
            sa.Column('headline', sa.Text(), nullable=False),
            sa.Column('summary', sa.Text(), nullable=False),
            sa.Column('why_it_matters', sa.Text(), nullable=True),
            sa.Column('watch_next_json', sa.JSON(), nullable=True),
            sa.Column('evidence_article_ids', sa.JSON(), nullable=True),
            sa.Column('status', sa.Text(), server_default='SUCCESS', nullable=False),
            sa.Column('model', sa.Text(), server_default='qwen3.5:4b', nullable=False),
            sa.Column('prompt_version', sa.Text(), server_default='editorial_event_v1', nullable=False),
            sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )

    # 5. daily_edition_briefs table
    if 'daily_edition_briefs' not in existing_tables:
        op.create_table(
            'daily_edition_briefs',
            sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
            sa.Column('edition_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('daily_editions.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('brief_text', sa.Text(), nullable=False),
            sa.Column('key_themes_json', sa.JSON(), nullable=True),
            sa.Column('model', sa.Text(), server_default='qwen3.5:4b', nullable=False),
            sa.Column('prompt_version', sa.Text(), server_default='editorial_edition_v1', nullable=False),
            sa.Column('status', sa.Text(), server_default='SUCCESS', nullable=False),
            sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )

    # 6. pipeline_locks table
    if 'pipeline_locks' not in existing_tables:
        op.create_table(
            'pipeline_locks',
            sa.Column('lock_name', sa.String(length=50), primary_key=True, nullable=False),
            sa.Column('is_locked', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        )

    # 7. Add missing Stage 3C columns to daily_editions if absent
    if 'daily_editions' in existing_tables:
        daily_editions_cols = [c['name'] for c in inspector.get_columns('daily_editions')]
        if 'readiness' not in daily_editions_cols:
            op.add_column('daily_editions', sa.Column('readiness', sa.Text(), server_default='PREPARING', nullable=False))
        if 'lead_event_cluster_id' not in daily_editions_cols:
            op.add_column('daily_editions', sa.Column('lead_event_cluster_id', sa.String(length=100), sa.ForeignKey('event_clusters.cluster_id', ondelete='SET NULL'), nullable=True))
        if 'event_count' not in daily_editions_cols:
            op.add_column('daily_editions', sa.Column('event_count', sa.Integer(), server_default='0', nullable=False))
        if 'audit_json' not in daily_editions_cols:
            op.add_column('daily_editions', sa.Column('audit_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    if 'daily_editions' in existing_tables:
        daily_editions_cols = [c['name'] for c in inspector.get_columns('daily_editions')]
        if 'audit_json' in daily_editions_cols:
            op.drop_column('daily_editions', 'audit_json')
        if 'event_count' in daily_editions_cols:
            op.drop_column('daily_editions', 'event_count')
        if 'lead_event_cluster_id' in daily_editions_cols:
            op.drop_column('daily_editions', 'lead_event_cluster_id')
        if 'readiness' in daily_editions_cols:
            op.drop_column('daily_editions', 'readiness')

    if 'pipeline_locks' in existing_tables:
        op.drop_table('pipeline_locks')
    if 'daily_edition_briefs' in existing_tables:
        op.drop_table('daily_edition_briefs')
    if 'event_editorial_prose' in existing_tables:
        op.drop_table('event_editorial_prose')
    if 'edition_events' in existing_tables:
        op.drop_table('edition_events')
    if 'event_cluster_articles' in existing_tables:
        op.drop_table('event_cluster_articles')
    if 'event_clusters' in existing_tables:
        op.drop_table('event_clusters')
