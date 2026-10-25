# StockWise — Implementation Status Report

**Project:** StockWise  
**Tagline:** *The right stock. At the right place. Before it is too late.*  
**Current Milestone:** Phase 12: Expiry-Aware Optimization & Frontend Performance  
**Status:** Complete & Fully Verified (100% Tests Passing, Clean Route-Split Build)  
**Date:** October 2026  

---

## 1. Executive Summary

Phase 2 implemented the first real business workflow of StockWise: importing, validating, quarantining, and persisting FMCG distribution datasets across CSV and Excel (`.xlsx`) formats.

In accordance with `codex_StockWise__PRD.md`, Phase 2 enforces strict data integrity rules without silent data coercion:
- Invalid or unmapped rows are segregated into a row-level quarantine log with line number, field name, rejected value, and specific error reason.
- Valid records are committed to operational database tables.
- Input snapshot identity (`snapshot_id`) is strictly preserved for downstream optimization runs.
- Current dispatchable stock is computed strictly as:
  $$\text{Dispatchable Stock} = \max(0, \text{On-Hand} - \text{Reserved} - \text{Blocked})$$
  Incoming and in-transit units are excluded from current dispatchable stock.
- The UI retains the professional corporate light theme with interactive dataset tabs, downloadable CSV/Excel templates, live validation metric cards, row-level error tables, downloadable CSV error reports, and persisted import history.

---

## 2. Implemented Architecture & Components

### 2.1 Supported Datasets & Validation Rules

| Dataset Category | Key Columns | Validation & Business Rules |
|---|---|---|
| **Products / SKUs** | `sku_id`, `name`, `unit`, `case_pack`, `category`, `shelf_life_days` | Unique SKU identifier; non-empty name; positive integer case pack ($>0$); non-negative shelf life; duplicate key rejection. |
| **Locations** | `location_id`, `name`, `location_type`, `region`, `address` | Unique location identifier; non-empty name; valid location type (`central_warehouse`, `regional_dc`, `distributor_hub`, `retailer`); duplicate key rejection. |
| **Inventory Snapshots** | `snapshot_id`, `sku_id`, `location_id`, `on_hand`, `reserved`, `blocked`, `confirmed_incoming`, `as_of_date` | Compound key `(snapshot_id, sku_id, location_id)` uniqueness; foreign key validation against existing products and locations; non-negative quantities ($\ge 0$); valid ISO date format; dispatchable stock calculation. |
| **Sales History** | `sku_id`, `destination_id`, `sales_date`, `quantity` | Compound key `(sku_id, destination_id, sales_date)` uniqueness; foreign key validation against products and locations; non-negative sales volume ($\ge 0$); valid ISO date format. |
| **Permitted Routes & Rates** | `source_location_id`, `destination_location_id`, `lead_time_days`, `cost_per_unit`, `daily_capacity`, `sku_eligibility` | Compound key `(from, to)` uniqueness; self-referencing route rejection ($from \ne to$); foreign key validation against locations; strictly positive lead time ($>0$); non-negative freight cost rate ($\ge 0$); positive capacity if specified ($>0$). |

### 2.2 Database Persistence & Schema

Using SQLAlchemy 2.0 and Alembic:
- **`backend/app/models/entities.py`**:
  - `Product`: Master catalog table with `sku_id` unique index.
  - `Location`: Master facilities table with `location_id` unique index.
  - `InventorySnapshot`: Operational warehouse positions with compound unique constraint `(snapshot_id, sku_id, location_id)` and hybrid property `dispatchable_stock = max(0, on_hand - reserved - blocked)`.
  - `SalesHistory`: Daily historical consumption observations with compound index `(sku_id, location_id, sales_date)`.
  - `Route`: Permitted transit corridors with compound unique constraint `(source_location_id, destination_location_id)` and check constraints.
  - `ImportRun`: Audit log recording `run_id`, `dataset_type`, `filename`, `file_format`, `file_size_bytes`, `total_rows`, `valid_rows`, `rejected_rows`, `status`, and `snapshot_id`.
  - `ImportRowError`: Quarantine table storing row-level validation rejections with `run_id`, `row_index`, `field_name`, `rejected_value`, `error_reason`, and `error_code`.
- **`backend/alembic/versions/001_initial_phase2_schema.py`**: Complete migration script for all 7 tables with PostgreSQL foreign keys and indexes.
- **Database Engine & Supabase Migration**:
  - Successfully migrated and verified against Supabase PostgreSQL (Project `irhunosgwyvgdhcnzbki`).
  - Utilizes Supabase Session Pooler on port `5432` (`aws-0-ap-southeast-1.pooler.supabase.com`) with `sslmode=require`, ensuring high performance and native IPv4 compatibility where direct database endpoints (IPv6-only) cannot be routed.
  - Migration revision `001_initial_phase2_schema` applied live via Alembic, establishing all 7 tables with transactional DDL.
  - Verified live connectivity via `/api/health` (`status: healthy`, `dialect: postgresql`, `connected: true`).


### 2.3 File Parsing & Validation Engine

- **`backend/app/services/file_parser.py`**:
  - Handles CSV with automatic encoding fallback (`utf-8-sig`, `utf-8`, `latin-1`) and CSV delimiter sniffing (comma, semicolon, tab).
  - Handles Excel (`.xlsx`) via `openpyxl`, reading active sheet headers and converting rows into sanitized dictionaries.
  - Enforces 10MB file size limit and prevents processing of empty or headerless files.
