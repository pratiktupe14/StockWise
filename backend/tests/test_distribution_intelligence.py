import io
import json
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
)


def _seed_basic_network(client: TestClient):
    """Helper to seed a valid FMCG network with company, distributor, locations, and products."""
    # 1. Organizations
    client.post("/api/organizations", json={"org_id": "ORG-FMCG", "name": "Global FMCG Corp", "org_type": "fmcg_company"})
    client.post("/api/organizations", json={"org_id": "ORG-DIST-1", "name": "Metro Distribution Partner", "org_type": "independent_distributor"})
    client.post("/api/organizations", json={"org_id": "ORG-3PL", "name": "SpeedLogistics 3PL", "org_type": "logistics_provider"})

    # 2. Locations
    # Central Plant (Source)
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-PLANT-MUM",
            "name": "Mumbai Central Plant",
            "location_type": "central_plant",
            "region": "West",
            "city": "Mumbai",
            "owner_org_id": "ORG-FMCG",
            "operator_org_id": "ORG-FMCG",
            "storage_capacity_units": 500000,
            "dispatch_capacity_daily": 20000,
            "is_active": True,
        },
    )
    # Regional Warehouse (Source/Buffer)
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-RDC-PUNE",
            "name": "Pune Regional DC",
            "location_type": "regional_warehouse",
            "region": "West",
            "city": "Pune",
            "owner_org_id": "ORG-FMCG",
            "operator_org_id": "ORG-FMCG",
            "storage_capacity_units": 100000,
            "dispatch_capacity_daily": 5000,
            "is_active": True,
        },
    )
    # Retail Destination / Distributor Warehouse (Destination)
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-RET-NAGPUR",
            "name": "Nagpur Metro Depot",
            "location_type": "retail_destination",
            "region": "West",
            "city": "Nagpur",
            "owner_org_id": "ORG-DIST-1",
            "operator_org_id": "ORG-DIST-1",
            "storage_capacity_units": 30000,
            "dispatch_capacity_daily": 2000,
            "is_active": True,
        },
    )

    # 3. Product
    client.post(
        "/api/imports/products",
        files={"file": ("products.csv", io.BytesIO(b"sku_id,name,category,unit,case_pack,shelf_life_days\nSKU-JUICE-100,Orange Juice 1L,Beverages,cases,12,90\n"), "text/csv")},
    )


def test_ac1_insufficient_stock_correct_demand_gap(client: TestClient, db_session: Session):
    """
    AC 1: A destination with insufficient stock receives a correct demand-gap calculation.
    Demand Gap = max(0, total_forecast_demand - (dispatchable_stock + confirmed_incoming))
    """
    _seed_basic_network(client)

    # Seed 14 days of sales history (20 cases/day) for SKU-JUICE-100 at LOC-RET-NAGPUR
    base_date = (datetime.now(timezone.utc) - timedelta(days=15)).date()
    for day in range(14):
        s_date = base_date + timedelta(days=day)
        db_session.add(
            SalesHistory(
                sku_id="SKU-JUICE-100",
                destination_id="LOC-RET-NAGPUR",
                sales_date=s_date,
                quantity=20.0,
            )
        )
    db_session.commit()

    # Destination has 40 cases dispatchable stock (OH=50, Res=10, Blk=0) and 0 confirmed incoming
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-AC1-1",
            sku_id="SKU-JUICE-100",
            location_id="LOC-RET-NAGPUR",
            on_hand=50.0,
            reserved=10.0,
            blocked=0.0,
            confirmed_incoming=0.0,
            as_of_date=datetime.now(timezone.utc).date(),
            owner_org_id="ORG-DIST-1",
        )
    )
    db_session.commit()

    # Query Risk Analysis for 7-day horizon:
    # Daily forecast = 20.0, 7-day total demand = 140.0 cases.
    # Eligible stock = 40.0.
    # Projected Demand Gap = 140.0 - 40.0 = 100.0 cases.
    resp = client.get("/api/risk/analysis?horizon_days=7&destination_id=LOC-RET-NAGPUR&sku_id=SKU-JUICE-100")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["total_forecast_demand"] == 140.0
    assert item["dispatchable_stock"] == 40.0
    assert item["demand_gap"] == 100.0
    assert item["cover_days"] == 2.0  # 40 / 20 = 2 days of cover


