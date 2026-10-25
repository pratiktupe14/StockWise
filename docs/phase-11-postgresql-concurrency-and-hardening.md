# StockWise — Phase 11: PostgreSQL Concurrency, Security & Production Hardening Report

**Project:** StockWise — FMCG Distribution Intelligence & Finished-Goods Inventory Optimization  
**Phase:** 11 — PostgreSQL Concurrency, Security & Production Hardening  
**Target Environment:** Supabase Cloud PostgreSQL (Dialect `postgresql`, Pooler `aws-0-ap-southeast-1.pooler.supabase.com:5432`)  
**Verdict:** **PASS WITH LIMITATIONS**  
**Date:** October 2026  

---

## 1. Executive Summary

Phase 11 hardens StockWise for concurrent, multi-tenant production operations. Unlike previous phases where concurrency assertions relied primarily on in-memory SQLite fixtures or mocked database locks, Phase 11 validates physical concurrency, row-level locking, and transactional isolation against live PostgreSQL on Supabase.

We implemented and verified:
1. **Live PostgreSQL Row-Level Locking:** Integrated `SELECT ... FOR UPDATE` via `with_row_lock` in `logistics_service.py` and `network_service.py`. Concurrent attempts to stage, dispatch, or deliver stock are serialized at the database engine level.
2. **Multi-Session Concurrency Test Runner:** Created and executed a dedicated live PostgreSQL concurrency suite (`backend/test_postgres_concurrency_live.py`) using concurrent Python worker threads with isolated database sessions connected to the live Supabase pooler.
3. **Security & Multi-Tenant Authorization:** Hardened JWT token validation, verified server-side claims extraction (neutralizing arbitrary client `user_metadata` privilege escalation), and audited multi-tenant boundaries across Manufacturer, Distributor, and Retailer roles.
4. **Strict FEFO Expiry Allocation:** Hardened batch selection to strictly exclude expired items ($\le \text{today}$) and allocate stock in earliest-expiry-first order during warehouse preparation and physical dispatch.
5. **Full Regression & Production Build:** Verified all 124 backend tests pass with 0 failures, confirmed clean frontend linting (0 errors), and executed a zero-error Vite production build.

---

## 2. PostgreSQL Live Staging Environment & Connectivity

- **Database Host:** `aws-0-ap-southeast-1.pooler.supabase.com` (Supabase Session Pooler on port `5432` with `sslmode=require`)
- **Engine Dialect:** `postgresql+psycopg2`
- **Alembic Head Revision:** `006_idempotency` (15 operational tables in the `public` schema)
- **Live Verification Tool:** `backend/verify_supabase_connection.py`
- **Connection Latency:** ~1468ms round-trip over SSL pooler

### Live Database Schema Verified
The live Supabase staging database contains 15 active tables:
`alembic_version`, `products`, `locations`, `inventory_snapshots`, `sales_history`, `routes`, `import_runs`, `import_row_errors`, `shipments`, `shipment_audit_events`, `inventory_batches`, `stock_movements`, `organizations`, `replenishment_requests`, and `idempotency_keys`.

---

## 3. Concurrency Validation & Inventory Integrity

### 3.1 Hardening Implementation
In previous iterations, concurrent requests could read identical stock levels before committing updates, risking negative available inventory or duplicate dispatches.

We hardened the operational pipeline in `backend/app/services/logistics_service.py` and `backend/app/services/network_service.py`:
- **Row-Level Locking:** Replaced standard queries with `with_row_lock(db.query(...))` (`with_for_update()` on PostgreSQL engines) for `Shipment`, `InventorySnapshot`, and `InventoryBatch` rows.
- **Strict FEFO Sorting in Logistics:** Warehouse preparation (`prepare_dispatch`) and dispatch execution (`confirm_dispatch`) now query batches sorted by `expiry_date.asc()` with row-level locks, filtering out any batch where `expiry_date <= today`.
- **Atomic Transition Guard:** State checks (`shipment.status == "created"`, `shipment.status == "staged"`, etc.) occur within the acquired row lock, ensuring immediate serialization of competing worker sessions.

### 3.2 Live Multi-Session PostgreSQL Concurrency Test Results
Ran `backend/test_postgres_concurrency_live.py` against live Supabase PostgreSQL with two independent worker threads executing simultaneous operations across separate database connections.