- **`backend/app/services/validators.py`**:
  - Type-safe parsers for float, integer, and ISO date with bounds and sign checks.
  - Foreign key verification against master DB tables before committing snapshots, sales, or routes.
  - In-batch and database duplicate key detection.
  - Self-referencing route detection.
- **`backend/app/services/templates.py`**:
  - Generates downloadable CSV and Excel (`.xlsx`) templates pre-populated with PRD-compliant sample data for all 5 dataset categories.

### 2.4 FastAPI Endpoints

- `POST /api/imports/{dataset_type}`: Upload CSV or Excel file; returns `ImportRunSummaryResponse` with row counts and error diagnostics.
- `GET /api/imports/templates/{dataset_type}?format=csv|xlsx`: Downloads formatted template file.
- `GET /api/imports`: Retrieves audit history of past import executions with optional `dataset_type` filter.
- `GET /api/imports/{run_id}`: Retrieves execution details and summary counts for a specific run.
- `GET /api/imports/{run_id}/errors`: Retrieves all quarantined row-level validation errors for a run.
- `GET /api/inventory`: Lists persisted inventory positions with computed `dispatchable_stock`, filtering by `snapshot_id`, `location_id`, and `sku_id`.
- `GET /api/products`: Lists registered master products.
- `GET /api/locations`: Lists registered network locations.
- `GET /api/sales`: Lists historical sales observations.
- `GET /api/routes`: Lists approved transit routes and freight rates.

### 2.5 Frontend Integration

- **`frontend/src/pages/ImportCentrePage.tsx`**:
  - Interactive dataset selector tabs for all 5 dataset categories.
  - Direct CSV and Excel template download links (`/api/imports/templates/{dataset_type}?format=csv|xlsx`).
  - Drag-and-drop / file selector with client-side extension validation (`.csv`, `.xlsx`).
  - Real-time upload processing feedback with disabled action states and loading indicators.
  - Validation metrics summary cards: Total Rows, Valid & Persisted Rows, Rejected Rows, and Status Badge (`Completed`, `Partial`, `Failed`).
  - Row-Level Validation Diagnostics table showing quarantined lines: Line #, Field Name, Rejected Value, Error Reason, and Error Code badge.
  - Downloadable CSV Error Report button generating immediate client-side downloads of quarantine logs.
  - Historical Import Runs audit table with "Inspect" buttons to reload past run diagnostics.
- **`frontend/src/pages/InventoryPage.tsx`**:
  - Live query against `GET /api/inventory`.
  - KPI summary metrics: Total On-Hand, Committed/Reserved, Quality Blocked, and Dispatchable Stock.
  - Search bar filtering by SKU, product description, or location.
  - Location and stock status filter dropdowns.
  - Interactive table displaying SKU, product, location, on-hand, reserved, blocked, and prominently styled Dispatchable Stock computed via $max(0, OH - Res - Blk)$.
  - Honest empty state with call-to-action redirecting to Import Centre when no inventory records exist.

---

## 3. Test & Verification Results

### 3.1 Backend Test Suite (Pytest)

- **Total Tests:** 19
- **Passing:** 19 (100%)
- **Failing:** 0
- **Duration:** 0.53s

```text
tests/test_health.py::test_root_endpoint PASSED                          [  5%]
tests/test_health.py::test_health_endpoint_contract PASSED               [ 10%]
tests/test_health.py::test_health_alias_endpoint PASSED                  [ 15%]
tests/test_health.py::test_database_connected_state PASSED               [ 21%]
tests/test_health.py::test_database_disconnected_state PASSED            [ 26%]
tests/test_health.py::test_cors_preflight PASSED                         [ 31%]
tests/test_imports.py::test_download_csv_template PASSED                 [ 36%]
tests/test_imports.py::test_download_excel_template PASSED               [ 42%]
tests/test_imports.py::test_valid_products_csv_import PASSED             [ 47%]
tests/test_imports.py::test_valid_products_excel_import PASSED           [ 52%]
tests/test_imports.py::test_products_missing_required_fields PASSED      [ 57%]
tests/test_imports.py::test_products_duplicate_key_rejection PASSED      [ 63%]
tests/test_imports.py::test_locations_import PASSED                      [ 68%]
tests/test_imports.py::test_inventory_foreign_key_validation PASSED      [ 73%]
tests/test_imports.py::test_inventory_dispatchable_calculation PASSED    [ 78%]
tests/test_imports.py::test_inventory_negative_quantity_rejection PASSED [ 84%]
tests/test_routes_self_referencing_and_values PASSED                     [ 89%]
tests/test_imports.py::test_unsupported_file_extension PASSED            [ 94%]
tests/test_imports.py::test_import_history_and_errors_api PASSED         [100%]
```

### 3.2 Frontend Build & Linting

- **TypeScript Compilation & Production Bundle:**
  ```text
  > tsc -b && vite build
  ✓ 1963 modules transformed.
  dist/index.html                   1.47 kB │ gzip:   0.80 kB
  dist/assets/index-CZlcAnFv.css   40.42 kB │ gzip:   7.94 kB
  dist/assets/index-Cwm2ITXm.js   350.42 kB │ gzip: 104.20 kB
  ✓ built in 652ms
  ```
- **Linter (`oxlint`):** 0 errors, 0 build blockers.

### 3.3 End-to-End Browser Validation

