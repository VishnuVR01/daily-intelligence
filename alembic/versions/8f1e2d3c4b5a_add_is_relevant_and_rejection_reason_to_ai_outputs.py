"""add is_relevant and rejection_reason to article_ai_outputs

Revision ID: 8f1e2d3c4b5a
Revises: 4e8910a51c91
Create Date: 2026-09-13 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f1e2d3c4b5a'
down_revision: Union[str, Sequence[str], None] = ('352c665694b2', '4e8910a51c91')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('article_ai_outputs', sa.Column('is_relevant', sa.Boolean(), nullable=True))
    op.add_column('article_ai_outputs', sa.Column('rejection_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('article_ai_outputs', 'rejection_reason')
    op.drop_column('article_ai_outputs', 'is_relevant')
