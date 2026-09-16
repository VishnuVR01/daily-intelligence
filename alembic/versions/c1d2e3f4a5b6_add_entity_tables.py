"""Add entity tables for Stage 4B Knowledge Layer

Revision ID: c1d2e3f4a5b6
Revises: b7a6f5e4d3c2
Create Date: 2026-09-15 23:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b7a6f5e4d3c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. entities table
    op.create_table(
        'entities',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
        sa.Column('canonical_name', sa.Text(), nullable=False),
        sa.Column('normalized_name', sa.Text(), nullable=False),
        sa.Column('entity_type', sa.Text(), nullable=False),
        sa.Column('slug', sa.Text(), nullable=False),
        sa.Column('country_code', sa.String(length=10), nullable=True),
        sa.Column('external_ids', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('slug', name='uix_entity_slug'),
        sa.UniqueConstraint('normalized_name', 'entity_type', name='uix_entity_name_type'),
    )
    op.create_index('idx_entities_slug', 'entities', ['slug'])
    op.create_index('idx_entities_normalized_name', 'entities', ['normalized_name'])
    op.create_index('idx_entities_type', 'entities', ['entity_type'])

    # 2. entity_aliases table
    op.create_table(
        'entity_aliases',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
        sa.Column('entity_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('alias', sa.Text(), nullable=False),
        sa.Column('normalized_alias', sa.Text(), nullable=False),
        sa.Column('alias_type', sa.Text(), server_default='KNOWN_ALIAS', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('entity_id', 'normalized_alias', name='uix_entity_alias'),
    )
    op.create_index('idx_entity_aliases_normalized', 'entity_aliases', ['normalized_alias'])

    # 3. entity_mentions table
    op.create_table(
        'entity_mentions',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
        sa.Column('entity_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('article_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('surface_form', sa.Text(), nullable=False),
        sa.Column('raw_entity_type', sa.Text(), nullable=False),
        sa.Column('resolved_entity_type', sa.Text(), nullable=False),
        sa.Column('confidence_class', sa.Text(), server_default='HIGH', nullable=False),
        sa.Column('extraction_method', sa.Text(), server_default='AI_OUTPUT_EXISTING', nullable=False),
        sa.Column('extractor_version', sa.Text(), server_default='entity_extractor_v1', nullable=False),
        sa.Column('context_snippet', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('entity_id', 'article_id', name='uix_entity_article_mention'),
    )
    op.create_index('idx_entity_mentions_article', 'entity_mentions', ['article_id'])
    op.create_index('idx_entity_mentions_entity', 'entity_mentions', ['entity_id'])


def downgrade() -> None:
    op.drop_table('entity_mentions')
    op.drop_table('entity_aliases')
    op.drop_table('entities')