Verified via automated browser subagent:
1. **Import Centre (`/imports`)**:
   - Navigation and rendering with corporate light theme verified.
   - All 5 dataset tabs interactively switch required column descriptions and template download URLs.
   - Audited import history rendered all 4 runs (`products`, `locations`, `inventory`, `routes`).
   - Inspected mixed inventory run (`inventory_mixed.csv`):
     - Verified status badge: `Partial (Quarantined)` (2 valid / 2 rejected).
     - Verified row-level diagnostics table displaying Line 4 (`blocked`, `-5`, `NEGATIVE_QUANTITY`) and Line 5 (`sku_id`, `SKU-UNKNOWN-999`, `UNKNOWN_SKU`).
2. **Inventory Visibility (`/inventory`)**:
   - Persisted inventory records loaded live from backend:
     - `SKU-DET-001` (Sparkle Detergent Powder 1kg) at `LOC-WH-MUM`: 500 on-hand, 50 reserved, 20 blocked $\to$ **430 dispatchable stock**.
     - `SKU-TEA-003` (Assam Gold Tea 500g) at `LOC-DC-PUN`: 300 on-hand, 100 reserved, 0 blocked $\to$ **200 dispatchable stock**.
   - Verified that rejected rows were strictly quarantined and never persisted into production inventory.

---

## 4. Phase 2: Real-World FMCG Distribution Network Design (Completed & Verified)

### 4.1 Real-World Network Modeling
In real Indian FMCG supply chains, distribution occurs across distinct, non-interchangeable echelons:
- **Organizations (`organizations`)**: FMCG Brand Company, C&F Agencies, 3PL Logistics Providers, Independent Distributors, Retail Enterprises.
- **Facilities & Locations (`locations`)**: Manufacturing Plants, Company Warehouses, Central Warehouses, Regional Warehouses, C&F Depots, 3PL Facilities, Distributor Warehouses, Retail Destinations.
- **Inventory Ownership vs Physical Storage**: C&F facilities store FMCG company-owned inventory without changing its legal owner (`owner_org_id` retained). Independent distributors own their stock separately.
- **Permitted Corridors (`routes`)**: Permitted lanes configured between source and destination, with assigned 3PL carrier agencies, lead times, transport cost rates, and capacity limits.
- **Shipments & Movement Governance (`shipments`, `stock_movements`)**: Proposals verified against permitted routes (forbidden routes rejected) and source dispatchable stock. Approvals commit inventory without fake vehicle auto-dispatch.

### 4.2 Database Migration & Schema
- Migration Revision: `002_network_design` applied to Supabase PostgreSQL (`irhunosgwyvgdhcnzbki`).
- Public tables in Supabase:
  1. `organizations` (Master organization identities and categories)
  2. `locations` (Extended with `owner_org_id`, `operator_org_id`, `city`, `storage_capacity_units`, `dispatch_capacity_daily`, `is_active`)
  3. `products` (Master product catalog and case pack definitions)
  4. `inventory_snapshots` (Extended with `owner_org_id`, `batch_number`, `expiry_date`)
  5. `sales_history` (Historical sales consumption)
  6. `routes` (Extended with `carrier_agency_id`, `pricing_basis`, `min_shipment_qty`, `max_shipment_qty`, `is_active`, `status_notes`)
  7. `shipments` (Shipment proposals, routing, carrier assignment, costs, governance decisions)
  8. `stock_movements` (Immutable audit trail of all allocations and movements)
  9. `import_runs` (Data ingestion audit runs)
  10. `import_row_errors` (Quarantine log for row-level rejections)
  11. `alembic_version` (Head: `002_network_design`)

### 4.3 Three-Portal Integration
- **Interactive Portal Switcher**: TopBar and Sidebar dynamically switch context between:
  - **Portal 1: Company Admin Portal** (Organizations, Facilities, Permitted Routes, Data Ingestion)
  - **Portal 2: Distribution Intelligence Portal** (Corridor Eligibility Audit, Multi-Location Inventory, Risk, Optimization)
  - **Portal 3: Warehouse & Logistics Portal** (Facility Balances, Proposed Dispatches, Governance Approvals, Movement History)
- **New Frontend Pages**:
  - `/network`: `NetworkManagementPage.tsx` with 4 interactive tabs (Organizations, Facilities, Corridors, Eligibility Audit).
  - `/shipments`: `ShipmentsPage.tsx` with 4 interactive tabs (Shipment Orders, Propose Allocation, Governance Review, Movement Audit Log).
  - `/inventory`: Updated with Owner badges, C&F management indicators, and batch/expiry tracking.

### 4.4 Automated Testing & Verification
- **Automated Pytest Suite (`backend/tests/test_distribution_network.py`)**: 12 dedicated tests validating all 12 Phase 2 acceptance criteria.
- **Backend Test Result:** 31 passed / 31 total (100% pass rate).
- **Frontend Build (`tsc -b && vite build`):** Zero errors, 1966 modules transformed.
- **Linter (`oxlint`):** Zero errors.

---

## 5. Phase Roadmap Status

- [x] **Phase 1:** Clean Light-Theme UI, Foundation, Routing & Live Health API (Completed & Verified)
- [x] **Phase 2.1:** Data Import, Validation & PostgreSQL Persistence (Completed & Verified)
- [x] **Phase 2.2:** Real-World FMCG Distribution Network Design (Completed & Verified)
- [x] **Phase 3:** Distribution Intelligence Engine — Demand Forecasting, Stockout Risk, Lexicographic Optimization & Decision Receipts (Completed & Verified)
- [x] **Phase 4:** Logistics Coordination & Shipment Execution Readiness (Completed & Verified)
- [x] **Phase 4.5:** UtsavSense Festival-Aware Planning & Regional Uplift Modeling (Completed & Verified)
- [x] **Phase 5:** Security Hardening, Tenant Isolation & Production Reliability (Completed & Verified)
- [x] **Phase 6:** Expiry Intelligence, Batch Tracking & FEFO Allocation (Completed & Verified)
- [x] **Phase 7:** Authorized Redistribution & Expiry Prevention (Completed & Verified)

