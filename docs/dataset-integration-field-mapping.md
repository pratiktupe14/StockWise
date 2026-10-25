# StockWise FMCG Distribution Intelligence Platform
## Real Dataset Integration Audit & Canonical Field Mapping Specification

**Document Version:** 1.0.0  
**Status:** Approved & Enforced  
**Audit Scope:** Products, Locations, Organizations, Inventory, Sales, Routes, Optimization, Portals, Logistics Execution, and Analytics.

---

## 1. Executive Summary & Audit Purpose

The purpose of this audit is to systematically map real-world public datasets and verified geographic information into the existing StockWise FMCG Distribution Intelligence Platform.

StockWise requires strict architectural discipline:
1. **Zero Data Fabrication:** Public benchmark data, simulated scenarios, and estimates must never be masqueraded as genuine company operational records.
2. **Strict Category Separation:**
   - **Public Benchmark Data:** Real public transaction histories (e.g., UCI Online Retail II, Dingdong FreshRetailNet, Kaggle M5) used for statistical model training, baseline benchmarking, and algorithm evaluation.
   - **Verified Geographic Data:** OpenStreetMap (OSM) nodes and OSRM highway distance measurements used for accurate route road lengths.
   - **Company Operational Data:** Authorized private corporate master data (ERP inventory snapshots, actual batch numbers, negotiated carrier contracts, physical proof-of-delivery).
   - **Configurable Estimates:** Explicitly designated freight and handling rate cards used strictly for scenario comparison when company rate cards have not yet been uploaded.
3. **Preservation of Existing Architecture:** No breaking database migrations, duplicate entity models, or loss of role-based tenant isolation.

---

## 2. Codebase & Architectural Audit

### 2.1 Products and SKUs (`products` table)
- **Primary Model:** `app.models.entities.Product`
- **Fields:**
  - `sku_id` (VARCHAR(64), Primary Key)
  - `name` (VARCHAR(255), Not Null)
  - `category` (VARCHAR(128), Nullable, default 'General')
  - `unit` (VARCHAR(32), Not Null, default 'cases')
  - `case_pack` (INTEGER, Not Null, default 1)
  - `shelf_life_days` (INTEGER, Nullable)
- **Downstream Usages:** Inventory snapshots, sales histories, route eligibility, optimization demand variables, and festival category uplifts.

### 2.2 Organizations (`organizations` table)
- **Primary Model:** `app.models.entities.Organization`
- **Fields:**
  - `org_id` (VARCHAR(64), Primary Key)
  - `name` (VARCHAR(255), Not Null)
  - `org_type` (VARCHAR(64), Not Null): `fmcg_company`, `cnf_agency`, `logistics_provider`, `distributor`, `retailer`
  - `contact_email`, `contact_phone`, `is_active`
- **Downstream Usages:** Multi-tenant portals, facility ownership, route carrier agency assignment, shipment owner separation.

### 2.3 Network Locations (`locations` table)
- **Primary Model:** `app.models.entities.Location`
- **Fields:**
  - `location_id` (VARCHAR(64), Primary Key)
  - `name` (VARCHAR(255), Not Null)
  - `location_type` (VARCHAR(64), Not Null): `manufacturing_plant`, `company_warehouse`, `central_warehouse`, `regional_warehouse`, `cnf_facility`, `3pl_facility`, `distributor_warehouse`, `retail_destination`
  - `region` (VARCHAR(128), Not Null)
  - `city` (VARCHAR(128), Nullable)
  - `address` (VARCHAR(255), Nullable)
  - `owner_org_id`, `operator_org_id` (Foreign Keys to `organizations`)
  - `storage_capacity_units` (FLOAT, Nullable)
  - `dispatch_capacity_daily` (FLOAT, Nullable)
  - `latitude`, `longitude` (FLOAT, Nullable)
  - `is_active` (BOOLEAN, default True)
- **Downstream Usages:** Source-destination routing, geographic distance calculation, facility capacity constraints in LP optimizer.

### 2.4 Inventory Balances & Expiry Batches (`inventory_snapshots` table)
- **Primary Model:** `app.models.entities.InventorySnapshot`
- **Fields:**
  - `snapshot_id` (VARCHAR(64), Not Null)
  - `sku_id` (VARCHAR(64), FK `products`)
  - `location_id` (VARCHAR(64), FK `locations`)
  - `owner_org_id` (VARCHAR(64), FK `organizations`)
  - `on_hand` (FLOAT, Not Null)
  - `reserved` (FLOAT, Not Null)
  - `blocked` (FLOAT, Not Null)
  - `confirmed_incoming` (FLOAT, Not Null)
  - `batch_number` (VARCHAR(64), Nullable)
  - `expiry_date` (DATE, Nullable)
  - `as_of_date` (DATE, Not Null)
- **Core Formula Enforced:**
  $$\text{dispatchable\_stock} = \max(0.0, \text{on\_hand} - \text{reserved} - \text{blocked})$$
  Incoming stock and in-transit units are strictly excluded from current dispatchable stock.

