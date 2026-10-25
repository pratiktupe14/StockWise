"""Real-world distribution network schema: organizations, extended locations/routes/inventory, shipments, and stock movements.

Revision ID: 002_network_design
Revises: 001_initial_phase2_schema
Create Date: 2026-10-24 18:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_network_design'
down_revision = '001_initial_phase2_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Organizations
    op.create_table(
        'organizations',
        sa.Column('org_id', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('org_type', sa.String(length=64), nullable=False),
        sa.Column('contact_email', sa.String(length=128), nullable=True),
        sa.Column('contact_phone', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_organizations_org_id', 'organizations', ['org_id'])
    op.create_index('ix_organizations_org_type', 'organizations', ['org_type'])

    # 2. Extend Locations
    op.add_column('locations', sa.Column('city', sa.String(length=128), nullable=True))
    op.add_column('locations', sa.Column('owner_org_id', sa.String(length=64), nullable=True))
    op.add_column('locations', sa.Column('operator_org_id', sa.String(length=64), nullable=True))
    op.add_column('locations', sa.Column('storage_capacity_units', sa.Float(), nullable=True))
    op.add_column('locations', sa.Column('dispatch_capacity_daily', sa.Float(), nullable=True))
    op.add_column('locations', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('locations', sa.Column('longitude', sa.Float(), nullable=True))
    op.add_column('locations', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    
    op.create_foreign_key('fk_locations_owner_org', 'locations', 'organizations', ['owner_org_id'], ['org_id'], ondelete='SET NULL')
    op.create_foreign_key('fk_locations_operator_org', 'locations', 'organizations', ['operator_org_id'], ['org_id'], ondelete='SET NULL')
    op.create_index('ix_locations_location_type', 'locations', ['location_type'])
    op.create_index('ix_locations_owner_org_id', 'locations', ['owner_org_id'])
    op.create_index('ix_locations_operator_org_id', 'locations', ['operator_org_id'])

    # 3. Extend Inventory Snapshots
    op.add_column('inventory_snapshots', sa.Column('owner_org_id', sa.String(length=64), nullable=True))
    op.add_column('inventory_snapshots', sa.Column('batch_number', sa.String(length=64), nullable=True))
    op.add_column('inventory_snapshots', sa.Column('expiry_date', sa.Date(), nullable=True))
    op.create_foreign_key('fk_inventory_owner_org', 'inventory_snapshots', 'organizations', ['owner_org_id'], ['org_id'], ondelete='SET NULL')
    op.create_index('ix_inventory_snapshots_owner_org_id', 'inventory_snapshots', ['owner_org_id'])

    # 4. Extend Routes
    op.add_column('routes', sa.Column('carrier_agency_id', sa.String(length=64), nullable=True))
    op.add_column('routes', sa.Column('pricing_basis', sa.String(length=64), nullable=False, server_default='per_unit'))
    op.add_column('routes', sa.Column('min_shipment_qty', sa.Float(), nullable=True))
    op.add_column('routes', sa.Column('max_shipment_qty', sa.Float(), nullable=True))
    op.add_column('routes', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('routes', sa.Column('status_notes', sa.String(length=255), nullable=True))
    op.create_foreign_key('fk_routes_carrier_agency', 'routes', 'organizations', ['carrier_agency_id'], ['org_id'], ondelete='SET NULL')
    op.create_index('ix_routes_carrier_agency_id', 'routes', ['carrier_agency_id'])

    # 5. Shipments
    op.create_table(
        'shipments',
        sa.Column('shipment_id', sa.String(length=64), primary_key=True),
        sa.Column('sku_id', sa.String(length=64), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('source_location_id', sa.String(length=64), nullable=False),
        sa.Column('destination_location_id', sa.String(length=64), nullable=False),
        sa.Column('owner_org_id', sa.String(length=64), nullable=True),
        sa.Column('carrier_agency_id', sa.String(length=64), nullable=True),
        sa.Column('route_id', sa.Integer(), nullable=True),
        sa.Column('estimated_dispatch_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('estimated_arrival_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('estimated_transport_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='proposed'),
        sa.Column('planning_run_id', sa.String(length=64), nullable=True),
        sa.Column('approval_status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('approved_by', sa.String(length=128), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['sku_id'], ['products.sku_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_location_id'], ['locations.location_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['destination_location_id'], ['locations.location_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_org_id'], ['organizations.org_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['carrier_agency_id'], ['organizations.org_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['route_id'], ['routes.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_shipments_shipment_id', 'shipments', ['shipment_id'])
    op.create_index('ix_shipments_sku_id', 'shipments', ['sku_id'])
    op.create_index('ix_shipments_source_location_id', 'shipments', ['source_location_id'])
    op.create_index('ix_shipments_destination_location_id', 'shipments', ['destination_location_id'])
    op.create_index('ix_shipments_status', 'shipments', ['status'])
    op.create_index('ix_shipments_approval_status', 'shipments', ['approval_status'])

    # 6. Stock Movements (traceable history)
    op.create_table(
        'stock_movements',
        sa.Column('movement_id', sa.String(length=64), primary_key=True),
        sa.Column('shipment_id', sa.String(length=64), nullable=True),
        sa.Column('sku_id', sa.String(length=64), nullable=False),
        sa.Column('source_location_id', sa.String(length=64), nullable=False),
        sa.Column('destination_location_id', sa.String(length=64), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('movement_type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.shipment_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sku_id'], ['products.sku_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_location_id'], ['locations.location_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['destination_location_id'], ['locations.location_id'], ondelete='CASCADE'),
    )
    op.create_index('ix_stock_movements_movement_id', 'stock_movements', ['movement_id'])
    op.create_index('ix_stock_movements_shipment_id', 'stock_movements', ['shipment_id'])
    op.create_index('ix_stock_movements_sku_id', 'stock_movements', ['sku_id'])


def downgrade() -> None:
    op.drop_table('stock_movements')
    op.drop_table('shipments')
    op.drop_constraint('fk_routes_carrier_agency', 'routes', type_='foreignkey')
    op.drop_column('routes', 'status_notes')
    op.drop_column('routes', 'is_active')
    op.drop_column('routes', 'max_shipment_qty')
    op.drop_column('routes', 'min_shipment_qty')
    op.drop_column('routes', 'pricing_basis')
    op.drop_column('routes', 'carrier_agency_id')
    op.drop_constraint('fk_inventory_owner_org', 'inventory_snapshots', type_='foreignkey')
    op.drop_column('inventory_snapshots', 'expiry_date')
    op.drop_column('inventory_snapshots', 'batch_number')
    op.drop_column('inventory_snapshots', 'owner_org_id')
    op.drop_constraint('fk_locations_operator_org', 'locations', type_='foreignkey')
    op.drop_constraint('fk_locations_owner_org', 'locations', type_='foreignkey')
    op.drop_column('locations', 'is_active')
    op.drop_column('locations', 'longitude')
    op.drop_column('locations', 'latitude')
    op.drop_column('locations', 'dispatch_capacity_daily')
    op.drop_column('locations', 'storage_capacity_units')
    op.drop_column('locations', 'operator_org_id')
    op.drop_column('locations', 'owner_org_id')
    op.drop_column('locations', 'city')
    op.drop_table('organizations')