def test_ac2_reserved_and_blocked_inventory_cannot_be_allocated(client: TestClient, db_session: Session):
    """
    AC 2: Reserved and blocked inventory cannot be allocated.
    Source has 500 On-Hand, but 300 Reserved + 200 Blocked => Dispatchable Stock = 0.
    Optimizer must not allocate any stock from this source.
    """
    _seed_basic_network(client)

    # Active route from Plant to Nagpur: lead time 2 days, cost $4.00
    r_resp = client.post(
        "/api/network/routes",
        json={
            "from_location_id": "LOC-PLANT-MUM",
            "to_location_id": "LOC-RET-NAGPUR",
            "lead_time_days": 2.0,
            "cost_rate": 4.0,
            "is_active": True,
        },
    )
    assert r_resp.status_code == 201

    # Destination has 100 cases demand gap (via sales history)
    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(
            SalesHistory(
                sku_id="SKU-JUICE-100",
                destination_id="LOC-RET-NAGPUR",
                sales_date=base_date + timedelta(days=day),
                quantity=15.0,
            )
        )

    # Source has 500 On-Hand, but 300 Reserved and 200 Blocked => 0 dispatchable!
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-AC2-SRC",
            sku_id="SKU-JUICE-100",
            location_id="LOC-PLANT-MUM",
            on_hand=500.0,
            reserved=300.0,
            blocked=200.0,
            confirmed_incoming=0.0,
            as_of_date=datetime.now(timezone.utc).date(),
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    # Run optimization
    opt_resp = client.post(
        "/api/optimization/run",
        json={"horizon_days": 7, "objective_strategy": "service-first"},
    )
    assert opt_resp.status_code == 201
    plan = opt_resp.json()

    # Zero units should be allocated from LOC-PLANT-MUM because dispatchable stock is 0
    assert plan["fulfilled_demand_units"] == 0.0
    assert len(plan["recommended_shipments"]) == 0
    assert plan["unmet_demand_units"] > 0.0

    # Verify unmet demand breakdown explicitly notes 0 dispatchable stock
    assert len(plan["unmet_demand_breakdown"]) == 1
    unmet_item = plan["unmet_demand_breakdown"][0]
    assert any("0.0 dispatchable stock" in r for r in unmet_item["reasons"])


def test_ac3_inactive_or_forbidden_route_cannot_be_used(client: TestClient, db_session: Session):
    """
    AC 3: An inactive or forbidden route cannot be used.
    Source has ample stock (1,000 cases), but the route is marked is_active=False.
    """
    _seed_basic_network(client)

    # Inactive route
    r_resp = client.post(
        "/api/network/routes",
        json={
            "from_location_id": "LOC-PLANT-MUM",
            "to_location_id": "LOC-RET-NAGPUR",
            "lead_time_days": 2.0,
            "cost_rate": 3.5,
            "is_active": False,  # INACTIVE!
        },
    )
    assert r_resp.status_code == 201

    # Sales history creating demand
    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(
            SalesHistory(
                sku_id="SKU-JUICE-100",
                destination_id="LOC-RET-NAGPUR",
                sales_date=base_date + timedelta(days=day),
                quantity=10.0,
            )
        )

    # Plant has 1000 dispatchable cases
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-AC3-SRC",
            sku_id="SKU-JUICE-100",
            location_id="LOC-PLANT-MUM",
            on_hand=1000.0,
            reserved=0.0,
            blocked=0.0,
            as_of_date=datetime.now(timezone.utc).date(),
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    # Run optimization
    opt_resp = client.post("/api/optimization/run", json={"horizon_days": 7})
    assert opt_resp.status_code == 201
    plan = opt_resp.json()

    # Route must NOT be used
    assert plan["fulfilled_demand_units"] == 0.0
    assert len(plan["recommended_shipments"]) == 0
    assert any("unpermitted or marked inactive" in r for r in plan["unmet_demand_breakdown"][0]["reasons"])


