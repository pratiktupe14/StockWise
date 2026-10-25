"""007_tenant_isolation

Revision ID: 007_tenant_isolation
Revises: 006_idempotency
Create Date: 2026-10-25 01:48:00.000000

Phase 5: Tenant Isolation - Scopes planning runs and import runs to organizations and users.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '007_tenant_isolation'
down_revision: Union[str, None] = '006_idempotency'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add tenant context columns to import_runs
    op.add_column('import_runs', sa.Column('org_id', sa.String(length=64), nullable=True))
    op.add_column('import_runs', sa.Column('created_by_user_id', sa.String(length=100), nullable=True))
    op.create_index('ix_import_runs_org_id', 'import_runs', ['org_id'], unique=False)

    # 2. Add tenant context columns to planning_runs
    op.add_column('planning_runs', sa.Column('org_id', sa.String(length=64), nullable=True))
    op.add_column('planning_runs', sa.Column('created_by_user_id', sa.String(length=100), nullable=True))
    op.create_index('ix_planning_runs_org_id', 'planning_runs', ['org_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_planning_runs_org_id', table_name='planning_runs')
    op.drop_column('planning_runs', 'created_by_user_id')
    op.drop_column('planning_runs', 'org_id')

    op.drop_index('ix_import_runs_org_id', table_name='import_runs')
    op.drop_column('import_runs', 'created_by_user_id')
    op.drop_column('import_runs', 'org_id')
