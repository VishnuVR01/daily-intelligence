"""Add signals and signal_evidence tables for Stage 4D Knowledge Layer

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-09-15 23:22:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. signals table
    op.create_table(
        'signals',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
        sa.Column('signal_type', sa.String(length=50), nullable=False),
        sa.Column('subject_type', sa.String(length=50), nullable=False),
        sa.Column('subject_key', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('entities.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='ACTIVE', nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('comparison_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('comparison_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('event_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('entity_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('source_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('trigger_method', sa.String(length=50), nullable=False),
        sa.Column('generator_version', sa.String(length=50), server_default='signal_generator_v1', nullable=False),
        sa.Column('fingerprint', sa.String(length=128), nullable=False),
        sa.Column('audit_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('fingerprint', name='uix_signal_fingerprint'),
    )
    op.create_index('idx_signals_type', 'signals', ['signal_type'])
    op.create_index('idx_signals_subject', 'signals', ['subject_type', 'subject_key'])
    op.create_index('idx_signals_status', 'signals', ['status'])
    op.create_index('idx_signals_entity', 'signals', ['entity_id'])

    # 2. signal_evidence table
    op.create_table(
        'signal_evidence',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
        sa.Column('signal_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('signals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_cluster_id', sa.String(length=100), sa.ForeignKey('event_clusters.cluster_id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('entities.id', ondelete='SET NULL'), nullable=True),
        sa.Column('article_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), sa.ForeignKey('articles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('evidence_role', sa.String(length=50), server_default='PRIMARY_EVENT', nullable=False),
        sa.Column('evidence_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('idx_signal_evidence_signal', 'signal_evidence', ['signal_id'])
    op.create_index('idx_signal_evidence_cluster', 'signal_evidence', ['event_cluster_id'])
    
    # PostgreSQL-safe NULL-safe unique index for (signal_id, event_cluster_id, COALESCE(entity_id, -1))
    op.execute(
        "CREATE UNIQUE INDEX uix_signal_evidence_null_safe ON signal_evidence "
        "(signal_id, event_cluster_id, COALESCE(entity_id, -1))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uix_signal_evidence_null_safe")
    op.drop_index('idx_signal_evidence_cluster', table_name='signal_evidence')
    op.drop_index('idx_signal_evidence_signal', table_name='signal_evidence')
    op.drop_table('signal_evidence')
    op.drop_index('idx_signals_entity', table_name='signals')
    op.drop_index('idx_signals_status', table_name='signals')
    op.drop_index('idx_signals_subject', table_name='signals')
    op.drop_index('idx_signals_type', table_name='signals')
    op.drop_table('signals')