### 2.5 Sales History & Demand Forecasting (`sales_history` table)
- **Primary Model:** `app.models.entities.SalesHistory`
- **Fields:**
  - `sku_id` (VARCHAR(64), FK `products`)
  - `destination_id` (VARCHAR(64), FK `locations`)
  - `sales_date` (DATE, Not Null)
  - `quantity` (FLOAT, Not Null)
- **Forecasting Pipeline (`forecast_service.py`):**
  - Grouped by `(sku_id, destination_id)` time series.
  - Baselines: 7-day Rolling Moving Average (`moving_average_7d`) and Day-of-Week cyclical lag (`seasonal_naive_7d`).
  - Strict temporal boundary: Out-of-sample holdout validation without lookahead leakage.
  - Evaluation Metrics: MAE (Mean Absolute Error) and WAPE (Weighted Absolute Percentage Error).

### 2.6 Routes & Transport Costs (`routes` table)
- **Primary Model:** `app.models.entities.Route`
- **Fields:**
  - `from_location_id`, `to_location_id` (FKs `locations`, unique pair)
  - `carrier_agency_id` (FK `organizations`)
  - `lead_time_days` (FLOAT, Not Null, strictly > 0)
  - `cost_rate` (FLOAT, Not Null, >= 0)
  - `capacity_units` (FLOAT, Nullable)
  - `sku_eligibility` (VARCHAR(255), default 'all')
  - `pricing_basis` (VARCHAR(64), default 'per_unit')
  - `min_shipment_qty`, `max_shipment_qty`
- **Distance & Cost Engine:** OpenStreetMap node coordinates with OSRM road distance routing (fallback: road-adjusted Haversine, winding factor 1.25).

### 2.7 Optimization & Decision Receipts (`planning_runs`, `shipments`, `stock_movements`)
- **Optimization Engine (`optimizer_service.py`):**
  - 2-Stage Lexicographic LP (OR-Tools GLOP / SciPy HiGHS):
    - Stage 1: Minimize total unmet demand across all corridors.
    - Stage 2: Minimize total transportation cost subject to preserving optimal service.
  - FEFO (First-Expired, First-Out) batch allocation.
  - Generates immutable Decision Receipts explaining selected warehouse, rejection of alternative corridors, distance, and freight breakdown.
- **Logistics Execution (`logistics_service.py`):**
  - Strict state machine: `proposed` -> `approved` -> `ready_for_dispatch` -> `in_transit` -> `delivered`.
  - Immutable `ShipmentEvent` audit trail.

---

## 3. Canonical Field Mapping Matrix

| Canonical Field | Type | Model.Column | Public Benchmark Population | Verified Geo Population | Authorized Company Data Required |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Product SKU** | String(64) | `Product.sku_id` | UCI `StockCode` / M5 `item_id` | N/A | Company ERP SKU Master |
| **Product Name** | String(255) | `Product.name` | UCI `Description` | N/A | Company Catalog Description |
| **Category** | String(128) | `Product.category` | Derived / M5 `dept_id` | N/A | Company Category Hierarchy |
| **Unit** | String(32) | `Product.unit` | Defaulted to 'cases' | N/A | ERP Standard UOM |
| **Case Pack Quantity** | Integer | `Product.case_pack` | Benchmark default (1 or 12) | N/A | **Company Packaging Spec** |
| **Shelf Life (Days)** | Integer | `Product.shelf_life_days` | Benchmark produce shelf life | N/A | **Quality / Formulation Spec** |
| **Location ID** | String(64) | `Location.location_id` | Synthetic code (e.g. `LOC-PUN-01`) | OSM Node Reference | Company Facility Master |
| **Location Name** | String(255) | `Location.name` | City / Market Name | OSM Facility Name | Company Registered Facility Name |
| **Location Type** | String(64) | `Location.location_type` | Inferred from supply tier | OSM Tag (industrial/retail) | **Company Network Hierarchy** |
| **Latitude / Longitude** | Float | `Location.latitude/longitude`| N/A | **OpenStreetMap verified coordinates** | Company GPS Geo-fence |
| **Region / State** | String(128) | `Location.region` | M5 `state_id` / UCI `Country` | OSM Administrative Boundary | Company Sales Territory |
| **Facility Daily Dispatch Cap**| Float | `Location.dispatch_capacity_daily` | Benchmark capacity (5,000 cases) | N/A | **Company Warehouse SLA / Dock Doors** |
| **Inventory On-Hand** | Float | `InventorySnapshot.on_hand`| Inferred initial balance | N/A | **Authorized ERP WMS Balance** |
| **Inventory Reserved** | Float | `InventorySnapshot.reserved`| 0.0 (Unreserved baseline) | N/A | **Active WMS Sales Allocations** |
| **Inventory Blocked** | Float | `InventorySnapshot.blocked` | 0.0 (Unblocked baseline) | N/A | **Quality Hold / Quarantine Records** |
| **Batch Number** | String(64) | `InventorySnapshot.batch_number` | Marked "UNTRACKED_BENCHMARK" | N/A | **Manufacturing Batch Record** |
| **Batch Expiry Date** | Date | `InventorySnapshot.expiry_date` | Inferred from shelf life if available | N/A | **Manufacturing QA Expiry Certificate** |
| **Sales Date** | Date | `SalesHistory.sales_date` | **UCI `InvoiceDate` / M5 date** | N/A | Company POS / Order Book |
| **Sales Quantity** | Float | `SalesHistory.quantity` | **UCI `Quantity` / M5 units** | N/A | Company Dispatched Units |
| **Route Source / Dest** | String(64) | `Route.from/to_location_id` | Hub-to-spoke network | OSM Coordinate Pair | Company Logistics Contract Lane |
| **Road Distance (km)** | Float | Computed in Engine | Haversine estimate | **OSRM Real Driving Road Distance** | Toll / Fleet GPS Log |
| **Transit Lead Time** | Float | `Route.lead_time_days` | Estimated from distance/speed | OSRM Driving Duration + Buffer | **Transporter Contractual SLA** |
| **Freight Cost Rate** | Float | `Route.cost_rate` | Configurable simulation rate | N/A | **Authorized Transporter Rate Card** |
| **Actual Freight Cost** | Float | `Shipment.actual_transport_cost` | N/A | N/A | **Transporter Invoice / Billed Amount** |
| **Consignment Number** | String(64) | `Shipment.consignment_number` | N/A | N/A | **Logistics Docket / LR Number** |
| **Vehicle / Driver** | String | `Shipment.vehicle/driver` | N/A | N/A | **Driver Phone & Vehicle Registration** |
| **Proof of Delivery (POD)** | String(128) | `Shipment.pod_reference` | N/A | N/A | **Signed Physical POD / E-way Bill** |

