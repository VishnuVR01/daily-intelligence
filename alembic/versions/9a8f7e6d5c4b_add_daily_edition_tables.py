"""add daily_editions and daily_edition_articles tables

Revision ID: 9a8f7e6d5c4b
Revises: 8f1e2d3c4b5a
Create Date: 2026-09-13 21:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a8f7e6d5c4b'
down_revision: Union[str, Sequence[str], None] = '8f1e2d3c4b5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS edition_articles CASCADE")
    op.execute("DROP TABLE IF EXISTS daily_edition_articles CASCADE")
    op.execute("DROP TABLE IF EXISTS daily_editions CASCADE")

    op.create_table(
        'daily_editions',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
        sa.Column('edition_date', sa.Date(), nullable=False),
        sa.Column('algorithm_version', sa.Text(), nullable=False, server_default='edition_v1'),
        sa.Column('status', sa.Text(), nullable=False, server_default='published'),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('lead_article_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('articles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('article_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.UniqueConstraint('edition_date', 'algorithm_version', name='uix_daily_edition_date_version'),
    )

    op.create_table(
        'daily_edition_articles',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
        sa.Column('edition_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('daily_editions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('article_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('section', sa.Text(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('edition_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('selection_reason', sa.Text(), nullable=True),
        sa.Column('selection_reason_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('edition_id', 'article_id', name='uix_edition_article_unique'),
    )


def downgrade() -> None:
    op.drop_table('daily_edition_articles')
    op.drop_table('daily_editions')
