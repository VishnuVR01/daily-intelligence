"""Add event_entities table for Stage 4C Knowledge Layer

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-09-15 23:12:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'event_entities',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
        sa.Column('event_cluster_id', sa.String(length=100), sa.ForeignKey('event_clusters.cluster_id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='MENTIONED', nullable=False),
        sa.Column('confidence_class', sa.String(length=20), server_default='HIGH', nullable=False),
        sa.Column('link_method', sa.String(length=50), nullable=False),
        sa.Column('supporting_mention_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('supporting_article_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('distinct_source_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('evidence_class', sa.String(length=50), server_default='SUPPORTING_ONLY', nullable=False),
        sa.Column('provenance_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('event_cluster_id', 'entity_id', 'role', name='uix_event_entity_role'),
    )
    op.create_index('idx_event_entities_cluster', 'event_entities', ['event_cluster_id'])
    op.create_index('idx_event_entities_entity', 'event_entities', ['entity_id'])
    op.create_index('idx_event_entities_role', 'event_entities', ['role'])


def downgrade() -> None:
    op.drop_index('idx_event_entities_role', table_name='event_entities')
    op.drop_index('idx_event_entities_entity', table_name='event_entities')
    op.drop_index('idx_event_entities_cluster', table_name='event_entities')
    op.drop_table('event_entities')