def test_ac4_route_arriving_after_cutoff_is_excluded(client: TestClient, db_session: Session):
    """
    AC 4: A route arriving after the demand cutoff is excluded.
    Planning horizon is 7 days; route lead time is 9 days (exceeds cutoff).
    """
    _seed_basic_network(client)

    # Route with 9 days lead time (> 7 days horizon)
    r_resp = client.post(
        "/api/network/routes",
        json={
            "from_location_id": "LOC-PLANT-MUM",
            "to_location_id": "LOC-RET-NAGPUR",
            "lead_time_days": 9.0,  # EXCEEDS 7-DAY HORIZON!
            "cost_rate": 2.5,
            "is_active": True,
        },
    )
    assert r_resp.status_code == 201

    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(
            SalesHistory(
                sku_id="SKU-JUICE-100",
                destination_id="LOC-RET-NAGPUR",
                sales_date=base_date + timedelta(days=day),
                quantity=10.0,
            )
        )

    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-AC4-SRC",
            sku_id="SKU-JUICE-100",
            location_id="LOC-PLANT-MUM",
            on_hand=1000.0,
            reserved=0.0,
            blocked=0.0,
            as_of_date=datetime.now(timezone.utc).date(),
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    # Run optimization for 7-day horizon
    opt_resp = client.post("/api/optimization/run", json={"horizon_days": 7})
    assert opt_resp.status_code == 201
    plan = opt_resp.json()

    # Corridor must be excluded due to temporal cutoff
    assert plan["fulfilled_demand_units"] == 0.0
    assert len(plan["recommended_shipments"]) == 0
    assert any("exceeds 7-day cutoff" in r for r in plan["unmet_demand_breakdown"][0]["reasons"])


def test_ac5_source_inventory_cannot_be_overallocated(client: TestClient, db_session: Session):
    """
    AC 5: Source inventory cannot be overallocated across destinations.
    Source has 100 cases dispatchable stock.
    Two destinations each have a 80-case demand gap (total 160 cases).
    Total allocated from source must be <= 100 cases.
    """
    _seed_basic_network(client)

    # Register second destination
    client.post(
        "/api/network/locations",
        json={
            "location_id": "LOC-RET-NASHIK",
            "name": "Nashik Retail Hub",
            "location_type": "retail_destination",
            "region": "West",
            "city": "Nashik",
            "is_active": True,
        },
    )

    # Routes to both destinations
    client.post(
        "/api/network/routes",
        json={"from_location_id": "LOC-PLANT-MUM", "to_location_id": "LOC-RET-NAGPUR", "lead_time_days": 2.0, "cost_rate": 4.0, "is_active": True},
    )
    client.post(
        "/api/network/routes",
        json={"from_location_id": "LOC-PLANT-MUM", "to_location_id": "LOC-RET-NASHIK", "lead_time_days": 1.0, "cost_rate": 2.0, "is_active": True},
    )

    # Sales history: ~11.4 cases/day => 80 cases over 7 days for each destination
    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(SalesHistory(sku_id="SKU-JUICE-100", destination_id="LOC-RET-NAGPUR", sales_date=base_date + timedelta(days=day), quantity=11.43))
        db_session.add(SalesHistory(sku_id="SKU-JUICE-100", destination_id="LOC-RET-NASHIK", sales_date=base_date + timedelta(days=day), quantity=11.43))

    # Source has strictly 100 cases
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-AC5-SRC",
            sku_id="SKU-JUICE-100",
            location_id="LOC-PLANT-MUM",
            on_hand=100.0,
            reserved=0.0,
            blocked=0.0,
            as_of_date=datetime.now(timezone.utc).date(),
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    # Run optimization
    opt_resp = client.post("/api/optimization/run", json={"horizon_days": 7})
    assert opt_resp.status_code == 201
    plan = opt_resp.json()

    # Total fulfilled must NOT exceed 100.0 cases!
    total_allocated = sum(s["quantity"] for s in plan["recommended_shipments"])
    assert total_allocated <= 100.0
    assert plan["fulfilled_demand_units"] <= 100.0
    assert plan["unmet_demand_units"] >= 59.0  # Around 60 cases unmet out of 160


