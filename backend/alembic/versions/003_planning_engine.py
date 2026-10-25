"""Planning engine schema: planning_runs table for persisting optimization and baseline audit records.

Revision ID: 003_planning_engine
Revises: 002_network_design
Create Date: 2026-10-24 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_planning_engine'
down_revision = '002_network_design'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'planning_runs',
        sa.Column('run_id', sa.String(length=64), primary_key=True),
        sa.Column('snapshot_id', sa.String(length=64), nullable=True, index=True),
        sa.Column('horizon_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('objective_strategy', sa.String(length=64), nullable=False, server_default='service-first'),
        sa.Column('solver_status', sa.String(length=32), nullable=False, server_default='optimal'),
        sa.Column('solve_time_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_demand_units', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('fulfilled_demand_units', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('unmet_demand_units', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('service_level_percent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('estimated_transport_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('stock_utilization_percent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('unmet_demand_breakdown', sa.Text(), nullable=True),
        sa.Column('baseline_comparison', sa.Text(), nullable=True),
        sa.Column('decision_receipts', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('planning_runs')
