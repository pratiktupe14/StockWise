"""
Tests for Distribution Intelligence Enhancements:
- Multi-warehouse split sourcing & network allocation
- Route SKU handling eligibility enforcement
- Route max shipment quantity cap
- Facility dispatch capacity daily limit
- Corridor / route alternative comparator (ranking, itemized costs, rejection reasons)
- What-If scenario simulation dry run safety (zero DB side-effects)
- Traceable Decision Receipts (FEFO batches, distance, constraints)
- Operational distribution performance metrics
"""

import io
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.entities import (
    Organization,
    Location,
    Product,
    Route,
    InventorySnapshot,
    SalesHistory,
    PlanningRun,
    Shipment,
)


def _seed_distribution_network(client: TestClient, db_session: Session):
    """Seeds multi-warehouse distribution network."""
    # Organizations
    client.post("/api/organizations", json={"org_id": "ORG-FMCG", "name": "Global FMCG Corp", "org_type": "fmcg_company"})
    client.post("/api/organizations", json={"org_id": "ORG-DIST-1", "name": "Metro Distribution Partner", "org_type": "independent_distributor"})

    # Locations
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-PLANT-MUM",
            "name": "Mumbai Central Plant",
            "location_type": "central_plant",
            "region": "West",
            "city": "Mumbai",
            "latitude": 19.0760,
            "longitude": 72.8777,
            "owner_org_id": "ORG-FMCG",
            "operator_org_id": "ORG-FMCG",
            "storage_capacity_units": 500000,
            "dispatch_capacity_daily": 20000,
            "is_active": True,
        },
    )
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-RDC-PUNE",
            "name": "Pune Regional DC",
            "location_type": "regional_warehouse",
            "region": "West",
            "city": "Pune",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "owner_org_id": "ORG-FMCG",
            "operator_org_id": "ORG-FMCG",
            "storage_capacity_units": 100000,
            "dispatch_capacity_daily": 5000,
            "is_active": True,
        },
    )
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-RET-NAGPUR",
            "name": "Nagpur Metro Depot",
            "location_type": "retail_destination",
            "region": "West",
            "city": "Nagpur",
            "latitude": 21.1458,
            "longitude": 79.0882,
            "owner_org_id": "ORG-DIST-1",
            "operator_org_id": "ORG-DIST-1",
            "storage_capacity_units": 30000,
            "dispatch_capacity_daily": 2000,
            "is_active": True,
        },
    )

    # Products
    client.post(
        "/api/imports/products",
        files={"file": ("products.csv", io.BytesIO(b"sku_id,name,category,unit,case_pack,shelf_life_days\nSKU-JUICE-100,Orange Juice 1L,Beverages,cases,12,90\nSKU-SNACK-200,Salted Crisps,Snacks,cases,24,180\n"), "text/csv")},
    )


def test_multi_warehouse_split_sourcing(client: TestClient, db_session: Session):
    """
    Test Multi-Warehouse Split Sourcing:
    Destination has demand gap of 100 cases.
    Mumbai Plant has 60 cases dispatchable stock.
    Pune RDC has 60 cases dispatchable stock.
    Neither warehouse alone can fulfill 100 cases.
    The optimizer should split sourcing across both warehouses to satisfy destination demand.
    """
    _seed_distribution_network(client, db_session)

    # Routes to Nagpur from both Mumbai and Pune
    client.post("/api/network/routes", json={
        "from_location_id": "LOC-PLANT-MUM",
        "to_location_id": "LOC-RET-NAGPUR",
        "lead_time_days": 2.0,
        "cost_rate": 5.0,
        "is_active": True,
    })
    client.post("/api/network/routes", json={
        "from_location_id": "LOC-RDC-PUNE",
        "to_location_id": "LOC-RET-NAGPUR",
        "lead_time_days": 2.0,
        "cost_rate": 4.0,
        "is_active": True,
    })

    # Sales history: 20 cases/day for 7 days = 140 cases forecast
    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(SalesHistory(
            sku_id="SKU-JUICE-100",
            destination_id="LOC-RET-NAGPUR",
            sales_date=base_date + timedelta(days=day),
            quantity=20.0,
        ))

    # Destination on-hand: 40 cases => Demand Gap = 140 - 40 = 100 cases
    db_session.add(InventorySnapshot(
        snapshot_id="SNAP-DEST-1",
        sku_id="SKU-JUICE-100",
        location_id="LOC-RET-NAGPUR",
        on_hand=40.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        as_of_date=datetime.now(timezone.utc).date(),
        owner_org_id="ORG-DIST-1",
    ))

    # Mumbai Plant has 60 cases dispatchable
    db_session.add(InventorySnapshot(
        snapshot_id="SNAP-MUM-1",
        sku_id="SKU-JUICE-100",
        location_id="LOC-PLANT-MUM",
        on_hand=60.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        as_of_date=datetime.now(timezone.utc).date(),
        owner_org_id="ORG-FMCG",
    ))

    # Pune RDC has 60 cases dispatchable
    db_session.add(InventorySnapshot(
        snapshot_id="SNAP-PUNE-1",
        sku_id="SKU-JUICE-100",
        location_id="LOC-RDC-PUNE",
        on_hand=60.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        as_of_date=datetime.now(timezone.utc).date(),
        owner_org_id="ORG-FMCG",
    ))
    db_session.commit()

    resp = client.post("/api/optimization/run", json={"horizon_days": 7, "solver_preference": "ortools"})
    assert resp.status_code == 201
    data = resp.json()

    allocations = [
        s for s in data["recommended_shipments"]
        if s["destination_location_id"] == "LOC-RET-NAGPUR" and s["sku_id"] == "SKU-JUICE-100"
    ]
    total_allocated = sum(s["quantity"] for s in allocations)
    assert total_allocated == 100.0, f"Expected 100.0 cases fulfilled, got {total_allocated}"

    # Verify both sources contributed (split sourcing)
    source_ids = {s["source_location_id"] for s in allocations}
    assert "LOC-PLANT-MUM" in source_ids
    assert "LOC-RDC-PUNE" in source_ids


