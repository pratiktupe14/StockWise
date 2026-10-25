"""006_idempotency

Revision ID: 006_idempotency
Revises: 005_utsav_sense
Create Date: 2026-10-25 00:18:00.000000

Phase 5: Database Reliability & Concurrency - Idempotency records table.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006_idempotency'
down_revision: Union[str, None] = '005_utsav_sense'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'idempotency_records',
        sa.Column('key', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('endpoint', sa.String(length=255), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('response_data', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_idempotency_records_key', 'idempotency_records', ['key'], unique=False)
    op.create_index('ix_idempotency_records_user_id', 'idempotency_records', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_idempotency_records_user_id', table_name='idempotency_records')
    op.drop_index('ix_idempotency_records_key', table_name='idempotency_records')
    op.drop_table('idempotency_records')
