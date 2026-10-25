"""
Regression Test Suite for StockWise Import Centre and Global Data Synchronization.

Covers:
1. Valid product import persists records and product API returns them.
2. Valid location import persists records and location API returns them.
3. Inventory import updates snapshot without duplicates (tracks inserted vs updated).
4. Sales History import correctly maps quantity and date fields; rejects invalid without manufacturing values.
5. Route & rate imports persist valid records with carrier ownership.
6. Organization import persists partners and organization API returns them.
7. File-level missing column and row validation rejection with useful errors.
8. Idempotent re-imports (duplicate files update records rather than multiplying keys).
9. Downstream API persistence verification.
10. Benchmark data isolation (benchmark records do not leak into operational inventory).
11. Tenant isolation (planner imports default to planner's organization).
12. Benchmark ingestion metadata contract (records_ingested & message).
"""

import io
from datetime import date, datetime, timezone, timedelta
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import Organization, Location, Product, InventorySnapshot

TEST_SECRET = "test-jwt-secret-for-imports-sync-must-be-at-least-32-chars!"


def make_jwt(
    sub: str = "USER-PLANNER-1",
    email: str = "planner@britannia.internal",
    role: str = "planner",
    org_id: str = "ORG-FMCG-CORP",
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=2)).timestamp()),
        "app_metadata": {"role": role, "org_id": org_id},
        "user_metadata": {},
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")


