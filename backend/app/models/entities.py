from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Float,
    DateTime,
    Date,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    UniqueConstraint,
    desc,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    org_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    org_type = Column(String(64), nullable=False, index=True)  # fmcg_company, cnf_agency, logistics_provider, distributor, retailer
    contact_email = Column(String(128), nullable=True)
    contact_phone = Column(String(64), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    owned_locations = relationship("Location", foreign_keys="[Location.owner_org_id]", back_populates="owner_org")
    operated_locations = relationship("Location", foreign_keys="[Location.operator_org_id]", back_populates="operator_org")
    owned_inventory = relationship("InventorySnapshot", back_populates="owner_org")
    carried_routes = relationship("Route", back_populates="carrier_agency")


class Product(Base):
    __tablename__ = "products"

    sku_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(128), nullable=True, default="General")
    unit = Column(String(32), nullable=False, default="cases")
    case_pack = Column(Integer, nullable=False, default=1)
    shelf_life_days = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    inventory_records = relationship("InventorySnapshot", back_populates="product", cascade="all, delete-orphan")
    sales_records = relationship("SalesHistory", back_populates="product", cascade="all, delete-orphan")


class Location(Base):
    __tablename__ = "locations"

    location_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    location_type = Column(String(64), nullable=False, index=True)
    # Types: manufacturing_plant, company_warehouse, central_warehouse, regional_warehouse,
    # cnf_facility, 3pl_facility, distributor_warehouse, retail_destination
    region = Column(String(128), nullable=False)
    city = Column(String(128), nullable=True)
    address = Column(String(255), nullable=True)
    owner_org_id = Column(String(64), ForeignKey("organizations.org_id", ondelete="SET NULL"), nullable=True, index=True)
    operator_org_id = Column(String(64), ForeignKey("organizations.org_id", ondelete="SET NULL"), nullable=True, index=True)
    storage_capacity_units = Column(Float, nullable=True)
    dispatch_capacity_daily = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    owner_org = relationship("Organization", foreign_keys=[owner_org_id], back_populates="owned_locations")
    operator_org = relationship("Organization", foreign_keys=[operator_org_id], back_populates="operated_locations")
    inventory_records = relationship("InventorySnapshot", back_populates="location", cascade="all, delete-orphan")
    destination_sales = relationship("SalesHistory", back_populates="destination", cascade="all, delete-orphan")
    routes_from = relationship("Route", foreign_keys="[Route.from_location_id]", back_populates="from_location", cascade="all, delete-orphan")
    routes_to = relationship("Route", foreign_keys="[Route.to_location_id]", back_populates="to_location", cascade="all, delete-orphan")


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(64), index=True, nullable=False)
    sku_id = Column(String(64), ForeignKey("products.sku_id", ondelete="CASCADE"), nullable=False, index=True)
    location_id = Column(String(64), ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False, index=True)
    owner_org_id = Column(String(64), ForeignKey("organizations.org_id", ondelete="SET NULL"), nullable=True, index=True)
    on_hand = Column(Float, nullable=False, default=0.0)
    reserved = Column(Float, nullable=False, default=0.0)
    blocked = Column(Float, nullable=False, default=0.0)
    confirmed_incoming = Column(Float, nullable=False, default=0.0)
    batch_number = Column(String(64), nullable=True)
    expiry_date = Column(Date, nullable=True)
    as_of_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Compound uniqueness on snapshot_id + sku_id + location_id
    __table_args__ = (
        UniqueConstraint("snapshot_id", "sku_id", "location_id", name="uq_snapshot_sku_location"),
    )

    product = relationship("Product", back_populates="inventory_records")
    location = relationship("Location", back_populates="inventory_records")
    owner_org = relationship("Organization", foreign_keys=[owner_org_id], back_populates="owned_inventory")

    @property
    def dispatchable_stock(self) -> float:
        """
        PRD Section 7.4:
        Current dispatchable amount = max(0, on_hand - reserved - blocked).
        Incoming and in-transit units are not current dispatchable stock.
        """
        return max(0.0, float(self.on_hand - self.reserved - self.blocked))