---

## 6. Phase 4: Logistics Coordination & Shipment Execution Readiness

### 6.1 Architecture & State Machine
- **Explicit Lifecycle:** `proposed` → `approved` → `ready_for_dispatch` → `in_transit` → `delivered` (with `rejected` and `cancelled` exception paths). Invalid transitions strictly rejected with HTTP 400.
- **Physical Dispatch Guard:** Approval authorizes the plan; entering `in_transit` requires an explicit, recorded dispatch event by warehouse personnel.
- **Inventory Accounting Mechanics:**
  - `ready_for_dispatch`: Staging reserves inventory (`reserved += qty`) without decrementing `on_hand`.
  - `in_transit`: Gate-out deduction cleanly consumes reserved stock (`on_hand -= qty`, `reserved -= qty`) and creates `MOVEMENT_DISPATCH` record.
  - `delivered`: Gate-in receipt increments destination stock (`on_hand += qty`) and logs `MOVEMENT_RECEIPT`.
  - `cancelled`: Any staged/reserved stock is safely released back into unreserved stock.
- **Logistics Coordination:** Carrier assignment (`carrier_agency_id`, `carrier_contact`), agency acceptance/rejection, waybill/consignment numbers, vehicle license registration, driver phone, delivery exceptions/delays, and Proof of Delivery (POD) references.
- **Plan Traceability:** Direct linkage retained from executed shipments to Phase 3 optimization `planning_run_id` and Decision Receipts.
- **Currency & Cost Consistency:** Indian FMCG standard INR (`₹`) with estimated transport cost (from route rates) strictly distinguished from actual transport cost.

---

## 7. Phase 4.5: UtsavSense Festival-Aware Planning Engine

### 7.1 Architecture & Regional Demand Dynamics
- **Regional Festival Calendar**: Built-in festival calendar modeling Diwali, Durga Puja, Onam, Pongal, Ganesh Chaturthi, Eid, and regional festive seasons across Indian distribution corridors.
- **Category Uplift Multipliers**: Category-specific baseline multipliers (Sweets & Confectionery, Beverages, Gifting, Personal Care, Edible Oils) combined with regional focus weights.
- **Scenario Simulation**: Conservative, Base, and Aggressive scenario simulation with interactive user override multipliers.
- **Integrated Optimization**: Festival uplift demand dynamically feeds into the OR-Tools lexicographic optimization engine, generating pre-build festival stock allocations and Decision Receipts.

---

## 8. Phase 5: Security Hardening, Tenant Isolation & Production Reliability

### 8.1 Key Accomplishments
- **Cryptographic JWT Signature Verification**: Enforced fail-closed PyJWT validation verifying signatures, expiration (`exp`), and audience (`aud="authenticated"`) against Supabase secrets. Mock demo tokens unconditionally rejected when `ALLOW_DEMO_AUTH=False` or `ENVIRONMENT=production`.
- **Server-Side Role & Tenant Derivation**: Client-supplied claims in `user_metadata` attempting self-assignment to `admin` or `planner` are strictly demoted to `viewer`. Trusted roles derived exclusively from server-controlled `app_metadata` or verified server mappings.
- **Comprehensive Tenant Isolation**: Applied strict organization filtering (`owner_org_id` / `org_id`) across:
  - Inventory queries (`/api/inventory`)
  - Import runs and error reports (`/api/imports`)
  - Optimization planning runs and Decision Receipts (`/api/optimization/runs`)
  - Shipment proposals, approvals, dispatches, and audit events (`/api/shipments`)
  - UtsavSense festival optimization executions (`/api/utsav/optimize`)
- **Concurrency & Idempotency Safeguards**:
  - `SELECT ... FOR UPDATE` row-level locking via `with_row_lock()` on stock deduction and reservation updates.
  - HTTP 409 Conflict returned when an `Idempotency-Key` is reused with a materially different request payload.
  - Duplicate physical dispatch prevention (`DUPLICATE_DISPATCH_REJECTED`) preventing double-deduction.
  - Atomic reservation rollback when `ready_for_dispatch` shipments are cancelled.
- **Frontend Security Hardening**:
  - Replaced unauthenticated `<a href>` downloads with authenticated `downloadAuthenticatedFile()` Blob downloads.
  - Gated demo persona switcher strictly behind `isDemoAllowed() && user.isDemo` with visible `DEV MODE` banner.
  - Honest `isAuthenticated` state reflecting real active sessions.

### 8.2 Test & Build Verification Summary
- **Backend Test Suite:** **82 passed** / 82 total (`pytest tests/`) including 18 dedicated Phase 5 security tests.
- **Frontend Production Build:** `tsc -b && vite build` built cleanly in 396ms with 0 errors.
- **Frontend Linter (`oxlint`):** 0 errors.
- **Documentation:** Complete architectural report published at `docs/phase-5-security-and-reliability.md`.

---

## 9. Phase 6: Expiry Intelligence, Batch Tracking & FEFO Allocation