def test_ac6_confirmed_incoming_counted_only_when_eligible_and_only_once(client: TestClient, db_session: Session):
    """
    AC 6: Confirmed incoming inventory is counted only when eligible and only once.
    Destination needs 140 cases. Has 0 on-hand, but 40 confirmed incoming.
    Projected demand gap is exactly 100 cases (not 140, and not reduced twice).
    """
    _seed_basic_network(client)

    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(
            SalesHistory(
                sku_id="SKU-JUICE-100",
                destination_id="LOC-RET-NAGPUR",
                sales_date=base_date + timedelta(days=day),
                quantity=20.0,
            )
        )

    # Destination has 40 confirmed incoming
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-AC6-DEST",
            sku_id="SKU-JUICE-100",
            location_id="LOC-RET-NAGPUR",
            on_hand=0.0,
            reserved=0.0,
            blocked=0.0,
            confirmed_incoming=40.0,
            as_of_date=datetime.now(timezone.utc).date(),
            owner_org_id="ORG-DIST-1",
        )
    )
    db_session.commit()

    risk_resp = client.get("/api/risk/analysis?horizon_days=7&destination_id=LOC-RET-NAGPUR")
    assert risk_resp.status_code == 200
    item = risk_resp.json()["items"][0]
    # Forecast = 140.0, Confirmed Incoming = 40.0 => Gap = 100.0
    assert item["total_forecast_demand"] == 140.0
    assert item["confirmed_incoming"] == 40.0
    assert item["demand_gap"] == 100.0


def test_ac7_distributor_owned_inventory_not_treated_as_company_stock(client: TestClient, db_session: Session):
    """
    AC 7: Distributor-owned inventory is not incorrectly treated as company-owned stock.
    A distributor depot holds 500 cases, but owner_org_id is an independent distributor.
    The company optimizer cannot re-allocate distributor stock to other nodes.
    """
    _seed_basic_network(client)

    # Route from Distributor depot to another destination
    client.post(
        "/api/network/locations",
        json={"location_id": "LOC-RET-WARDHA", "name": "Wardha Outlet", "location_type": "retail_destination", "region": "West", "city": "Wardha", "is_active": True},
    )
    r_resp = client.post(
        "/api/network/routes",
        json={"from_location_id": "LOC-RET-NAGPUR", "to_location_id": "LOC-RET-WARDHA", "lead_time_days": 1.0, "cost_rate": 2.0, "is_active": True},
    )
    assert r_resp.status_code == 201

    # Wardha has demand
    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(SalesHistory(sku_id="SKU-JUICE-100", destination_id="LOC-RET-WARDHA", sales_date=base_date + timedelta(days=day), quantity=10.0))

    # Distributor depot has 500 cases owned by independent distributor
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-AC7-DIST",
            sku_id="SKU-JUICE-100",
            location_id="LOC-RET-NAGPUR",
            on_hand=500.0,
            reserved=0.0,
            blocked=0.0,
            as_of_date=datetime.now(timezone.utc).date(),
            owner_org_id="ORG-DIST-1",  # INDEPENDENT DISTRIBUTOR OWNER!
        )
    )
    db_session.commit()

    # Run optimization
    opt_resp = client.post("/api/optimization/run", json={"horizon_days": 7})
    assert opt_resp.status_code == 201
    plan = opt_resp.json()

    # Distributor stock must NOT be allocated to fulfill external company demand
    assert plan["fulfilled_demand_units"] == 0.0
    assert len(plan["unmet_demand_breakdown"]) >= 1
    assert any("Distributor-owned stock" in r for r in plan["unmet_demand_breakdown"][0]["reasons"])