---

## 4. Public Dataset Lineage, Licensing & Accessibility

### 4.1 UCI Online Retail II
- **Source Repository:** UCI Machine Learning Repository
- **URL:** `https://archive.ics.uci.edu/dataset/502/online+retail+ii` (Direct ZIP: `https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip`)
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0). Commercial and non-commercial usage permitted with attribution.
- **Coverage:** 2009-12-01 to 2011-12-09 (1,067,371 rows).
- **StockWise Value:** Provides real product descriptions, SKU codes, transactional quantities, cancellation identifiers (invoices beginning with 'C'), and timestamps.
- **Clean Ingestion Rules:**
  - Negative quantities and 'C' invoices are categorized as cancellations/returns and quarantined from positive demand series.
  - Product SKUs and descriptions are extracted to build canonical product masters.
  - Transactions are aggregated by day and destination country/hub to build clean time series.

### 4.2 OpenStreetMap (OSM) & OSRM Routing Engine
- **Source Repository:** OpenStreetMap Foundation & Project OSRM
- **URLs:** `https://www.openstreetmap.org/` and `http://router.project-osrm.org/`
- **License:** Open Data Commons Open Database License (ODbL) / BSD 2-Clause.
- **Coverage:** Indian FMCG distribution corridors (Bhiwandi, Sonipat, Chakan, Sri City, Whitefield, Dankuni, Nagpur, Hyderabad, Ahmedabad, Lucknow).
- **StockWise Value:**
  - Real highway road network distance calculation via OSRM Driving API.
  - Eliminates straight-line haversine distortion.
  - Graceful fallback: If OSRM is offline or rate-limited, compute road-adjusted Haversine with a 1.25 winding factor, explicitly recording the source as `haversine_road_adjusted`.

### 4.3 FreshRetailNet-50K
- **Source Repository:** Innovatiana / Hugging Face (`Dingdong-Inc/FreshRetailNet-50K`)
- **URL:** `https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K`
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Coverage:** Perishable food items across 898 stores in 18 cities with hourly sales and stockout annotations.
- **StockWise Value:** Demonstrates perishable retail dynamics and stockout impacts on demand.

### 4.4 Walmart M5 Forecasting
- **Source Repository:** Kaggle Competitions
- **URL:** `https://www.kaggle.com/competitions/m5-forecasting-accuracy/data`
- **License:** Kaggle Competition Rules (Research & Benchmarking).
- **Access Status & Blocker:** Requires Kaggle account authentication and manual acceptance of competition terms. Automated API download without private `kaggle.json` credentials is intentionally blocked by Kaggle (HTTP 401/404).
- **Handling:** We provide a schema transformation adapter script (`backend/app/services/m5_adapter.py`) that users with authorized Kaggle access can run to ingest local M5 extracts into StockWise.

---

## 5. Architectural Safeguards

1. **Namespace Isolation:**
   - All benchmark records are ingested with `snapshot_id="SNAP-BENCHMARK-PUBLIC"` or `org_id="BENCHMARK-NETWORK"`.
   - Production company data is completely isolated under company-owned organizations (e.g. `ORG-HIND-FMCG`).
2. **Zero Mutation Rule:**
   - Benchmark imports never trigger automated shipments or change live physical inventory balances.
   - Simulation mode operates on isolated memory planning state without mutating `InventorySnapshot`.
3. **Traceability in Receipts:**
   - Every Decision Receipt explicitly logs whether the underlying route cost was an authorized company rate card or a benchmark simulation rate.