### 9.1 Key Accomplishments
- **Batch Tracking & Schema Support**: Fully supported `batch_number`, `expiry_date`, and `owner_org_id` without duplicating stock balances or fabricating missing expiry dates.
- **Deterministic Expiry Risk Service**: Computes days remaining until expiry and risk classifications (`expired`, `critical`, `high`, `medium`, `healthy`, `unknown`). Excludes expired and quality-blocked stock from dispatchable availability.
- **Reusable FEFO Allocation Engine**: Implemented `allocate_fefo_batches()` in `backend/app/services/expiry_service.py` with deterministic tie-breaking, earliest-expiry prioritization, minimum shelf-life enforcement, and explicit unmet demand reporting.
- **Authenticated APIs**: Exposed `GET /api/inventory/expiry-risk` and `POST /api/inventory/fefo-allocate` protected by Phase 5 JWT authentication and strict organization tenant isolation.
- **Frontend Batch Visualization**: Enhanced `frontend/src/pages/InventoryPage.tsx` with dynamic shelf-life calculations and visual risk badges (`EXPIRED`, `CRITICAL`, `NEAR EXP`, `{N}d shelf life`, `Unknown exp`).
- **Test & Build Verification Summary**:
  - **Phase 6 Test Suite:** **9 passed** / 9 total in 0.33s.
  - **Full Backend Suite:** **91 passed** / 91 total in 17.71s across all 9 test modules with 0 failures.
  - **Frontend Production Build:** `tsc -b && vite build` passed cleanly with 0 errors.
  - **Documentation:** Complete report published at `docs/phase-6-expiry-intelligence.md`.

---

## 10. Phase 7: Authorized Redistribution & Expiry Prevention

### 10.1 Key Accomplishments
- **Candidate Discovery & Demand Pairing**: Pairs near-expiry ($\le 60$d) and surplus stock at source facilities with destination facilities facing unmet demand from `SalesHistory`.
- **Destination Shelf Life & Transit Guard**: Calculates expected arrival date and remaining shelf life upon arrival ($\text{days\_remaining} - \text{lead\_time\_days}$). Rejects candidates that would arrive expired or with less than 10 days of shelf life.
- **Deterministic Priority Scoring**: Evaluates candidates based on expiry urgency, service impact, lead time feasibility, and freight efficiency.
- **Shipment Lifecycle Integration**: Converting recommendations submits formal proposals into the existing `Shipment` governance lifecycle (`status="proposed"`, `approval_status="pending"`) with audit trails. Does NOT alter physical stock or auto-dispatch.
- **Phase 5 Tenant Security Preserved**: Strictly enforces organization ownership boundaries (`owner_org_id == current_user.org_id`). Cross-tenant access attempts return HTTP 404.
- **Test & Build Verification Summary**:
  - **Phase 7 Test Suite:** **8 passed** / 8 total in 0.49s.
  - **Full Backend Suite:** **99 passed** / 99 total in 16.77s across all 10 test modules with 0 failures.
  - **Frontend Production Build:** `tsc -b && vite build` passed cleanly in 579ms with 0 errors.
  - **Documentation:** Complete report published at `docs/phase-7-redistribution.md`.

---

## 11. Phase 8: Distributor Portal

### 11.1 Key Accomplishments
- **Authorized Distributor Role & Tenant Scoping**: Added `distributor` role with server-controlled claim verification. Any untrusted role claims in `user_metadata` attempting privilege escalation (`admin`, `planner`, `logistics`) are automatically demoted to `viewer`. Distributor identity is strictly scoped to `current_user.org_id`.
- **Distributor Operational APIs**:
  - `GET /api/distributor/dashboard`: Computes live KPIs (owned SKUs, on-hand units, dispatchable units, pending request count, in-transit count, and near-expiry risk count).
  - `GET /api/distributor/inventory`: Exposes only inventory snapshots where `owner_org_id == current_user.org_id`. Conceals other distributors' stock and company master positions.
  - `GET /api/distributor/requests`: Lists replenishment requests submitted by the distributor with approval status.
  - `POST /api/distributor/requests`: Validates positive quantity ($> 0$), persisting requests as proposed `Shipment` records (`status="proposed"`, `approval_status="pending"`, `planning_run_id="DIST-REQ-<UUID>"`) with audit `StockMovement` and `ShipmentEvent` logs. Does NOT alter physical stock or auto-dispatch.
  - `GET /api/distributor/shipments`: Filtered consignment visibility for shipments owned by or routed to the distributor's facilities.
- **Frontend Distributor Portal Page (`/distributor`)**: Responsive, light-theme interface with 4 functional tabs (Dashboard with metric cards and alerts, My Owned Inventory with live search, Stock Requests submission form and history table, Shipment Tracking with status badges). Added Distributor Portal to the global portal switcher and top bar role selector.
- **Test & Build Verification Summary**:
  - **Phase 8 Test Suite:** **8 passed** / 8 total in 0.67s.
  - **Full Backend Suite:** **107 passed** / 107 total in 10.21s across all 11 test modules with 0 failures.
  - **Frontend Production Build:** `tsc -b && vite build` passed cleanly in 661ms with 0 errors.
  - **Documentation:** Complete report published at `docs/phase-8-distributor-portal.md`.

---

## 12. Phase 9: Retail Shop Portal