| Scenario | Tested Concurrency Behavior | Expected Outcome | Live PostgreSQL Result | Status |
|---|---|---|---|---|
| **1. Concurrent Stock Reservation** | 2 concurrent workers attempting to prepare/reserve 70 units each against a single warehouse batch of 100 units. | Exactly 1 worker succeeds; 1 worker fails with `INSUFFICIENT_STOCK_FOR_PREPARATION`. Stock remains non-negative. | Worker A reserved 70 units; Worker B failed with `HTTP 400: INSUFFICIENT_STOCK_FOR_PREPARATION`. Remaining available stock is exactly 30 units (`on_hand=100.0`, `reserved=70.0`, `dispatchable=30.0`). Available inventory never turned negative. | **PASS** |
| **2. Concurrent Double-Dispatch** | 2 concurrent workers attempting `confirm_dispatch` on the same staged shipment. | Exactly 1 worker succeeds; 1 worker fails with `DUPLICATE_DISPATCH_REJECTED`. Stock decremented exactly once. | Worker A transitioned shipment to `in_transit`; Worker B received `HTTP 400: DUPLICATE_DISPATCH_REJECTED`. Stock decremented exactly once (`on_hand=30.0`, `reserved=0.0`). Exactly 1 `actual_dispatch` movement logged. | **PASS** |
| **3. Concurrent Double-Delivery** | 2 concurrent workers attempting `confirm_delivery` on the same in-transit shipment. | Exactly 1 worker succeeds; 1 worker fails with `DUPLICATE_DELIVERY_REJECTED`. Destination stock credited once. | Worker A transitioned shipment to `delivered`; Worker B received `HTTP 400: DUPLICATE_DELIVERY_REJECTED`. Destination stock credited once (`on_hand=70.0`). Exactly 1 `delivery_receipt` movement logged. | **PASS** |
| **4. Idempotency Conflict & Replay** | Identical request replayed returns cached 200; altered payload with the same key returns 409 Conflict. | Cached response on replay; 409 on hash mismatch. | Replay returned identical cached 200 response; altered payload returned `HTTP 409 Conflict: IDEMPOTENCY_KEY_PAYLOAD_MISMATCH`. | **PASS** |
| **5. Transaction Rollback Safety** | Invalid state transition triggers rollback. | No partial state or orphaned movements persisted. | Transaction rolled back cleanly; zero orphaned movements or corrupted status records. | **PASS** |

*Note: All synthetic test entities generated during live PostgreSQL validation were cleanly removed in the runner's `finally` cleanup block.*

---

## 4. Security & Tenant Isolation Audit

### 4.1 Authentication & Token Verification
- **JWT Signing & Algorithm:** Hardened token decoder in `backend/app/core/security.py` strictly requires HMAC-SHA256 (`HS256`) and validates token expiration (`exp`). Unsigned tokens, invalid signatures, or tokens signed with mismatched algorithms (`none`, `RS256`) are rejected with `401 Unauthorized`.
- **Missing or Malformed Bearer Token:** Requests lacking an `Authorization: Bearer <token>` header immediately fail at the dependency injection level (`get_current_user`).

### 4.2 Privilege Escalation & Role Integrity
- **Untrusted Client Metadata Neutralization:** User roles and organization memberships are parsed strictly from trusted claims (`app_metadata` or server-side database records). Any attempt by a client to inject `role: "admin"` or `role: "company_admin"` via mutable `user_metadata` is neutralized and defaulted to `viewer` with no organization authority.
- **Immutable Authorization Parameters:** Request bodies and query parameters cannot override the caller's server-verified `organization_id` or `role`.

### 4.3 Tenant Scoping & Isolation
- **Manufacturer (Company Admin):** Full visibility over central plants, regional hubs, and global optimization runs.
- **Distributor (`distributor` role):** Restricted to inventory located at facilities owned by their `organization_id`. Cannot view or dispatch stock belonging to other distributors or central manufacturing plants. Cross-tenant shipment lookups return `404 Not Found` to prevent entity enumeration.
- **Retailer (`retailer` role):** Restricted to store-level inventory and inbound store consignments. Cannot view distributor warehouse holdings or rival retailer orders.

---

## 5. Expiry-Aware Inventory Allocation & FEFO

### 5.1 FEFO Enforcement at Operational Boundary
In `backend/app/services/logistics_service.py` and `backend/app/services/expiry_service.py`:
- Batches with `expiry_date <= today` are marked expired and excluded from allocation.
- Batches are queried and allocated in ascending order of `expiry_date` (Earliest Expiry First Out).
- Reserved and blocked quantities are subtracted before determining allocatable batch volume.
- Shelf-life thresholds for destination locations are respected.

### 5.2 OR-Tools Solver Integration Analysis
**Architectural Decision:** We evaluated whether to introduce batch-level decision variables into the main OR-Tools linear programming solver (`optimizer_service.py`).
- **Conclusion:** We deliberately retain the decoupled design.
  - Adding discrete batch decision variables converts the efficient Linear Program (GLOP) into a Mixed-Integer Linear Program (MILP/SCIP), increasing solving time from sub-second to minutes on large FMCG distribution topologies.
  - Instead, the optimizer solves for aggregate optimal flow across eligible physical corridors, while the operational logistics engine (`prepare_dispatch` and `confirm_dispatch`) strictly enforces batch-level FEFO and shelf-life constraints at the time of reservation and physical dispatch.
  - This architecture preserves mathematical scalability while guaranteeing zero expired inventory reaches downstream channels.

