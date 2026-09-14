"""add PostgreSQL FTS GIN indexes for articles and article_ai_outputs

Revision ID: b7a6f5e4d3c2
Revises: 9a8f7e6d5c4b
Create Date: 2026-09-13 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7a6f5e4d3c2'
down_revision: Union[str, Sequence[str], None] = '9a8f7e6d5c4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres GIN full-text search indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_articles_fts ON articles 
        USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(raw_summary, '')));
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_article_ai_outputs_fts ON article_ai_outputs 
        USING gin(to_tsvector('english', coalesce(summary, '')));
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_article_ai_outputs_fts;")
    op.execute("DROP INDEX IF EXISTS idx_articles_fts;")