def test_route_sku_eligibility_enforcement(client: TestClient, db_session: Session):
    """
    Test Route SKU Handling Restrictions:
    A route restricted to 'SKU-SNACK-200' must reject 'SKU-JUICE-100'.
    """
    _seed_distribution_network(client, db_session)

    # Route with restricted SKU eligibility
    r_resp = client.post("/api/network/routes", json={
        "from_location_id": "LOC-PLANT-MUM",
        "to_location_id": "LOC-RET-NAGPUR",
        "lead_time_days": 2.0,
        "cost_rate": 3.0,
        "sku_eligibility": "SKU-SNACK-200",
        "is_active": True,
    })
    assert r_resp.status_code == 201

    # Sales history for SKU-JUICE-100
    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(SalesHistory(
            sku_id="SKU-JUICE-100",
            destination_id="LOC-RET-NAGPUR",
            sales_date=base_date + timedelta(days=day),
            quantity=15.0,
        ))

    db_session.add(InventorySnapshot(
        snapshot_id="SNAP-MUM-JUICE",
        sku_id="SKU-JUICE-100",
        location_id="LOC-PLANT-MUM",
        on_hand=500.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        as_of_date=datetime.now(timezone.utc).date(),
        owner_org_id="ORG-FMCG",
    ))
    db_session.commit()

    resp = client.post("/api/optimization/run", json={"horizon_days": 7, "solver_preference": "ortools"})
    assert resp.status_code == 201
    data = resp.json()

    # SKU-JUICE-100 should not be allocated on the restricted route
    allocations = [s for s in data["recommended_shipments"] if s["sku_id"] == "SKU-JUICE-100"]
    assert len(allocations) == 0

    # Unmet demand should be present with explanation
    unmet = [u for u in data["unmet_demand_breakdown"] if u["sku_id"] == "SKU-JUICE-100"]
    assert len(unmet) > 0
    assert any("permit" in r.lower() for r in unmet[0]["reasons"])


def test_route_max_shipment_qty_cap(client: TestClient, db_session: Session):
    """
    Test Route Capacity Limit:
    Route max_shipment_qty = 35.0.
    Destination needs 100.0.
    Warehouse has 200.0.
    Allocation cannot exceed 35.0.
    """
    _seed_distribution_network(client, db_session)

    client.post("/api/network/routes", json={
        "from_location_id": "LOC-PLANT-MUM",
        "to_location_id": "LOC-RET-NAGPUR",
        "lead_time_days": 2.0,
        "cost_rate": 3.0,
        "max_shipment_qty": 35.0,
        "is_active": True,
    })

    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(SalesHistory(
            sku_id="SKU-JUICE-100",
            destination_id="LOC-RET-NAGPUR",
            sales_date=base_date + timedelta(days=day),
            quantity=15.0,
        ))

    db_session.add(InventorySnapshot(
        snapshot_id="SNAP-MUM-CAP",
        sku_id="SKU-JUICE-100",
        location_id="LOC-PLANT-MUM",
        on_hand=500.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        as_of_date=datetime.now(timezone.utc).date(),
        owner_org_id="ORG-FMCG",
    ))
    db_session.commit()

    resp = client.post("/api/optimization/run", json={"horizon_days": 7, "solver_preference": "ortools"})
    assert resp.status_code == 201
    data = resp.json()

    allocations = [s for s in data["recommended_shipments"] if s["sku_id"] == "SKU-JUICE-100"]
    assert len(allocations) == 1
    assert allocations[0]["quantity"] <= 35.0