def auth_headers(sub="USER-1", email="user@test.internal", role="planner", org_id="ORG-FMCG-CORP"):
    token = make_jwt(sub=sub, email=email, role=role, org_id=org_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_jwt_env(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)


@pytest.fixture
def base_orgs(db_session: Session):
    """Seed default organizations required for foreign keys."""
    orgs = [
        Organization(org_id="ORG-FMCG-CORP", name="Britannia FMCG Corp", org_type="fmcg_company"),
        Organization(org_id="ORG-LOGISTICS-3PL", name="BlueDart 3PL", org_type="logistics_provider"),
        Organization(org_id="ORG-DIST-WEST", name="Apex West Distributors", org_type="distributor"),
        Organization(org_id="ORG-RETAIL-METRO", name="Metro Mart Retail", org_type="retailer"),
        Organization(org_id="BENCHMARK-COMPANY", name="Benchmark Corp", org_type="fmcg_company"),
    ]
    for org in orgs:
        db_session.merge(org)
    db_session.commit()
    return orgs


def test_1_product_import_and_downstream_api(client: TestClient, base_orgs):
    """1. A valid product import persists records and the product API returns them."""
    csv_data = (
        "sku_id,name,category,unit,case_pack,shelf_life_days\n"
        "SKU-SYNC-101,Marie Gold 100g,Biscuits,cases,24,180\n"
        "SKU-SYNC-102,Good Day Butter 50g,Biscuits,cases,48,240\n"
    )
    files = {"file": ("products.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    resp = client.post("/api/imports/products", files=files, headers=auth_headers(role="admin"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["valid_rows"] == 2
    assert data["inserted_rows"] == 2

    # Verify downstream API /api/products returns them
    prod_resp = client.get("/api/products", headers=auth_headers(role="planner"))
    assert prod_resp.status_code == 200
    items = prod_resp.json()
    sku_ids = [p["sku_id"] for p in items]
    assert "SKU-SYNC-101" in sku_ids
    assert "SKU-SYNC-102" in sku_ids


def test_2_location_import_and_downstream_api(client: TestClient, base_orgs):
    """2. A valid location import persists records and the location API returns them."""
    csv_data = (
        "location_id,name,location_type,region,city,owner_org_id,operator_org_id,storage_capacity_units,dispatch_capacity_daily\n"
        "LOC-SYNC-WH1,Bhiwandi Hub DC,company_warehouse,West,Mumbai,ORG-FMCG-CORP,ORG-FMCG-CORP,100000,5000\n"
        "LOC-SYNC-RET1,Andheri Store 1,retail_destination,West,Mumbai,ORG-RETAIL-METRO,ORG-RETAIL-METRO,2000,500\n"
    )
    files = {"file": ("locations.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    resp = client.post("/api/imports/locations", files=files, headers=auth_headers(role="admin"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["valid_rows"] == 2

    # Downstream API /api/locations
    loc_resp = client.get("/api/locations", headers=auth_headers(role="planner"))
    assert loc_resp.status_code == 200
    loc_items = loc_resp.json()
    loc_ids = [l["location_id"] for l in loc_items]
    assert "LOC-SYNC-WH1" in loc_ids
    assert "LOC-SYNC-RET1" in loc_ids


def test_3_inventory_import_and_idempotent_upsert(client: TestClient, base_orgs, db_session: Session):
    """3. Inventory import updates intended snapshot, tracks inserted vs updated, without duplicating records."""
    # First seed product and location
    prod = Product(sku_id="SKU-INV-1", name="NutriChoice 100g", category="Health", unit="cases", case_pack=12)
    loc = Location(location_id="LOC-INV-WH", name="Nagpur DC", location_type="company_warehouse", region="West", city="Nagpur", owner_org_id="ORG-FMCG-CORP", operator_org_id="ORG-FMCG-CORP")
    db_session.merge(prod)
    db_session.merge(loc)
    db_session.commit()

    csv_data = (
        "snapshot_id,location_id,sku_id,on_hand,reserved,blocked,batch_number\n"
        "SNAP-OP-01,LOC-INV-WH,SKU-INV-1,500,50,10,BATCH-001\n"
    )
    files = {"file": ("inventory.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    resp = client.post("/api/imports/inventory", files=files, headers=auth_headers(role="planner", org_id="ORG-FMCG-CORP"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_rows"] == 1
    assert data["inserted_rows"] == 1
    assert data["updated_rows"] == 0

    # Verify downstream /api/inventory
    inv_resp = client.get("/api/inventory", headers=auth_headers(role="planner", org_id="ORG-FMCG-CORP"))
    assert inv_resp.status_code == 200
    records = inv_resp.json()
    assert len(records) == 1
    assert records[0]["on_hand"] == 500
    assert records[0]["dispatchable_stock"] == 440  # 500 - 50 - 10
    assert records[0]["owner_org_id"] == "ORG-FMCG-CORP"

    # 7. Re-importing same file with updated on_hand must update, NOT duplicate
    csv_update = (
        "snapshot_id,location_id,sku_id,on_hand,reserved,blocked,batch_number\n"
        "SNAP-OP-01,LOC-INV-WH,SKU-INV-1,750,50,10,BATCH-001\n"
    )
    files2 = {"file": ("inventory.csv", io.BytesIO(csv_update.encode("utf-8")), "text/csv")}
    resp2 = client.post("/api/imports/inventory", files=files2, headers=auth_headers(role="planner", org_id="ORG-FMCG-CORP"))
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["valid_rows"] == 1
    assert data2["inserted_rows"] == 0
    assert data2["updated_rows"] == 1

    # Check total rows in DB is still 1
    inv_resp2 = client.get("/api/inventory", headers=auth_headers(role="planner", org_id="ORG-FMCG-CORP"))
    records2 = inv_resp2.json()
    assert len(records2) == 1
    assert records2[0]["on_hand"] == 750
    assert records2[0]["dispatchable_stock"] == 690


def test_4_sales_history_quantity_aliases_and_rejection(client: TestClient, base_orgs, db_session: Session):
    """4. Sales history maps aliases; rejects blank/negative quantity without manufacturing numbers."""
    prod = Product(sku_id="SKU-SALES-1", name="Tiger Crunch", category="Biscuits", unit="cases")
    loc = Location(location_id="LOC-SALES-RET", name="Retail Point", location_type="retail_destination", region="West")
    db_session.merge(prod)
    db_session.merge(loc)
    db_session.commit()

    # Valid CSV using order_quantity alias
    csv_valid = (
        "sku_id,location_id,date,order_quantity\n"
        "SKU-SALES-1,LOC-SALES-RET,2026-03-01,120\n"
    )
    files = {"file": ("sales.csv", io.BytesIO(csv_valid.encode("utf-8")), "text/csv")}
    resp = client.post("/api/imports/sales", files=files, headers=auth_headers(role="planner"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_rows"] == 1

    # Invalid CSV with empty quantity: must NOT manufacture numbers
    csv_empty_qty = (
        "sku_id,location_id,date,quantity\n"
        "SKU-SALES-1,LOC-SALES-RET,2026-03-02,\n"
        "SKU-SALES-1,LOC-SALES-RET,2026-03-03,-15\n"
    )
    files_inv = {"file": ("sales_invalid.csv", io.BytesIO(csv_empty_qty.encode("utf-8")), "text/csv")}
    resp_inv = client.post("/api/imports/sales", files=files_inv, headers=auth_headers(role="planner"))
    assert resp_inv.status_code == 200
    data_inv = resp_inv.json()
    assert data_inv["rejected_rows"] == 2
    assert data_inv["valid_rows"] == 0
    # Confirm error reasons
    errors = data_inv["errors"]
    error_codes = [e["error_code"] for e in errors]
    fields = [e["field_name"] for e in errors]
    assert "NEGATIVE_QUANTITY" in error_codes or "MISSING_FIELD" in error_codes
    assert "quantity" in fields


def test_5_route_import_and_carrier_ownership(client: TestClient, base_orgs, db_session: Session):
    """5. Route and rate imports persist valid records and preserve carrier ownership."""
    loc1 = Location(location_id="LOC-RT-SRC", name="Plant DC", location_type="manufacturing_plant", region="North")
    loc2 = Location(location_id="LOC-RT-DST", name="Depot DC", location_type="regional_warehouse", region="North")
    db_session.merge(loc1)
    db_session.merge(loc2)
    db_session.commit()

    csv_data = (
        "from_location_id,to_location_id,lead_time_days,cost_rate,capacity_units,carrier_agency_id\n"
        "LOC-RT-SRC,LOC-RT-DST,2.0,15.5,5000,ORG-LOGISTICS-3PL\n"
    )
    files = {"file": ("routes.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    resp = client.post("/api/imports/routes", files=files, headers=auth_headers(role="admin"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_rows"] == 1

    # Verify downstream /api/routes
    r_resp = client.get("/api/routes", headers=auth_headers(role="planner"))
    assert r_resp.status_code == 200
    routes = r_resp.json()
    found = [r for r in routes if r["from_location_id"] == "LOC-RT-SRC" and r["to_location_id"] == "LOC-RT-DST"]
    assert len(found) == 1
    assert found[0]["cost_rate"] == 15.5
    assert found[0]["carrier_agency_id"] == "ORG-LOGISTICS-3PL"


def test_6_organization_import_and_downstream_api(client: TestClient, base_orgs):
    """6. Organizations & Partners import persists records and downstream API returns them."""
    csv_data = (
        "org_id,name,org_type,contact_email,is_active\n"
        "ORG-NEW-DIST,New Distributor India,distributor,contact@newdist.com,true\n"
    )
    files = {"file": ("orgs.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    resp = client.post("/api/imports/organizations", files=files, headers=auth_headers(role="admin"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_rows"] == 1

    org_resp = client.get("/api/organizations", headers=auth_headers(role="planner"))
    assert org_resp.status_code == 200
    orgs = org_resp.json()
    assert any(o["org_id"] == "ORG-NEW-DIST" for o in orgs)


def test_7_missing_required_column_file_rejection(client: TestClient, base_orgs):
    """7. File missing mandatory column is rejected with MISSING_COLUMN error code."""
    # CSV missing required 'name' column
    csv_data = (
        "sku_id,category,unit\n"
        "SKU-BAD-1,Category A,cases\n"
    )
    files = {"file": ("products_bad.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    resp = client.post("/api/imports/products", files=files, headers=auth_headers(role="admin"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["valid_rows"] == 0
    assert len(data["errors"]) > 0
    assert data["errors"][0]["error_code"] == "MISSING_COLUMN"


def test_10_benchmark_isolation_from_operational_inventory(client: TestClient, base_orgs, db_session: Session):
    """10. Benchmark records under BENCHMARK-COMPANY cannot leak into operational company inventory results."""
    prod = Product(sku_id="SKU-BENCH-ISO", name="Benchmark SKU", category="Benchmark", unit="cases")
    loc = Location(location_id="LOC-BENCH-ISO", name="Benchmark WH", location_type="company_warehouse", region="National")
    db_session.merge(prod)
    db_session.merge(loc)
    db_session.commit()

    # Create 1 operational company inventory row and 1 benchmark inventory row
    op_inv = InventorySnapshot(
        snapshot_id="SNAP-OPERATIONAL-2026",
        location_id="LOC-BENCH-ISO",
        sku_id="SKU-BENCH-ISO",
        batch_number="OP-BATCH-1",
        on_hand=300,
        reserved=0,
        blocked=0,
        as_of_date=date.today(),
        owner_org_id="ORG-FMCG-CORP",
    )
    bench_inv = InventorySnapshot(
        snapshot_id="SNAP-BENCHMARK-PUBLIC",
        location_id="LOC-BENCH-ISO",
        sku_id="SKU-BENCH-ISO",
        batch_number="BENCH-BATCH-1",
        on_hand=9999,
        reserved=0,
        blocked=0,
        as_of_date=date.today(),
        owner_org_id="BENCHMARK-COMPANY",
    )
    db_session.add_all([op_inv, bench_inv])
    db_session.commit()

    # Query operational inventory as planner: must ONLY return company record
    planner_resp = client.get("/api/inventory", headers=auth_headers(role="planner", org_id="ORG-FMCG-CORP"))
    assert planner_resp.status_code == 200
    planner_items = planner_resp.json()
    assert len(planner_items) == 1
    assert planner_items[0]["snapshot_id"] == "SNAP-OPERATIONAL-2026"
    assert planner_items[0]["on_hand"] == 300

    # Query as admin without benchmark flag: must exclude benchmark records by default
    admin_resp = client.get("/api/inventory", headers=auth_headers(role="admin"))
    assert admin_resp.status_code == 200
    admin_items = admin_resp.json()
    snapshot_ids = [item["snapshot_id"] for item in admin_items]
    assert "SNAP-BENCHMARK-PUBLIC" not in snapshot_ids
    assert "SNAP-OPERATIONAL-2026" in snapshot_ids

    # Query as admin with include_benchmark=true: returns both
    admin_bench_resp = client.get("/api/inventory?include_benchmark=true", headers=auth_headers(role="admin"))
    assert admin_bench_resp.status_code == 200
    admin_bench_items = admin_bench_resp.json()
    bench_snapshot_ids = [item["snapshot_id"] for item in admin_bench_items]
    assert "SNAP-BENCHMARK-PUBLIC" in bench_snapshot_ids


def test_11_tenant_scoping_defaults_to_planner_company(client: TestClient, base_orgs, db_session: Session):
    """11. When a planner imports inventory without owner_org_id, it safely defaults to their own company."""
    prod = Product(sku_id="SKU-TENANT-1", name="Tenant SKU", category="Biscuits", unit="cases")
    loc = Location(location_id="LOC-TENANT-WH", name="Tenant WH", location_type="company_warehouse", region="South")
    db_session.merge(prod)
    db_session.merge(loc)
    db_session.commit()

    csv_data = (
        "snapshot_id,location_id,sku_id,on_hand,reserved,blocked,batch_number\n"
        "SNAP-TENANT-01,LOC-TENANT-WH,SKU-TENANT-1,400,0,0,BATCH-T1\n"
    )
    files = {"file": ("inv_tenant.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    resp = client.post("/api/imports/inventory", files=files, headers=auth_headers(role="planner", org_id="ORG-FMCG-CORP"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_rows"] == 1

    # Verify DB record owner_org_id is ORG-FMCG-CORP
    db_rec = db_session.query(InventorySnapshot).filter_by(snapshot_id="SNAP-TENANT-01").first()
    assert db_rec is not None
    assert db_rec.owner_org_id == "ORG-FMCG-CORP"


def test_12_benchmark_ingestion_endpoint_contract(client: TestClient, base_orgs):
    """12. Benchmark ingestion endpoint returns valid records_ingested and message for UI toast."""
    payload = {"source_id": "fmcg_distribution_benchmark_v1", "clean_slate": False}
    resp = client.post("/api/imports/benchmarks/ingest", json=payload, headers=auth_headers(role="admin"))
    assert resp.status_code == 200
    data = resp.json()
    assert "records_ingested" in data
    assert "message" in data
    assert data["records_ingested"] >= 0
