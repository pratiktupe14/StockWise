import os
import sys
from datetime import datetime, timezone, timedelta, date
import random

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, init_db
from app.models.entities import (
    Organization,
    Location,
    Product,
    Route,
    InventorySnapshot,
    SalesHistory,
    Shipment,
    StockMovement,
    ShipmentEvent,
)


def seed_demo_data(reset: bool = False, session=None):
    print("=" * 70)
    print(" StockWise Synthetic FMCG Scenario & Demo Generator")
    print("=" * 70)
    if not session:
        print("Initializing schema if required...")
        init_db()

    db = session or SessionLocal()
    try:
        today = datetime.now(timezone.utc).date()

        if reset:
            print("\n[RESET] Clearing previous synthetic demo records...")
            # Delete in foreign key dependency order
            db.query(ShipmentEvent).delete()
            db.query(StockMovement).delete()
            db.query(Shipment).delete()
            db.query(SalesHistory).delete()
            db.query(InventorySnapshot).delete()
            db.query(Route).delete()
            db.query(Location).delete()
            db.query(Product).delete()
            db.query(Organization).delete()
            db.commit()
            print("[RESET] Clean slate achieved.")

        # -----------------------------------------------------------------
        # 1. Organizations
        # -----------------------------------------------------------------
        print("\n1. Seeding Multi-Tenant Organizations...")
        orgs = [
            Organization(
                org_id="ORG-FMCG-CORP",
                name="Britannia FMCG Consumer Goods Ltd",
                org_type="fmcg_company",
                contact_email="supplychain@britannia.internal",
                is_active=True,
            ),
            Organization(
                org_id="ORG-LOGISTICS-3PL",
                name="TCI Surface & BlueDart Freight Consortium",
                org_type="logistics_provider",
                contact_email="dispatch@tci-bluedart.internal",
                is_active=True,
            ),
            Organization(
                org_id="ORG-DIST-WEST",
                name="Apex Metro FMCG Distributors (West Hub)",
                org_type="distributor",
                contact_email="orders@apexmetro.internal",
                is_active=True,
            ),
            Organization(
                org_id="ORG-RETAIL-METRO",
                name="Metro Mart Retail Hypermarkets Ltd",
                org_type="retailer",
                contact_email="storeops@metromart.internal",
                is_active=True,
            ),
        ]
        for o in orgs:
            db.merge(o)
        db.commit()
        print(f"   -> Seeded {len(orgs)} organizations across FMCG tiers.")

        # -----------------------------------------------------------------
        # 2. Master Products / SKUs
        # -----------------------------------------------------------------
        print("\n2. Seeding Finished Products Master Catalog...")
        products = [
            Product(
                sku_id="SKU-GOODDAY-100",
                name="Good Day Butter Cookies 120g",
                category="Biscuits",
                unit="cases",
                case_pack=24,
                shelf_life_days=180,
            ),
            Product(
                sku_id="SKU-NUTRICHOICE-200",
                name="NutriChoice Digestive 250g",
                category="Health Biscuits",
                unit="cases",
                case_pack=16,
                shelf_life_days=180,
            ),
            Product(
                sku_id="SKU-MARIEGOLD-300",
                name="Marie Gold Classic Tea Biscuit 300g",
                category="Biscuits",
                unit="cases",
                case_pack=30,
                shelf_life_days=240,
            ),
            Product(
                sku_id="SKU-WINKIES-400",
                name="Chocolate Swiss Roll Cake 45g",
                category="Cakes",
                unit="cases",
                case_pack=48,
                shelf_life_days=60,
            ),
            Product(
                sku_id="SKU-MILK-SHAKE-500",
                name="Strawberry Milkshake Tetra 200ml",
                category="Dairy",
                unit="cases",
                case_pack=24,
                shelf_life_days=90,
            ),
        ]
        for p in products:
            db.merge(p)
        db.commit()
        print(f"   -> Seeded {len(products)} SKUs with defined shelf-life baselines.")

        # -----------------------------------------------------------------
        # 3. Network Facilities & Locations
        # -----------------------------------------------------------------
        print("\n3. Seeding Network Multi-Tier Locations...")
        locs = [
            # Tier 1: Manufacturing Plant (Manufacturer Owned)
            Location(
                location_id="LOC-PLANT-KHOPOLI",
                name="Khopoli Mega Manufacturing Plant",
                location_type="manufacturing_plant",
                region="West",
                city="Khopoli",
                address="Plot 14, MIDC Industrial Area, Khopoli",
                owner_org_id="ORG-FMCG-CORP",
                operator_org_id="ORG-FMCG-CORP",
                storage_capacity_units=800000,
                dispatch_capacity_daily=40000,
                latitude=18.785,
                longitude=73.344,
                is_active=True,
            ),
            # Tier 2: Central Distribution Center (Manufacturer Owned)
            Location(
                location_id="LOC-NDC-BHIWANDI",
                name="Bhiwandi National Distribution Center",
                location_type="company_warehouse",
                region="West",
                city="Bhiwandi",
                address="Bhiwandi Logistics Hub, Sector 4, Thane",
                owner_org_id="ORG-FMCG-CORP",
                operator_org_id="ORG-FMCG-CORP",
                storage_capacity_units=500000,
                dispatch_capacity_daily=25000,
                latitude=19.297,
                longitude=73.064,
                is_active=True,
            ),
            # Tier 2: Regional C&F Buffer Depot
            Location(
                location_id="LOC-CNF-PUNE",
                name="Pune Regional C&F Depot",
                location_type="cnf_facility",
                region="West",
                city="Pune",
                address="Chakan Auto & FMCG Corridor, Pune",
                owner_org_id="ORG-FMCG-CORP",
                operator_org_id="ORG-LOGISTICS-3PL",
                storage_capacity_units=200000,
                dispatch_capacity_daily=10000,
                latitude=18.756,
                longitude=73.842,
                is_active=True,
            ),
            # Tier 3: Independent Distributor Hub (Distributor Owned)
            Location(
                location_id="LOC-DIST-WEST",
                name="Apex Metro Distribution Hub (West)",
                location_type="distributor",
                region="West",
                city="Mumbai",
                address="Kalyan FMCG Terminal, Mumbai East",
                owner_org_id="ORG-DIST-WEST",
                operator_org_id="ORG-DIST-WEST",
                storage_capacity_units=60000,
                dispatch_capacity_daily=6000,
                latitude=19.243,
                longitude=73.135,
                is_active=True,
            ),
            # Tier 4: Retail Hypermarket Store (Retailer Owned)
            Location(
                location_id="LOC-STORE-METRO",
                name="Metro Mart Retail Store #101",
                location_type="retailer",
                region="West",
                city="Mumbai",
                address="Phoenix Marketcity Mall, Kurla, Mumbai",
                owner_org_id="ORG-RETAIL-METRO",
                operator_org_id="ORG-RETAIL-METRO",
                storage_capacity_units=25000,
                dispatch_capacity_daily=1500,
                latitude=19.086,
                longitude=72.889,
                is_active=True,
            ),
        ]
        for l in locs:
            db.merge(l)
        db.commit()
        print(f"   -> Seeded {len(locs)} multi-tier facilities.")

        # -----------------------------------------------------------------
        # 4. Permitted Corridors & Freight Rates
        # -----------------------------------------------------------------
        print("\n4. Seeding Permitted Transport Corridors...")
        routes = [
            # Primary plant linehaul to DC (1 day, 2.20 INR/unit)
            Route(
                from_location_id="LOC-PLANT-KHOPOLI",
                to_location_id="LOC-NDC-BHIWANDI",
                carrier_agency_id="ORG-LOGISTICS-3PL",
                lead_time_days=1.0,
                cost_rate=2.20,
                capacity_units=20000,
                is_active=True,
                status_notes="Primary linehaul expressway shuttle",
            ),
            # Primary plant to Pune C&F (1 day, 2.50 INR/unit)
            Route(
                from_location_id="LOC-PLANT-KHOPOLI",
                to_location_id="LOC-CNF-PUNE",
                carrier_agency_id="ORG-LOGISTICS-3PL",
                lead_time_days=1.0,
                cost_rate=2.50,
                capacity_units=15000,
                is_active=True,
                status_notes="Expressway primary route",
            ),
            # NDC Bhiwandi to Distributor (1 day, 1.80 INR/unit)
            Route(
                from_location_id="LOC-NDC-BHIWANDI",
                to_location_id="LOC-DIST-WEST",
                carrier_agency_id="ORG-LOGISTICS-3PL",
                lead_time_days=1.0,
                cost_rate=1.80,
                capacity_units=8000,
                is_active=True,
                status_notes="Local distributor replenishment line",
            ),
            # Optimal replenishment corridor: NDC Bhiwandi to Retail Store (2 days, 3.20 INR/unit)
            Route(
                from_location_id="LOC-NDC-BHIWANDI",
                to_location_id="LOC-STORE-METRO",
                carrier_agency_id="ORG-LOGISTICS-3PL",
                lead_time_days=2.0,
                cost_rate=3.20,
                capacity_units=6000,
                is_active=True,
                status_notes="Secondary direct regional corridor",
            ),
            # Alternative route: Pune C&F to Retail Store (3 days, 4.80 INR/unit)
            Route(
                from_location_id="LOC-CNF-PUNE",
                to_location_id="LOC-STORE-METRO",
                carrier_agency_id="ORG-LOGISTICS-3PL",
                lead_time_days=3.0,
                cost_rate=4.80,
                capacity_units=4000,
                is_active=True,
                status_notes="Inter-district secondary corridor",
            ),
            # Higher-cost / slower alternative: Plant Direct to Retail Store (4 days, 6.50 INR/unit)
            Route(
                from_location_id="LOC-PLANT-KHOPOLI",
                to_location_id="LOC-STORE-METRO",
                carrier_agency_id="ORG-LOGISTICS-3PL",
                lead_time_days=4.0,
                cost_rate=6.50,
                capacity_units=3000,
                is_active=True,
                status_notes="Direct manufacturing bypass (high cost)",
            ),
        ]
        for r in routes:
            existing = db.query(Route).filter(
                Route.from_location_id == r.from_location_id,
                Route.to_location_id == r.to_location_id,
            ).first()
            if existing:
                existing.carrier_agency_id = r.carrier_agency_id
                existing.lead_time_days = r.lead_time_days
                existing.cost_rate = r.cost_rate
                existing.capacity_units = r.capacity_units
                existing.is_active = r.is_active
                existing.status_notes = r.status_notes
            else:
                db.add(r)
        db.commit()
        print(f"   -> Seeded {len(routes)} active transit routes with rates & lead times.")

        # -----------------------------------------------------------------
        # 5. Inventory Batches & Stock Positions
        # -----------------------------------------------------------------
        print("\n5. Seeding Inventory Batches & Stock Positions...")
        snap_id = f"SNAP-DEMO-{today.strftime('%Y%m%d')}"

        inventory_records = [
            # 1. Retail Store: Critically low on Good Day Cookies (only 35 units on hand against 25 units/day demand)
            InventorySnapshot(
                snapshot_id=snap_id,
                sku_id="SKU-GOODDAY-100",
                location_id="LOC-STORE-METRO",
                owner_org_id="ORG-RETAIL-METRO",
                on_hand=35.0,
                reserved=0.0,
                blocked=0.0,
                confirmed_incoming=0.0,
                batch_number="BAT-GD-STORE-01",
                expiry_date=today + timedelta(days=90),
                as_of_date=today,
            ),
            # Retail Store: Near-expiry Chocolate Cake (20 units expiring in 5 days!)
            InventorySnapshot(
                snapshot_id=snap_id,
                sku_id="SKU-WINKIES-400",
                location_id="LOC-STORE-METRO",
                owner_org_id="ORG-RETAIL-METRO",
                on_hand=20.0,
                reserved=0.0,
                blocked=0.0,
                confirmed_incoming=0.0,
                batch_number="BAT-WIN-STORE-NEAR",
                expiry_date=today + timedelta(days=5),
                as_of_date=today,
            ),
            # Retail Store: Healthy items
            InventorySnapshot(
                snapshot_id=snap_id,
                sku_id="SKU-NUTRICHOICE-200",
                location_id="LOC-STORE-METRO",
                owner_org_id="ORG-RETAIL-METRO",
                on_hand=180.0,
                reserved=0.0,
                blocked=0.0,
                confirmed_incoming=0.0,
                batch_number="BAT-NC-STORE-01",
                expiry_date=today + timedelta(days=120),
                as_of_date=today,
            ),
            # 2. Distributor Hub (Distributor-Owned Stock - Protected from Company Allocation)
            InventorySnapshot(
                snapshot_id=snap_id,
                sku_id="SKU-GOODDAY-100",
                location_id="LOC-DIST-WEST",
                owner_org_id="ORG-DIST-WEST",
                on_hand=400.0,
                reserved=0.0,
                blocked=0.0,
                confirmed_incoming=0.0,
                batch_number="BAT-GD-DIST-01",
                expiry_date=today + timedelta(days=100),
                as_of_date=today,
            ),
            # 3. National DC Bhiwandi (Fresh Company Stock - Eligible Source)
            InventorySnapshot(
                snapshot_id=snap_id,
                sku_id="SKU-GOODDAY-100",
                location_id="LOC-NDC-BHIWANDI",
                owner_org_id="ORG-FMCG-CORP",
                on_hand=4500.0,
                reserved=0.0,
                blocked=0.0,
                confirmed_incoming=0.0,
                batch_number="BAT-GD-BHI-FRESH",
                expiry_date=today + timedelta(days=150),
                as_of_date=today,
            ),
            # National DC Bhiwandi: Other SKUs
            InventorySnapshot(
                snapshot_id=snap_id,
                sku_id="SKU-WINKIES-400",
                location_id="LOC-NDC-BHIWANDI",
                owner_org_id="ORG-FMCG-CORP",
                on_hand=1500.0,
                reserved=0.0,
                blocked=0.0,
                confirmed_incoming=0.0,
                batch_number="BAT-WIN-BHI-01",
                expiry_date=today + timedelta(days=45),
                as_of_date=today,
            ),
            InventorySnapshot(
                snapshot_id=snap_id,
                sku_id="SKU-NUTRICHOICE-200",
                location_id="LOC-NDC-BHIWANDI",
                owner_org_id="ORG-FMCG-CORP",
                on_hand=2800.0,
                reserved=0.0,
                blocked=0.0,
                confirmed_incoming=0.0,
                batch_number="BAT-NC-BHI-01",
                expiry_date=today + timedelta(days=140),
                as_of_date=today,
            ),
            # 4. Pune Regional C&F
            InventorySnapshot(
                snapshot_id=snap_id,
                sku_id="SKU-GOODDAY-100",
                location_id="LOC-CNF-PUNE",
                owner_org_id="ORG-FMCG-CORP",
                on_hand=2000.0,
                reserved=200.0,
                blocked=100.0,
                confirmed_incoming=0.0,
                batch_number="BAT-GD-PUNE-01",
                expiry_date=today + timedelta(days=110),
                as_of_date=today,
            ),
            # 5. Khopoli Manufacturing Plant (Deep Buffer)
            InventorySnapshot(
                snapshot_id=snap_id,
                sku_id="SKU-GOODDAY-100",
                location_id="LOC-PLANT-KHOPOLI",
                owner_org_id="ORG-FMCG-CORP",
                on_hand=10000.0,
                reserved=500.0,
                blocked=200.0,
                confirmed_incoming=0.0,
                batch_number="BAT-GD-PLANT-01",
                expiry_date=today + timedelta(days=175),
                as_of_date=today,
            ),
        ]
        for inv in inventory_records:
            existing = db.query(InventorySnapshot).filter(
                InventorySnapshot.snapshot_id == inv.snapshot_id,
                InventorySnapshot.sku_id == inv.sku_id,
                InventorySnapshot.location_id == inv.location_id,
            ).first()
            if existing:
                existing.owner_org_id = inv.owner_org_id
                existing.on_hand = inv.on_hand
                existing.reserved = inv.reserved
                existing.blocked = inv.blocked
                existing.confirmed_incoming = inv.confirmed_incoming
                existing.batch_number = inv.batch_number
                existing.expiry_date = inv.expiry_date
                existing.as_of_date = inv.as_of_date
            else:
                db.add(inv)
        db.commit()
        print(f"   -> Seeded {len(inventory_records)} inventory positions across the network.")

        # -----------------------------------------------------------------
        # 6. Sales History (30 Days for Forecast & Stockout Detection)
        # -----------------------------------------------------------------
        print("\n6. Seeding 30 Days of Chronological Sales History...")
        random.seed(42)  # Deterministic seed for judge reproducibility
        start_date = today - timedelta(days=30)
        sales_records = []

        # Mean daily demand rates
        sales_targets = [
            ("SKU-GOODDAY-100", "LOC-STORE-METRO", 25.0),
            ("SKU-NUTRICHOICE-200", "LOC-STORE-METRO", 15.0),
            ("SKU-WINKIES-400", "LOC-STORE-METRO", 10.0),
            ("SKU-GOODDAY-100", "LOC-DIST-WEST", 60.0),
            ("SKU-NUTRICHOICE-200", "LOC-DIST-WEST", 35.0),
        ]

        # Clean prior demo sales history for these target SKUs and destinations
        for sku, dest, _ in sales_targets:
            db.query(SalesHistory).filter(
                SalesHistory.sku_id == sku,
                SalesHistory.destination_id == dest,
            ).delete(synchronize_session=False)
        db.commit()

        for sku, dest, mean_qty in sales_targets:
            for day in range(30):
                sale_date = start_date + timedelta(days=day)
                # Weekend surge (Friday & Saturday)
                weekday = sale_date.weekday()
                seasonality = 1.20 if weekday in (4, 5) else 0.92
                noise = random.uniform(-0.10, 0.10)
                qty = max(2.0, round(mean_qty * seasonality * (1.0 + noise), 1))
                sales_records.append(
                    SalesHistory(
                        sku_id=sku,
                        destination_id=dest,
                        sales_date=sale_date,
                        quantity=qty,
                    )
                )

        db.bulk_save_objects(sales_records)
        db.commit()
        print(f"   -> Seeded {len(sales_records)} daily sales records for demand models.")

        print("\n" + "=" * 70)
        print(" SYNTHETIC FMCG SCENARIO READY FOR DEMONSTRATION")
        print("=" * 70)
        print("Scenario Summary:")
        print(" - Product: Good Day Butter Cookies 120g (SKU-GOODDAY-100)")
        print(" - Destination: Metro Mart Store #101 (LOC-STORE-METRO)")
        print(f" - On-Hand Stock: 35.0 cases | Daily Demand: ~25.0 cases/day")
        print(f" - Cover Days: 1.4 days (CRITICAL STOCKOUT RISK < 2.0 DAYS)")
        print(f" - Optimal Upstream Source: Bhiwandi DC (LOC-NDC-BHIWANDI) with 4,500 unexpired cases")
        print(f" - Recommended Route: RTE-BHI-STORE (2.0 days lead time, 3.20 INR/unit)")
        print(f" - Near-Expiry Feature: Chocolate Swiss Roll (SKU-WINKIES-400) has 5d shelf life remaining")
        print("=" * 70)

    finally:
        if not session:
            db.close()


if __name__ == "__main__":
    reset_mode = "--reset" in sys.argv
    seed_demo_data(reset=reset_mode)