def test_corridor_comparison_endpoint(client: TestClient, db_session: Session):
    """
    Test GET /api/corridors/compare:
    Ranks routes by feasibility, distance, and total delivered cost.
    Provides itemized freight and handling costs and explicit rejection reasons.
    """
    _seed_distribution_network(client, db_session)

    # Route 1: Active
    client.post("/api/network/routes", json={
        "from_location_id": "LOC-PLANT-MUM",
        "to_location_id": "LOC-RET-NAGPUR",
        "lead_time_days": 2.0,
        "cost_rate": 5.0,
        "is_active": True,
    })
    # Route 2: Inactive
    client.post("/api/network/routes", json={
        "from_location_id": "LOC-RDC-PUNE",
        "to_location_id": "LOC-RET-NAGPUR",
        "lead_time_days": 3.0,
        "cost_rate": 3.5,
        "is_active": False,
    })

    # Add stock at Mumbai
    db_session.add(InventorySnapshot(
        snapshot_id="SNAP-CORR-MUM",
        sku_id="SKU-JUICE-100",
        location_id="LOC-PLANT-MUM",
        on_hand=200.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        as_of_date=datetime.now(timezone.utc).date(),
        owner_org_id="ORG-FMCG",
    ))
    db_session.commit()

    resp = client.get("/api/corridors/compare?destination_id=LOC-RET-NAGPUR&sku_id=SKU-JUICE-100&horizon_days=7")
    assert resp.status_code == 200
    data = resp.json()

    assert data["destination_id"] == "LOC-RET-NAGPUR"
    assert "alternatives" in data
    assert len(data["alternatives"]) >= 2

    # Verify ranking: Feasible corridor first
    top_corridor = data["alternatives"][0]
    assert top_corridor["is_feasible"] is True
    assert top_corridor["source_location_id"] == "LOC-PLANT-MUM"
    assert top_corridor["distance_km"] > 0
    assert top_corridor["cost_rate_per_unit"] > 0
    assert top_corridor["total_delivered_cost_per_unit"] > 0

    # Inactive route must be marked infeasible with rejection reason
    inactive_corridor = next((c for c in data["alternatives"] if c["source_location_id"] == "LOC-RDC-PUNE"), None)
    assert inactive_corridor is not None
    assert inactive_corridor["is_feasible"] is False
    assert any("inactive" in r.lower() for r in inactive_corridor["rejection_reasons"])