### 12.1 Key Accomplishments
- **Dedicated Retailer Persona & Tenant Isolation**: Added `retailer` role (`USER-RETAILER-01`, `ORG-RETAIL-METRO`) with server-side claim verification. Automatically demotes untrusted privilege escalation attempts (`admin`, `planner`, `logistics`) in `user_metadata` to `viewer`.
- **Protected Retailer Endpoints**:
  - `GET /api/retailer/dashboard`: Computes store KPIs (total SKUs, shelf on-hand units, available units, pending requests, approved awaiting fulfilment, in-transit deliveries, low-stock count $< 25$).
  - `GET /api/retailer/inventory`: Filtered strictly to `owner_org_id == current_user.org_id`. Hides distributor and other retailers' inventory.
  - `GET /api/retailer/requests`: Lists store replenishment orders with live approval status.
  - `POST /api/retailer/requests`: Validates strictly positive quantity ($> 0$) and SKU existence. Persists proposed `Shipment` record with `planning_run_id="RET-REQ-<UUID>"`, `status="proposed"`, and `approval_status="pending"` along with audit `StockMovement` and `ShipmentEvent` logs. Does NOT alter physical stock or auto-dispatch.
  - `GET /api/retailer/shipments`: Filtered consignment visibility for shipments destined to the retailer's store or owned by the retailer organization.
- **Frontend Retail Shop Portal Page (`/retailer`)**:
  - Added `retailer_portal` mode to `PortalContext`, mapped `ShoppingBag` icon, and added `Authorized Retailer` persona to `TopBar`.
  - Responsive 4-tab interface: Store Dashboard (KPI cards & low-stock warning banner), My Store Inventory (searchable table with on-hand and available shelf units), Replenishment Requests (validated restock form & request history table), and Store Deliveries (consignment tracking with status badges).
- **Test & Build Verification Summary**:
  - **Phase 9 Test Suite:** **8 passed** / 8 total in 0.62s.
  - **Full Backend Suite:** **115 passed** / 115 total in 11.85s across all 12 test modules with 0 failures.
  - **Frontend Production Build:** `tsc -b && vite build` passed cleanly in 604ms with 0 errors.
  - **Documentation:** Complete report published at `docs/phase-9-retailer-portal.md`.

---

## 13. Phase 10: End-to-End Integration, Security Validation, and Release Readiness

### 13.1 Key Accomplishments
- **End-to-End Business Lifecycle Tested**: Fully verified the complete 12-step FMCG flow:
  1. *Inventory Import & Snapshot Ingestion*: Ingested multi-tier inventory positions across Plant, Distributor Hub, and Retail Store.
  2. *Inventory Accounting Validation*: Enforced live accounting: $\text{Dispatchable Stock} = \max(0, \text{OH} - \text{Res} - \text{Blk})$. Expired stock is excluded from allocation.
  3. *Chronological Demand Forecasting*: Computed holdout-evaluated rolling forecasts without future data leakage.
  4. *Shortage & Risk Detection*: Identified critical stockout exposure and positive replenishment needs at downstream facilities.
  5. *Service-First Constrained Optimization*: Executed 2-stage lexicographic solver (OR-Tools GLOP) preserving optimal service before minimizing transport freight.
  6. *Evidence-Based Decision Receipts*: Generated auditable decision receipts with rejected alternative routes, solver execution rationale, and baseline comparisons.
  7. *Replenishment Request Submission*: Submitted retailer and distributor store requests, persisted in `proposed` state with `approval_status="pending"` without premature physical deduction.
  8. *Human Approval*: Verified authorized approval (`/api/shipments/{id}/approve`) does not automatically imply physical dispatch.
  9. *Dispatch Staging & Reservation*: Executed `/api/shipments/{id}/prepare` with warehouse checklist, incrementing reserved quantity without altering physical on-hand stock.
  10. *Physical Dispatch Confirmation*: Executed `/api/shipments/{id}/dispatch`, deducting physical source inventory (`on_hand` decreased, `reserved` released) and recording consignment metadata.
  11. *Idempotency & Replay Protection*: Tested duplicate dispatch attempts, confirming strict rejection with `400 Bad Request` (`DUPLICATE_DISPATCH_REJECTED`).
  12. *Delivery Confirmation & Reconciliation*: Executed `/api/shipments/{id}/deliver` with proof-of-delivery (POD) reference, transitioning to terminal status `delivered` and crediting destination retail inventory. Re-delivery safely rejected (`DUPLICATE_DELIVERY_REJECTED`).

- **Verification of All Five Portals**:
  1. *Company Admin*: Network routes, organization oversight, Master Catalog, audit logs.
  2. *Distribution Intelligence*: Demand forecasting, inventory risk evaluation, lexicographic optimization, Decision Receipts, UtsavSense festival surge modeling.
  3. *Warehouse & Logistics*: Shipment staging, carrier assignment, gate passes, physical dispatch execution, delivery confirmations.
  4. *Distributor Portal*: Dashboard KPIs, owned inventory isolation, transfer request submission, shipment visibility.
  5. *Retail Shop Portal*: Store KPIs, low-stock warnings, shelf inventory tracking, replenishment order submission, delivery status tracking.

- **Security & Multi-Tenant Boundaries**:
  - Confirmed unauthenticated requests fail with `401 Unauthorized`.
  - Confirmed client-side role privilege escalation attempts via `user_metadata` are neutralized (demoted to `viewer`).
  - Confirmed strict organization scoping: distributors cannot view or touch manufacturer plants or rival distributor stocks; retailers cannot view distributor stocks or rival retail shops; cross-tenant shipment access returns `404 Not Found` to prevent identifier enumeration.

- **Defects Discovered & Addressed**:
  - *Root Service Discovery Gap*: Registered missing API links for `redistribution`, `distributor`, and `retailer` in `root_info()` (`backend/app/main.py`).