class SalesHistory(Base):
    __tablename__ = "sales_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(String(64), ForeignKey("products.sku_id", ondelete="CASCADE"), nullable=False, index=True)
    destination_id = Column(String(64), ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False, index=True)
    sales_date = Column(Date, nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("sku_id", "destination_id", "sales_date", name="uq_sales_sku_dest_date"),
    )

    product = relationship("Product", back_populates="sales_records")
    destination = relationship("Location", back_populates="destination_sales")


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_location_id = Column(String(64), ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False, index=True)
    to_location_id = Column(String(64), ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False, index=True)
    carrier_agency_id = Column(String(64), ForeignKey("organizations.org_id", ondelete="SET NULL"), nullable=True, index=True)
    lead_time_days = Column(Float, nullable=False)
    cost_rate = Column(Float, nullable=False)
    capacity_units = Column(Float, nullable=True)
    sku_eligibility = Column(String(255), nullable=True, default="all")
    pricing_basis = Column(String(64), nullable=False, default="per_unit")  # per_unit, per_case, per_trip
    min_shipment_qty = Column(Float, nullable=True)
    max_shipment_qty = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    status_notes = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("from_location_id", "to_location_id", name="uq_route_from_to"),
    )

    from_location = relationship("Location", foreign_keys=[from_location_id], back_populates="routes_from")
    to_location = relationship("Location", foreign_keys=[to_location_id], back_populates="routes_to")
    carrier_agency = relationship("Organization", foreign_keys=[carrier_agency_id], back_populates="carried_routes")


