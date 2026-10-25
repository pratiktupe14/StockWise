"""UtsavSense festival planning schema & planning extensions (OR-Tools solver tracking, festival events).

Revision ID: 005_utsav_sense_and_planning_extensions
Revises: 004_logistics_execution
Create Date: 2026-10-24 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005_utsav_sense'
down_revision = '004_logistics_execution'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add solver_name, planning_mode, festival_event_id to planning_runs
    op.add_column('planning_runs', sa.Column('solver_name', sa.String(length=64), nullable=False, server_default='scipy_highs'))
    op.add_column('planning_runs', sa.Column('planning_mode', sa.String(length=64), nullable=False, server_default='standard'))
    op.add_column('planning_runs', sa.Column('festival_event_id', sa.String(length=64), nullable=True))
    op.create_index('ix_planning_runs_festival_event_id', 'planning_runs', ['festival_event_id'])

    # 2. Create festival_events table
    op.create_table(
        'festival_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('event_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('regions', sa.JSON(), nullable=False),
        sa.Column('applicable_categories', sa.JSON(), nullable=False),
        sa.Column('default_uplift_percent', sa.Float(), nullable=False, server_default='35.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_festival_events_event_id', 'festival_events', ['event_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_festival_events_event_id', table_name='festival_events')
    op.drop_table('festival_events')

    op.drop_index('ix_planning_runs_festival_event_id', table_name='planning_runs')
    op.drop_column('planning_runs', 'festival_event_id')
    op.drop_column('planning_runs', 'planning_mode')
    op.drop_column('planning_runs', 'solver_name')
