"""add saved_articles table and replacement_candidate to sources

Revision ID: 4e8910a51c91
Revises: 339be5e01b20
Create Date: 2026-09-13 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e8910a51c91'
down_revision: Union[str, None] = '339be5e01b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add replacement_candidate to sources table safely
    op.add_column(
        'sources',
        sa.Column('replacement_candidate', sa.Boolean(), server_default='false', nullable=False)
    )

    # Create saved_articles table
    op.create_table(
        'saved_articles',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
        sa.Column('article_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('saved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_read', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('saved_articles')
    op.drop_column('sources', 'replacement_candidate')
