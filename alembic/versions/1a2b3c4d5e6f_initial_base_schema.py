"""initial_base_schema

Revision ID: 1a2b3c4d5e6f
Revises: 
Create Date: 2026-09-12 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "sources" not in existing_tables:
        op.create_table(
            "sources",
            sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("feed_url", sa.Text(), nullable=True),
            sa.Column("website_url", sa.Text(), nullable=True),
            sa.Column("source_type", sa.Text(), nullable=False, server_default="rss"),
            sa.Column("category", sa.Text(), nullable=True),
            sa.Column("trust_tier", sa.Text(), nullable=False, server_default="useful"),
            sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if "articles" not in existing_tables:
        op.create_table(
            "articles",
            sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
            sa.Column("source_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey("sources.id"), nullable=True),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("canonical_url", sa.Text(), nullable=False, unique=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("raw_summary", sa.Text(), nullable=True),
            sa.Column("extracted_text", sa.Text(), nullable=True),
            sa.Column("title_fingerprint", sa.Text(), nullable=True),
            sa.Column("language", sa.Text(), server_default="en"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "articles" in existing_tables:
        op.drop_table("articles")
    if "sources" in existing_tables:
        op.drop_table("sources")