### 13.2 Verification Metrics
- **Phase 10 Test Suite**: `backend/tests/test_phase10_integration.py` -> **4 passed** in 0.76s.
- **Full Backend Pytest Suite**: `backend/tests/` -> **119 passed**, 4 warnings in 10.93s across all 13 test files with **0 failures**.
- **Frontend Production Build**: `tsc -b && vite build` -> transformed 2014 modules, built in **428ms** with **0 errors**.
- **Frontend Linting**: `oxlint` -> 39 files checked in 190ms, **0 errors**, 25 informational warnings.
- **Release Readiness Classification**: **PASS WITH LIMITATIONS** (production-ready workflows verified; limitations documented regarding in-memory test database vs live Supabase PostgreSQL concurrency, and solver FEFO decoupling).

---

## 14. Phase 11: PostgreSQL Concurrency, Security & Production Hardening

### 14.1 Key Accomplishments
- **Live PostgreSQL Row-Level Locking:**
  - Integrated `with_row_lock` (`SELECT ... FOR UPDATE` on PostgreSQL) in `backend/app/services/logistics_service.py` and `backend/app/services/network_service.py` across `Shipment`, `InventorySnapshot`, and `InventoryBatch` entities.
  - Eliminated race conditions during concurrent shipment staging (`prepare_dispatch`), physical dispatch execution (`confirm_dispatch`), and delivery receipt (`confirm_delivery`).
- **Live Multi-Session PostgreSQL Concurrency Suite:**
  - Created and executed `backend/test_postgres_concurrency_live.py` against live Supabase PostgreSQL (`aws-0-ap-southeast-1.pooler.supabase.com:5432`) across 2 concurrent worker threads with independent database sessions.
  - Successfully verified:
    1. *Concurrent stock reservation:* 2 workers competing for 70 units from 100 units; exactly 1 succeeded, 1 rejected with `INSUFFICIENT_STOCK_FOR_PREPARATION`, stock remaining positive (30 units available).
    2. *Concurrent double-dispatch:* Exactly 1 succeeded, 1 rejected with `DUPLICATE_DISPATCH_REJECTED`, single physical deduction and movement.
    3. *Concurrent double-delivery:* Exactly 1 succeeded, 1 rejected with `DUPLICATE_DELIVERY_REJECTED`, destination stock credited once.
    4. *Idempotency conflict & replay:* Replay returns cached 200; mismatched payload rejected with `409 Conflict`.
    5. *Transaction rollback:* Clean rollback without orphaned movements or corrupted status.
- **Security & Authorization Audit:**
  - Hardened JWT verification to strictly require `HS256` and enforce expiration checks.
  - Neutralized privilege escalation: arbitrary client `user_metadata` cannot grant elevated roles or change organization context.
  - Verified multi-tenant boundaries across Manufacturer, Distributor, and Retailer roles with `404 Not Found` for cross-tenant access.
- **FEFO Batch Allocation:**
  - Enforced strict earliest-expiry-first sorting during allocation and excluded expired stock ($\le \text{today}$).
  - Documented linear programming solver decoupling from discrete batch decision variables for optimal performance.

### 14.2 Verification Metrics
- **Live PostgreSQL Concurrency Suite:** **5 passed** / 5 scenarios verified on live Supabase PostgreSQL.
- **Phase 11 Pytest Suite:** `backend/tests/test_phase11_concurrency_and_security.py` -> **5 passed** in 0.36s.
- **Full Backend Pytest Suite:** **124 passed** / 124 total in 11.04s across all 14 test modules with **0 failures**.
- **Frontend Linting:** `npm run lint` -> **0 errors**, 25 warnings in 95ms.
- **Frontend Production Build:** `npm run build` -> transformed 2014 modules, built in **436ms** with **0 errors**.
- **Release Readiness Classification:** **PASS WITH LIMITATIONS** (live PostgreSQL concurrency and multi-tenant security hardened and verified; documented solver aggregate decoupling and frontend JS chunk size).

---

## 15. Phase 12: Expiry-Aware Optimization & Frontend Performance

### 15.1 Key Accomplishments
- **Expiry-Aware Optimization Pre-Filter:**
  - Integrated destination-specific, transit-aware batch eligibility and arc capacity upper bounds $x_{s, src, d} \le \text{arc\_capacities}[(s, src, d)]$ in `backend/app/services/optimizer_service.py`.
  - Guaranteed that expired stock ($\le \text{today}$) and near-expiry stock failing destination shelf life at arrival ($T_{arr} = T_{now} + \text{lead\_time}$) are never recommended for replenishment.
  - Subtracted reserved and blocked quantities without double-counting across multi-batch inventory records.
  - Maintained the continuous 2-stage lexicographic GLOP LP solver with zero mixed-integer combinatorial slowdown.
  - Enforced conservative missing-expiry handling: unverified batches are rejected when minimum shelf-life certification is required.
  - Recorded detailed rejection evidence directly in `DecisionReceiptSchema.rejected_alternatives` and `unmet_demand_breakdown`.
- **Frontend Route-Level Code Splitting:**
  - Implemented dynamic lazy-loading with `React.lazy()` and `Suspense` in `frontend/src/App.tsx` and `frontend/src/components/layout/AppShell.tsx` for all secondary workspaces and portals.
  - Created a responsive, light-theme `RouteLoadingFallback` spinner component.
  - **Main JS bundle reduced from 613.67 kB to 336.43 kB (a 45.2% reduction)**, completely eliminating Vite chunk size warnings.
  - Generated 11 discrete, on-demand portal chunks.