def test_ac8_infeasible_supply_produces_explicit_unmet_demand(client: TestClient, db_session: Session):
    """
    AC 8: Infeasible supply produces explicit unmet demand.
    Demand is 140 cases, but total network supply is only 50 cases.
    Optimizer fulfills 50 cases and explicitly reports 90 cases unmet demand.
    """
    _seed_basic_network(client)

    r_resp = client.post(
        "/api/network/routes",
        json={"from_location_id": "LOC-PLANT-MUM", "to_location_id": "LOC-RET-NAGPUR", "lead_time_days": 2.0, "cost_rate": 3.0, "is_active": True},
    )
    assert r_resp.status_code == 201

    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(SalesHistory(sku_id="SKU-JUICE-100", destination_id="LOC-RET-NAGPUR", sales_date=base_date + timedelta(days=day), quantity=20.0))

    # Supply is strictly 50 cases
    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-AC8-SRC",
            sku_id="SKU-JUICE-100",
            location_id="LOC-PLANT-MUM",
            on_hand=50.0,
            reserved=0.0,
            blocked=0.0,
            as_of_date=datetime.now(timezone.utc).date(),
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    opt_resp = client.post("/api/optimization/run", json={"horizon_days": 7})
    assert opt_resp.status_code == 201
    plan = opt_resp.json()

    assert plan["fulfilled_demand_units"] == 50.0
    assert plan["unmet_demand_units"] == 90.0
    assert plan["service_level_percent"] == 35.7  # 50 / 140 = 35.7%
    assert len(plan["unmet_demand_breakdown"]) == 1
    assert plan["unmet_demand_breakdown"][0]["unmet_quantity"] == 90.0


def test_ac9_forecast_identifies_insufficient_historical_data(client: TestClient, db_session: Session):
    """
    AC 9: Forecasts identify insufficient historical data (< 7 days) and zero demand.
    """
    _seed_basic_network(client)

    # 1. Series with only 3 days of sales (< 7 threshold)
    base_date = (datetime.now(timezone.utc) - timedelta(days=5)).date()
    for day in range(3):
        db_session.add(
            SalesHistory(
                sku_id="SKU-JUICE-100",
                destination_id="LOC-RET-NAGPUR",
                sales_date=base_date + timedelta(days=day),
                quantity=10.0,
            )
        )
    db_session.commit()

    resp = client.get("/api/forecast?horizon_days=7&destination_id=LOC-RET-NAGPUR&sku_id=SKU-JUICE-100")
    assert resp.status_code == 200
    data = resp.json()
    # Find item for SKU-JUICE-100 at LOC-RET-NAGPUR
    items = [f for f in data["forecasts"] if f["sku_id"] == "SKU-JUICE-100" and f["destination_id"] == "LOC-RET-NAGPUR"]
    assert len(items) == 1
    item = items[0]
    assert item["data_sufficiency"] == "insufficient_history"
    assert item["forecast_method"] == "sparse_mean"
    assert "Limited sample size" in item["assumptions"]


def test_ac10_baseline_and_optimizer_use_identical_constraints_and_input_snapshot(client: TestClient, db_session: Session):
    """
    AC 10: The baseline and optimizer use identical constraints and input snapshots.
    Compare metrics: fill rate, unmet demand, transport cost, stock utilization, constraint violations.
    """
    _seed_basic_network(client)

    r_resp = client.post(
        "/api/network/routes",
        json={"from_location_id": "LOC-PLANT-MUM", "to_location_id": "LOC-RET-NAGPUR", "lead_time_days": 2.0, "cost_rate": 3.5, "is_active": True},
    )
    assert r_resp.status_code == 201

    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(SalesHistory(sku_id="SKU-JUICE-100", destination_id="LOC-RET-NAGPUR", sales_date=base_date + timedelta(days=day), quantity=20.0))

    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-AC10-SRC",
            sku_id="SKU-JUICE-100",
            location_id="LOC-PLANT-MUM",
            on_hand=300.0,
            reserved=0.0,
            blocked=0.0,
            as_of_date=datetime.now(timezone.utc).date(),
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    opt_resp = client.post("/api/optimization/run", json={"horizon_days": 7})
    assert opt_resp.status_code == 201
    plan = opt_resp.json()

    comparison = plan["baseline_comparison"]
    assert comparison is not None
    assert "optimizer" in comparison
    assert "baseline" in comparison

    opt_metrics = comparison["optimizer"]
    base_metrics = comparison["baseline"]

    # Both must evaluate against identical demand and report 0 constraint violations
    assert opt_metrics["constraint_violations_count"] == 0
    assert base_metrics["constraint_violations_count"] == 0
    assert opt_metrics["fulfilled_demand_units"] == base_metrics["fulfilled_demand_units"]
    assert opt_metrics["service_level_percent"] == 100.0
    assert base_metrics["service_level_percent"] == 100.0


