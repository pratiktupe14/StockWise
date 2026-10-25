"""Logistics execution schema: Phase 4 carrier coordination, warehouse dispatch readiness, shipment events audit trail.

Revision ID: 004_logistics_execution
Revises: 003_planning_engine
Create Date: 2026-10-24 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_logistics_execution'
down_revision = '003_planning_engine'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add Phase 4 execution columns to shipments table
    op.add_column('shipments', sa.Column('carrier_contact', sa.String(length=128), nullable=True))
    op.add_column('shipments', sa.Column('consignment_number', sa.String(length=64), nullable=True))
    op.add_column('shipments', sa.Column('vehicle_number', sa.String(length=32), nullable=True))
    op.add_column('shipments', sa.Column('driver_contact', sa.String(length=64), nullable=True))
    op.add_column('shipments', sa.Column('planned_pickup_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('shipments', sa.Column('actual_pickup_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('shipments', sa.Column('actual_delivery_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('shipments', sa.Column('actual_transport_cost', sa.Float(), nullable=True))
    op.add_column('shipments', sa.Column('logistics_status', sa.String(length=32), nullable=False, server_default='unassigned'))
    op.add_column('shipments', sa.Column('logistics_notes', sa.Text(), nullable=True))
    op.add_column('shipments', sa.Column('exception_reason', sa.String(length=255), nullable=True))
    op.add_column('shipments', sa.Column('exception_notes', sa.Text(), nullable=True))
    op.add_column('shipments', sa.Column('pod_reference', sa.String(length=128), nullable=True))
    op.add_column('shipments', sa.Column('dispatch_checklist', sa.Text(), nullable=True))

    op.create_index('ix_shipments_consignment_number', 'shipments', ['consignment_number'])
    op.create_index('ix_shipments_logistics_status', 'shipments', ['logistics_status'])

    # 2. Create shipment_events immutable audit table
    op.create_table(
        'shipment_events',
        sa.Column('event_id', sa.String(length=64), primary_key=True),
        sa.Column('shipment_id', sa.String(length=64), sa.ForeignKey('shipments.shipment_id', ondelete='CASCADE'), nullable=False),
        sa.Column('from_status', sa.String(length=32), nullable=False),
        sa.Column('to_status', sa.String(length=32), nullable=False),
        sa.Column('actor_id', sa.String(length=128), nullable=False),
        sa.Column('actor_role', sa.String(length=64), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_shipment_events_event_id', 'shipment_events', ['event_id'])
    op.create_index('ix_shipment_events_shipment_id', 'shipment_events', ['shipment_id'])


def downgrade() -> None:
    op.drop_index('ix_shipment_events_shipment_id', table_name='shipment_events')
    op.drop_index('ix_shipment_events_event_id', table_name='shipment_events')
    op.drop_table('shipment_events')

    op.drop_index('ix_shipments_logistics_status', table_name='shipments')
    op.drop_index('ix_shipments_consignment_number', table_name='shipments')

    op.drop_column('shipments', 'dispatch_checklist')
    op.drop_column('shipments', 'pod_reference')
    op.drop_column('shipments', 'exception_notes')
    op.drop_column('shipments', 'exception_reason')
    op.drop_column('shipments', 'logistics_notes')
    op.drop_column('shipments', 'logistics_status')
    op.drop_column('shipments', 'actual_transport_cost')
    op.drop_column('shipments', 'actual_delivery_date')
    op.drop_column('shipments', 'actual_pickup_date')
    op.drop_column('shipments', 'planned_pickup_date')
    op.drop_column('shipments', 'driver_contact')
    op.drop_column('shipments', 'vehicle_number')
    op.drop_column('shipments', 'consignment_number')
    op.drop_column('shipments', 'carrier_contact')