class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id = Column(String(64), primary_key=True, index=True)
    sku_id = Column(String(64), ForeignKey("products.sku_id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    source_location_id = Column(String(64), ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False, index=True)
    destination_location_id = Column(String(64), ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False, index=True)
    owner_org_id = Column(String(64), ForeignKey("organizations.org_id", ondelete="SET NULL"), nullable=True, index=True)
    carrier_agency_id = Column(String(64), ForeignKey("organizations.org_id", ondelete="SET NULL"), nullable=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="SET NULL"), nullable=True)
    estimated_dispatch_date = Column(DateTime(timezone=True), nullable=True)
    estimated_arrival_date = Column(DateTime(timezone=True), nullable=True)
    estimated_transport_cost = Column(Float, nullable=False, default=0.0)
    status = Column(String(32), nullable=False, default="proposed", index=True)
    # Statuses: proposed, approved, rejected, ready_for_dispatch, in_transit, delivered, cancelled
    planning_run_id = Column(String(64), nullable=True, index=True)
    approval_status = Column(String(32), nullable=False, default="pending", index=True)  # pending, approved, rejected
    approved_by = Column(String(128), nullable=True)
    approval_notes = Column(Text, nullable=True)

    # Phase 4: Logistics Agency Coordination & Operational Execution
    carrier_contact = Column(String(128), nullable=True)
    consignment_number = Column(String(64), nullable=True, index=True)
    vehicle_number = Column(String(32), nullable=True)
    driver_contact = Column(String(64), nullable=True)
    planned_pickup_date = Column(DateTime(timezone=True), nullable=True)
    actual_pickup_date = Column(DateTime(timezone=True), nullable=True)
    actual_delivery_date = Column(DateTime(timezone=True), nullable=True)
    actual_transport_cost = Column(Float, nullable=True)  # Separate from estimated_transport_cost
    logistics_status = Column(String(32), nullable=False, default="unassigned", index=True)  # unassigned, assigned, accepted, rejected
    logistics_notes = Column(Text, nullable=True)
    exception_reason = Column(String(255), nullable=True)
    exception_notes = Column(Text, nullable=True)
    pod_reference = Column(String(128), nullable=True)
    dispatch_checklist = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    product = relationship("Product")
    source_location = relationship("Location", foreign_keys=[source_location_id])
    destination_location = relationship("Location", foreign_keys=[destination_location_id])
    owner_org = relationship("Organization", foreign_keys=[owner_org_id])
    carrier_agency = relationship("Organization", foreign_keys=[carrier_agency_id])
    route = relationship("Route")
    movements = relationship("StockMovement", back_populates="shipment", cascade="all, delete-orphan")
    events = relationship("ShipmentEvent", back_populates="shipment", cascade="all, delete-orphan", order_by="desc(ShipmentEvent.created_at)")


class ShipmentEvent(Base):
    __tablename__ = "shipment_events"

    event_id = Column(String(64), primary_key=True, index=True)
    shipment_id = Column(String(64), ForeignKey("shipments.shipment_id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String(32), nullable=False)
    to_status = Column(String(32), nullable=False)
    actor_id = Column(String(128), nullable=False)
    actor_role = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    shipment = relationship("Shipment", back_populates="events")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    movement_id = Column(String(64), primary_key=True, index=True)
    shipment_id = Column(String(64), ForeignKey("shipments.shipment_id", ondelete="SET NULL"), nullable=True, index=True)
    sku_id = Column(String(64), ForeignKey("products.sku_id", ondelete="CASCADE"), nullable=False, index=True)
    source_location_id = Column(String(64), ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False)
    destination_location_id = Column(String(64), ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Float, nullable=False)
    movement_type = Column(String(32), nullable=False)  # proposed_dispatch, approved_allocation, simulated_transit, delivered_audit
    status = Column(String(32), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    notes = Column(String(255), nullable=True)

    # Relationships
    shipment = relationship("Shipment", back_populates="movements")
    product = relationship("Product")
    source = relationship("Location", foreign_keys=[source_location_id])
    destination = relationship("Location", foreign_keys=[destination_location_id])


class ImportRun(Base):
    __tablename__ = "import_runs"

    run_id = Column(String(64), primary_key=True, index=True)
    dataset_type = Column(String(64), nullable=False, index=True)  # products, locations, inventory, sales, routes, organizations
    filename = Column(String(255), nullable=False)
    file_format = Column(String(16), nullable=False)  # csv, xlsx
    file_size_bytes = Column(Integer, nullable=False)
    total_rows = Column(Integer, nullable=False, default=0)
    valid_rows = Column(Integer, nullable=False, default=0)
    rejected_rows = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, index=True)  # completed, partial, failed
    snapshot_id = Column(String(64), nullable=True, index=True)
    org_id = Column(String(64), nullable=True, index=True)
    created_by_user_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    errors = relationship("ImportRowError", back_populates="import_run", cascade="all, delete-orphan")


class ImportRowError(Base):
    __tablename__ = "import_row_errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("import_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    row_index = Column(Integer, nullable=False)  # 1-based original file row number
    field_name = Column(String(64), nullable=True)
    rejected_value = Column(String(255), nullable=True)
    error_reason = Column(String(255), nullable=False)
    error_code = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    import_run = relationship("ImportRun", back_populates="errors")


class PlanningRun(Base):
    __tablename__ = "planning_runs"

    run_id = Column(String(64), primary_key=True, index=True)
    snapshot_id = Column(String(64), nullable=True, index=True)
    horizon_days = Column(Integer, nullable=False, default=7)
    objective_strategy = Column(String(64), nullable=False, default="service-first")
    solver_status = Column(String(32), nullable=False, default="optimal")
    solve_time_ms = Column(Float, nullable=False, default=0.0)
    total_demand_units = Column(Float, nullable=False, default=0.0)
    fulfilled_demand_units = Column(Float, nullable=False, default=0.0)
    unmet_demand_units = Column(Float, nullable=False, default=0.0)
    service_level_percent = Column(Float, nullable=False, default=0.0)
    estimated_transport_cost = Column(Float, nullable=False, default=0.0)
    stock_utilization_percent = Column(Float, nullable=False, default=0.0)
    unmet_demand_breakdown = Column(Text, nullable=True)
    baseline_comparison = Column(Text, nullable=True)
    decision_receipts = Column(Text, nullable=True)
    solver_name = Column(String(64), nullable=False, default="scipy_highs")
    planning_mode = Column(String(64), nullable=False, default="standard")
    festival_event_id = Column(String(64), nullable=True)
    org_id = Column(String(64), nullable=True, index=True)
    created_by_user_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class FestivalEvent(Base):
    """
    Phase 4.5 UtsavSense: Festival-Aware Inventory Planning Events.
    Represents configurable cultural and regional festivals with demand uplift assumptions.
    """
    __tablename__ = "festival_events"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    regions = Column(JSON, nullable=False, default=list)
    applicable_categories = Column(JSON, nullable=False, default=list)
    default_uplift_percent = Column(Float, nullable=False, default=35.0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class IdempotencyRecord(Base):
    """
    Phase 5 Database Reliability: Idempotency protections for state-mutating operations.
    Prevents duplicate shipment staging, dispatch deduction, and double billing.
    """
    __tablename__ = "idempotency_records"

    key = Column(String(64), primary_key=True, index=True)
    user_id = Column(String(100), nullable=True, index=True)
    endpoint = Column(String(255), nullable=False)
    request_hash = Column(String(64), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_data = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