def test_ac11_every_proposed_shipment_has_decision_receipt(client: TestClient, db_session: Session):
    """
    AC 11: Every proposed shipment has a Decision Receipt containing structured evidence.
    """
    _seed_basic_network(client)

    r_resp = client.post(
        "/api/network/routes",
        json={"from_location_id": "LOC-PLANT-MUM", "to_location_id": "LOC-RET-NAGPUR", "lead_time_days": 2.0, "cost_rate": 4.5, "is_active": True},
    )
    assert r_resp.status_code == 201

    base_date = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    for day in range(8):
        db_session.add(SalesHistory(sku_id="SKU-JUICE-100", destination_id="LOC-RET-NAGPUR", sales_date=base_date + timedelta(days=day), quantity=25.0))

    db_session.add(
        InventorySnapshot(
            snapshot_id="SNAP-AC11-SRC",
            sku_id="SKU-JUICE-100",
            location_id="LOC-PLANT-MUM",
            on_hand=500.0,
            reserved=0.0,
            blocked=0.0,
            as_of_date=datetime.now(timezone.utc).date(),
            owner_org_id="ORG-FMCG",
        )
    )
    db_session.commit()

    opt_resp = client.post("/api/optimization/run", json={"horizon_days": 7})
    assert opt_resp.status_code == 201
    plan = opt_resp.json()

    run_id = plan["run_id"]
    receipts_resp = client.get(f"/api/optimization/runs/{run_id}/receipts")
    assert receipts_resp.status_code == 200
    receipts = receipts_resp.json()

    assert len(receipts) == len(plan["recommended_shipments"])
    assert len(receipts) >= 1

    rcpt = receipts[0]
    assert rcpt["sku_id"] == "SKU-JUICE-100"
    assert rcpt["source_location_id"] == "LOC-PLANT-MUM"
    assert rcpt["destination_location_id"] == "LOC-RET-NAGPUR"
    assert rcpt["lead_time_days"] == 2.0
    assert rcpt["estimated_cost"] > 0
    assert "evidence" in rcpt and len(rcpt["evidence"]) > 10
    assert isinstance(rcpt["rejected_alternatives"], list)


def test_ac12_all_three_portals_and_existing_functionality_preserved(client: TestClient):
    """
    AC 12: All three portals and existing Phase 2 functionality continue to work.
    1. Company Admin: Organization and Network management.
    2. Warehouse & Logistics: Inbound/outbound shipments and inventory tracking.
    3. Distribution Intelligence: Planning runs, forecast, risk analysis.
    """
    # 1. Company Admin Endpoints
    orgs = client.get("/api/organizations").json()
    assert isinstance(orgs, list)
    locs = client.get("/api/network/locations").json()
    assert isinstance(locs, list)
    routes = client.get("/api/network/routes").json()
    assert isinstance(routes, list)

    # 2. Warehouse & Logistics Endpoints
    shipments = client.get("/api/shipments").json()
    assert isinstance(shipments, list)
    inv = client.get("/api/inventory").json()
    assert isinstance(inv, list)

    # 3. Distribution Intelligence Endpoints
    fc = client.get("/api/forecast").json()
    assert "forecasts" in fc
    risk = client.get("/api/risk/analysis").json()
    assert "items" in risk
    runs = client.get("/api/optimization/runs").json()
    assert isinstance(runs, list)