def test_what_if_scenario_simulation_dry_run_safety(client: TestClient, db_session: Session):
    """
    Test POST /api/optimization/simulate:
    Evaluates scenario changes (demand surge, freight rate changes) completely in-memory.
    Crucial Safety: Must leave physical inventory, planning runs, and shipments completely unchanged.
    """
    _seed_distribution_network(client, db_session)

    client.post("/api/network/routes", json={
        "from_location_id": "LOC-PLANT-MUM",
        "to_location_id": "LOC-RET-NAGPUR",
        "lead_time_days": 2.0,
        "cost_rate": 4.0,
        "is_active": True,
    })

    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(SalesHistory(
            sku_id="SKU-JUICE-100",
            destination_id="LOC-RET-NAGPUR",
            sales_date=base_date + timedelta(days=day),
            quantity=20.0,
        ))

    db_session.add(InventorySnapshot(
        snapshot_id="SNAP-SIM-MUM",
        sku_id="SKU-JUICE-100",
        location_id="LOC-PLANT-MUM",
        on_hand=300.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        as_of_date=datetime.now(timezone.utc).date(),
        owner_org_id="ORG-FMCG",
    ))
    db_session.commit()

    runs_before = db_session.query(PlanningRun).count()
    shipments_before = db_session.query(Shipment).count()

    sim_payload = {
        "scenario_name": "Diwali 50% Demand Surge + 20% Freight Increase",
        "demand_multiplier": 1.5,
        "freight_rate_multiplier": 1.2,
        "source_stock_multiplier": 1.0,
        "disrupted_route_ids": [],
        "horizon_days": 7,
    }

    resp = client.post("/api/optimization/simulate", json=sim_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_simulation"] is True
    assert len(data["impact_analysis"]) > 0
    assert data["simulated_plan"]["fulfilled_demand_units"] > 0

    # SAFETY CHECK: No database records created or modified
    runs_after = db_session.query(PlanningRun).count()
    shipments_after = db_session.query(Shipment).count()
    assert runs_after == runs_before, "Simulation must not create PlanningRun database records"
    assert shipments_after == shipments_before, "Simulation must not create Shipment database records"


def test_decision_receipt_traceability_and_batch_allocation(client: TestClient, db_session: Session):
    """
    Test Traceable Decision Receipts:
    Includes FEFO batch allocations, road distance km, itemized costs, and constraints evaluated.
    """
    _seed_distribution_network(client, db_session)

    client.post("/api/network/routes", json={
        "from_location_id": "LOC-PLANT-MUM",
        "to_location_id": "LOC-RET-NAGPUR",
        "lead_time_days": 2.0,
        "cost_rate": 4.5,
        "is_active": True,
    })

    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(SalesHistory(
            sku_id="SKU-JUICE-100",
            destination_id="LOC-RET-NAGPUR",
            sales_date=base_date + timedelta(days=day),
            quantity=15.0,
        ))

    # Add FEFO batch records via InventorySnapshot
    exp_date1 = (datetime.now(timezone.utc) + timedelta(days=45)).date()
    exp_date2 = (datetime.now(timezone.utc) + timedelta(days=80)).date()
    db_session.add(InventorySnapshot(
        snapshot_id="SNAP-MUM-BATCH-1",
        sku_id="SKU-JUICE-100",
        location_id="LOC-PLANT-MUM",
        on_hand=50.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        batch_number="B-MUM-001",
        expiry_date=exp_date1,
        as_of_date=datetime.now(timezone.utc).date(),
        owner_org_id="ORG-FMCG",
    ))
    db_session.add(InventorySnapshot(
        snapshot_id="SNAP-MUM-BATCH-2",
        sku_id="SKU-JUICE-100",
        location_id="LOC-PLANT-MUM",
        on_hand=150.0,
        reserved=0.0,
        blocked=0.0,
        confirmed_incoming=0.0,
        batch_number="B-MUM-002",
        expiry_date=exp_date2,
        as_of_date=datetime.now(timezone.utc).date(),
        owner_org_id="ORG-FMCG",
    ))
    db_session.commit()

    resp = client.post("/api/optimization/run", json={"horizon_days": 7, "solver_preference": "ortools"})
    assert resp.status_code == 201
    data = resp.json()

    receipts = data["decision_receipts"]
    assert len(receipts) > 0
    receipt = receipts[0]

    # Verify enriched fields
    assert "route_id" in receipt and receipt["route_id"] is not None
    assert "distance_km" in receipt and receipt["distance_km"] > 0
    assert "base_freight_cost" in receipt and receipt["base_freight_cost"] > 0
    assert "handling_cost" in receipt and receipt["handling_cost"] >= 0
    assert "allocated_batches" in receipt and len(receipt["allocated_batches"]) > 0
    assert "constraints_evaluated" in receipt and len(receipt["constraints_evaluated"]) >= 5

    # Verify FEFO ordering: earliest expiring batch first
    first_allocated_batch = receipt["allocated_batches"][0]
    assert first_allocated_batch["batch_number"] == "B-MUM-001"


def test_operational_performance_metrics_endpoint(client: TestClient, db_session: Session):
    """
    Test GET /api/optimization/performance-metrics:
    Returns lifecycle tracking across recommended, approved, reserved, dispatched, and delivered shipments.
    """
    _seed_distribution_network(client, db_session)

    # Seed shipments in various states matching the authenticated FMCG org
    now = datetime.now(timezone.utc)
    s1 = Shipment(
        shipment_id="SHIP-001",
        sku_id="SKU-JUICE-100",
        source_location_id="LOC-PLANT-MUM",
        destination_location_id="LOC-RET-NAGPUR",
        quantity=50.0,
        estimated_transport_cost=200.0,
        status="delivered",
        owner_org_id="ORG-FMCG-CORP",
        created_at=now - timedelta(days=2),
    )
    s2 = Shipment(
        shipment_id="SHIP-002",
        sku_id="SKU-JUICE-100",
        source_location_id="LOC-PLANT-MUM",
        destination_location_id="LOC-RET-NAGPUR",
        quantity=40.0,
        estimated_transport_cost=160.0,
        status="in_transit",
        owner_org_id="ORG-FMCG-CORP",
        created_at=now - timedelta(days=1),
    )
    db_session.add(s1)
    db_session.add(s2)
    db_session.commit()

    resp = client.get("/api/optimization/performance-metrics")
    assert resp.status_code == 200
    data = resp.json()

    assert "total_delivered_units" in data
    assert data["total_delivered_units"] == 50.0
    assert data["total_dispatched_units"] == 90.0  # delivered + in_transit
    assert "approval_rate_percent" in data
    assert "delivery_fulfillment_rate_percent" in data
    assert "lifecycle_breakdown" in data
    assert len(data["lifecycle_breakdown"]) >= 2
    assert "as_of" in data