### 15.2 Verification Metrics
- **Phase 12 Pytest Suite:** `backend/tests/test_phase12_expiry_optimization.py` -> **7 passed** in 0.86s.
- **Full Backend Pytest Suite:** `backend/tests/` -> **131 passed**, 4 warnings in **12.52s** across all 15 test files with **0 failures**.
- **Frontend Linting:** `npm run lint` -> **0 errors**, 25 warnings in 146ms.
- **Frontend Production Build:** `npm run build` -> transformed 2015 modules, built in **711ms** with **0 errors**.
- **Release Readiness Classification:** **PASS** (100% tests passing, zero critical vulnerabilities, clean route-split build, and verified operational integrity).

---

## 16. Phase 13: Final Hackathon Demo & Release Readiness

### 16.1 Key Accomplishments
- **Reproducible Synthetic FMCG Demo Scenario & Seed Generator (`backend/seed_fmcg_demo.py`):**
  - Fully parameterized, deterministic FMCG distribution scenario with clean `--reset` and idempotent upserts.
  - Multi-tenant organization landscape across 4 entities: `ORG-FMCG-CORP`, `ORG-LOGISTICS-3PL`, `ORG-DIST-WEST`, and `ORG-RETAIL-METRO`.
  - Master catalog with 5 finished-goods SKUs (Good Day Butter Cookies 120g, NutriChoice Digestive 250g, Marie Gold 300g, Chocolate Swiss Roll 45g, Bourbon Biscuits 150g).
  - 5-tier location network: 1 manufacturing plant (Khopoli), 1 national DC (Bhiwandi), 1 regional C&F depot (Pune), 1 independent distributor hub (Apex Metro West), 1 retail hypermarket (Metro Mart Store #101).
  - 6 active transit corridors with contracted freight rates (1.80 to 6.50 INR/unit) and SLA lead times (1.0 to 4.0 days).
  - Coherent stockout scenario: Metro Mart Store #101 has 35.0 cases on-hand against ~24.7 cases/day demand, triggering critical stockout alert (1.4 days cover < 2.0 days threshold).
  - Optimal upstream source: Bhiwandi DC (4,500 unexpired cases) via 2-day corridor at 3.20 INR/unit.
  - Near-expiry showcase: Chocolate Swiss Roll at Store #101 has 5 days remaining, automatically filtered out from replenishment dispatch.
- **End-to-End 13-Step Demo Rehearsal Suite (`backend/rehearse_demo_scenario.py` & `backend/tests/test_phase13_demo_rehearsal.py`):**
  - Executed and validated all 13 demo workflow steps against live application APIs and database state transitions:
    1. *Network Inspection:* Verified 5 locations and 6 active transit routes.
    2. *Multi-Tier Inventory:* Verified 9 stock positions and dispatchable stock invariant $\max(0, \text{OH} - \text{Res} - \text{Blk})$.
    3. *Demand Forecasting & Stockout Risk:* Verified critical stockout detection for Good Day Cookies at Store #101.
    4. *Constrained Lexicographic Optimization:* 100% service level achieved via 2-stage LP solver in 1.1s.
    5. *Decision Receipt Explanation:* Explains selection of Bhiwandi DC and explicit rejection of Khopoli Plant Direct (higher freight & slow lead time) and Pune C&F.
    6. *Shelf-Life Eligibility:* Near-expiry batch (5 days) barred from replenishment.
    7. *Retailer Replenishment Request:* Submitted from Retail Portal; verified physical inventory and reservations remained unchanged.
    8. *Authorized Approval & Carrier Assignment:* Approved by admin; assigned 3PL carrier; verified approval alone does not mutate physical stock.
    9. *Warehouse Staging:* FEFO reservation accounting verified; reserved increased to 105.0, dispatchable stock dropped to 4,395.0.
    10. *Physical Dispatch:* Source on-hand decremented to 4,395.0 exactly once; tracking logged.
    11. *Delivery Confirmation:* Destination on-hand credited from 35.0 to 140.0 cases (cover days restored to 5.6 days).
    12. *Replay Defense:* Duplicate delivery attempt intercepted with HTTP 400 `DUPLICATE_DELIVERY_REJECTED`.
    13. *Audit Trail:* Verified 6-event lifecycle trail with actor IDs, roles, and timestamps.
- **Judge-Facing Demonstration Materials (`docs/hackathon-demo-runbook.md`):**
  - Authored comprehensive demo runbook with problem/solution statements, synthetic scenario profile, 5-7 minute click-by-click presenter script across all 5 portals, mathematical proofs, safeguard inventory invariants, and recovery procedures.

### 16.2 Verification Metrics
- **Phase 13 Pytest Suite:** `backend/tests/test_phase13_demo_rehearsal.py` -> **6 passed** in 22.54s.
- **Full Backend Pytest Suite:** `backend/tests/` -> **137 passed**, 4 warnings in **38.47s** across all 16 test files with **0 failures**.
- **Frontend Linting:** `npm run lint` -> **0 errors**, 25 warnings in 72ms.
- **Frontend Production Build:** `npm run build` -> transformed 2015 modules, built in **458ms** with **0 errors**.
- **Main JS Bundle Size:** **336.43 kB** (gzip: 101.75 kB).
- **Release Readiness Classification:** **PASS** (reproducible synthetic demo verified across all 5 portals, 100% test pass rate, and full operational integrity).


