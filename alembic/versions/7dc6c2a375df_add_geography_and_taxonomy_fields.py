"""add geography and taxonomy fields

Revision ID: 7dc6c2a375df
Revises: 
Create Date: 2026-09-12 22:23:09.341644

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7dc6c2a375df'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # 1. Create countries table if missing
    if "countries" not in existing_tables:
        op.create_table(
            "countries",
            sa.Column("code", sa.String(length=10), primary_key=True, nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("region", sa.Text(), nullable=True),
            sa.Column("is_brics", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("is_g7", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("is_g20", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("lat", sa.Float(), nullable=True),
            sa.Column("lng", sa.Float(), nullable=True),
        )

    # 2. Create article_countries table if missing
    if "article_countries" not in existing_tables:
        op.create_table(
            "article_countries",
            sa.Column("article_id", sa.BigInteger(), nullable=False),
            sa.Column("country_code", sa.String(length=10), nullable=False),
            sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["country_code"], ["countries.code"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("article_id", "country_code"),
        )

    # 3. Safely add columns to sources
    sources_cols = [c["name"] for c in inspector.get_columns("sources")]
    if "country_code" not in sources_cols:
        op.add_column("sources", sa.Column("country_code", sa.String(length=10), nullable=True))
        op.create_foreign_key(
            "fk_sources_country_code",
            "sources",
            "countries",
            ["country_code"],
            ["code"],
        )

    # 4. Safely add columns to articles
    articles_cols = [c["name"] for c in inspector.get_columns("articles")]
    if "primary_category" not in articles_cols:
        op.add_column("articles", sa.Column("primary_category", sa.Text(), nullable=True))
    if "regions" not in articles_cols:
        op.add_column("articles", sa.Column("regions", sa.Text(), nullable=True))
    if "groups" not in articles_cols:
        op.add_column("articles", sa.Column("groups", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "articles" in existing_tables:
        articles_cols = [c["name"] for c in inspector.get_columns("articles")]
        if "groups" in articles_cols:
            op.drop_column("articles", "groups")
        if "regions" in articles_cols:
            op.drop_column("articles", "regions")
        if "primary_category" in articles_cols:
            op.drop_column("articles", "primary_category")

    if "sources" in existing_tables:
        sources_cols = [c["name"] for c in inspector.get_columns("sources")]
        if "country_code" in sources_cols:
            try:
                op.drop_constraint("fk_sources_country_code", "sources", type_="foreignkey")
            except Exception:
                pass
            op.drop_column("sources", "country_code")

    if "article_countries" in existing_tables:
        op.drop_table("article_countries")

    if "countries" in existing_tables:
        op.drop_table("countries")