---

## 6. Regression Testing & Release Readiness

### 6.1 Backend Test Suite (Pytest)
Executed command:
```powershell
.\.venv\Scripts\python -m pytest tests/
```
**Results:** **124 passed**, 4 warnings in **11.04s** across 14 test modules (100% pass rate).

| Test Module | Tests | Status |
|---|---|---|
| `test_distribution_intelligence.py` | 12 | Passed |
| `test_distribution_network.py` | 12 | Passed |
| `test_health.py` | 6 | Passed |
| `test_imports.py` | 13 | Passed |
| `test_logistics_execution.py` | 9 | Passed |
| `test_missing_features_and_utsav.py` | 9 | Passed |
| `test_phase10_integration.py` | 4 | Passed |
| `test_phase11_concurrency_and_security.py` | 5 | Passed |
| `test_phase5_security.py` | 18 | Passed |
| `test_phase6_expiry.py` | 9 | Passed |
| `test_phase7_redistribution.py` | 8 | Passed |
| `test_phase8_distributor.py` | 8 | Passed |
| `test_phase9_retailer.py` | 8 | Passed |
| `test_production_readiness.py` | 3 | Passed |
| **Total** | **124** | **100% Passed** |

### 6.2 Frontend Linting
Executed command:
```powershell
npm run lint
```
**Results:** **0 errors**, 25 informational warnings across 39 files in 95ms.

### 6.3 Frontend Production Build
Executed command:
```powershell
npm run build
```
**Results:** `tsc -b && vite build` succeeded in **436ms** with **0 errors**. Produced optimized bundles:
- `dist/index.html` (1.47 kB)
- `dist/assets/index-DiBKhT5o.css` (60.83 kB)
- `dist/assets/index-e7hd_kxZ.js` (613.67 kB)

---

## 7. Hackathon Demonstration Scenario (10-Step Workflow)

A repeatable, 10-step end-to-end demonstration scenario using synthetic FMCG data (`seed_fmcg_demo.py`):

1. **Shortage Identified:** Retail Shop `RET-001` (Indiranagar Store) displays critical stockout risk for *Basmati Rice 5kg* (`SKU-RIC-01`) with projected cover days under 2.0.
2. **Demand Forecast Analysis:** In *Distribution Intelligence*, the 14-day rolling demand forecast predicts a surge of 180 units driven by upcoming festivities.
3. **Constrained Optimization Proposal:** The OR-Tools engine executes, proposing a replenishment consignment of 150 units from Regional DC `RDC-BLR-01` over Route `RTE-BLR-RDC-RET1`.
4. **Decision Receipt Audit:** The generated *Decision Receipt* details why higher-cost air and cross-zone routes were rejected in favor of the optimal low-cost road transit corridor.
5. **Replenishment Request Submission:** The Retailer submits a restock request via the *Retail Shop Portal* (`/retailer`).
6. **Authorized Approval:** The Company Logistics Manager approves the shipment via `/shipments` (`approval_status="approved"`).
7. **FEFO Warehouse Staging:** In *Warehouse & Logistics*, the warehouse manager executes dispatch preparation (`/api/shipments/{id}/prepare`). The database selects Batch `BATCH-RIC-01` (earliest expiry: 90 days out) and reserves 150 units with row-level locks, leaving expired stock untouched.
8. **Physical Dispatch:** The warehouse confirms physical gate exit (`/api/shipments/{id}/dispatch`). Physical on-hand stock decrements by 150 units, reservation is released, and consignment status updates to `in_transit`.
9. **Destination Delivery Confirmation:** The store manager records delivery receipt (`/api/shipments/{id}/deliver`) with POD reference `POD-IND-9912`. Retail on-hand stock increases by 150 units.
10. **Reconciliation & Idempotency Check:** Re-attempting delivery confirmation is rejected (`DUPLICATE_DELIVERY_REJECTED`). The audit trail records all 6 lifecycle events with user ID and timestamps.

---

## 8. Open Risks & Mitigations

1. **Frontend JS Bundle Chunk Size:**
   - *Risk:* Vite emitted a warning that `index.js` is 613 kB (> 500 kB recommended threshold).
   - *Impact:* Minimal for desktop hackathon demo; could slightly impact mobile page load speeds on low-bandwidth cellular networks.
   - *Mitigation:* Implement dynamic `React.lazy()` route-based code splitting in Phase 12.
2. **Linear Optimizer FEFO Decoupling:**
   - *Risk:* The OR-Tools LP optimizes aggregate SKU quantity rather than discrete batch expiry dates.
   - *Impact:* If an entire warehouse only possesses near-expiry stock that fails destination minimum shelf-life rules, the aggregate solver might route from that warehouse, requiring the logistics engine to flag the shortfall during staging.
   - *Mitigation:* Documented and handled cleanly at the staging stage (`prepare_dispatch`) where insufficient eligible non-expired stock returns a clear business error.
