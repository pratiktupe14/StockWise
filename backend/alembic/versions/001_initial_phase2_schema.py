"""Initial Phase 2 schema for products, locations, inventory, sales, routes, and imports.

Revision ID: 001_initial_phase2_schema
Revises: 
Create Date: 2026-10-24 16:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_initial_phase2_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Products
    op.create_table(
        'products',
        sa.Column('sku_id', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=128), nullable=True),
        sa.Column('unit', sa.String(length=32), nullable=False, server_default='cases'),
        sa.Column('case_pack', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('shelf_life_days', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_products_sku_id', 'products', ['sku_id'])

    # 2. Locations
    op.create_table(
        'locations',
        sa.Column('location_id', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('location_type', sa.String(length=64), nullable=False),
        sa.Column('region', sa.String(length=128), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_locations_location_id', 'locations', ['location_id'])

    # 3. Inventory Snapshots
    op.create_table(
        'inventory_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('snapshot_id', sa.String(length=64), nullable=False),
        sa.Column('sku_id', sa.String(length=64), nullable=False),
        sa.Column('location_id', sa.String(length=64), nullable=False),
        sa.Column('on_hand', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('reserved', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('blocked', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('confirmed_incoming', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['sku_id'], ['products.sku_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.location_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('snapshot_id', 'sku_id', 'location_id', name='uq_snapshot_sku_location'),
    )
    op.create_index('ix_inventory_snapshots_snapshot_id', 'inventory_snapshots', ['snapshot_id'])
    op.create_index('ix_inventory_snapshots_sku_id', 'inventory_snapshots', ['sku_id'])
    op.create_index('ix_inventory_snapshots_location_id', 'inventory_snapshots', ['location_id'])

    # 4. Sales History
    op.create_table(
        'sales_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('sku_id', sa.String(length=64), nullable=False),
        sa.Column('destination_id', sa.String(length=64), nullable=False),
        sa.Column('sales_date', sa.Date(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['sku_id'], ['products.sku_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['destination_id'], ['locations.location_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('sku_id', 'destination_id', 'sales_date', name='uq_sales_sku_dest_date'),
    )
    op.create_index('ix_sales_history_sku_id', 'sales_history', ['sku_id'])
    op.create_index('ix_sales_history_destination_id', 'sales_history', ['destination_id'])
    op.create_index('ix_sales_history_sales_date', 'sales_history', ['sales_date'])

    # 5. Routes
    op.create_table(
        'routes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('from_location_id', sa.String(length=64), nullable=False),
        sa.Column('to_location_id', sa.String(length=64), nullable=False),
        sa.Column('lead_time_days', sa.Float(), nullable=False),
        sa.Column('cost_rate', sa.Float(), nullable=False),
        sa.Column('capacity_units', sa.Float(), nullable=True),
        sa.Column('sku_eligibility', sa.String(length=255), nullable=True, server_default='all'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['from_location_id'], ['locations.location_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_location_id'], ['locations.location_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('from_location_id', 'to_location_id', name='uq_route_from_to'),
    )
    op.create_index('ix_routes_from_location_id', 'routes', ['from_location_id'])
    op.create_index('ix_routes_to_location_id', 'routes', ['to_location_id'])

    # 6. Import Runs
    op.create_table(
        'import_runs',
        sa.Column('run_id', sa.String(length=64), primary_key=True),
        sa.Column('dataset_type', sa.String(length=64), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_format', sa.String(length=16), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('total_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('valid_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rejected_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('snapshot_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_import_runs_run_id', 'import_runs', ['run_id'])
    op.create_index('ix_import_runs_dataset_type', 'import_runs', ['dataset_type'])
    op.create_index('ix_import_runs_status', 'import_runs', ['status'])
    op.create_index('ix_import_runs_snapshot_id', 'import_runs', ['snapshot_id'])

    # 7. Import Row Errors
    op.create_table(
        'import_row_errors',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('row_index', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(length=64), nullable=True),
        sa.Column('rejected_value', sa.String(length=255), nullable=True),
        sa.Column('error_reason', sa.String(length=255), nullable=False),
        sa.Column('error_code', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['import_runs.run_id'], ondelete='CASCADE'),
    )
    op.create_index('ix_import_row_errors_run_id', 'import_row_errors', ['run_id'])


def downgrade() -> None:
    op.drop_table('import_row_errors')
    op.drop_table('import_runs')
    op.drop_table('routes')
    op.drop_table('sales_history')
    op.drop_table('inventory_snapshots')
    op.drop_table('locations')
    op.drop_table('products')
