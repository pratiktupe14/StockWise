# StockWise — Phase 6: Expiry Intelligence, Batch Tracking & FEFO Allocation

**Document Version:** 1.0  
**Status:** Completed & Fully Verified (Sprint Subset)  
**Date:** October 2026  
**Scope:** Priority 1 to Priority 5 implementation of Batch Expiry Intelligence and FEFO Allocation  

---

## 1. Executive Summary

Phase 6 implements core batch tracking, deterministic expiry risk calculations, and a First-Expired, First-Out (FEFO) allocation engine for finished-goods inventory. This addresses the FMCG operational mandate to prevent dispatch of expired or QA-held goods and prioritize batches with the shortest remaining shelf life while strictly preserving Phase 5 tenant isolation, inventory ownership, and dispatchable stock rules ($max(0, \text{On-Hand} - \text{Reserved} - \text{Blocked})$).

---

## 2. Features Implemented

### Priority 1: Batch Expiry Schema & Field Support
- Reused and validated existing database columns on `inventory_snapshots`: `batch_number`, `expiry_date`, `owner_org_id`, `as_of_date`.
- Preserved existing inventory accounting conventions: unbatched items retain `batch_number=None`, unknown expiry dates remain `expiry_date=None` (never fabricated).
- Validated date inputs and non-negative quantity assertions.

### Priority 2: Deterministic Expiry Risk Engine (`backend/app/services/expiry_service.py`)
- Computes `days_remaining = (expiry_date - as_of_date).days`.
- Categorizes inventory records into explainable risk tiers:
  - `expired`: `days_remaining <= 0` (strictly excluded from dispatch).
  - `critical`: `1 <= days_remaining <= 15` days.
  - `high`: `16 <= days_remaining <= 30` days.
  - `medium`: `31 <= days_remaining <= 60` days.
  - `healthy`: `days_remaining > 60` days.
  - `unknown`: Missing expiry date (never assigned arbitrary predictions).
- Calculates available stock strictly as $max(0, \text{on\_hand} - \text{reserved} - \text{blocked})$.

### Priority 3: Reusable FEFO Allocation Engine (`backend/app/services/expiry_service.py`)
- Deterministic FEFO sorting:
  1. Batches with known expiry sorted ascending by `expiry_date`.
  2. Batches with unknown expiry placed after known valid batches.
  3. Tie-breaking by dispatchable quantity DESC, `batch_number` ASC, and record ID.
- Strict eligibility filtering:
  - Excludes expired batches (`days_remaining <= 0`).
  - Excludes batches below `min_remaining_shelf_life_days` when specified.
  - Excludes zero or negative dispatchable stock.
- Calculates exact per-batch allocations and explicit `unmet_demand` when available stock is insufficient.

### Priority 4: API & UI Integration
- **API Endpoints (`backend/app/api/entities.py`)**:
  - `GET /api/inventory/expiry-risk`: Returns `ExpiryRiskSummaryResponse` with risk aggregates (expired, critical, high risk, healthy, unknown) and item-level metrics. Protected by tenant isolation (`owner_org_id == current_user.org_id`).
  - `POST /api/inventory/fefo-allocate`: Returns `FEFOAllocationResponse` performing deterministic FEFO batch allocation for a given SKU, demand quantity, and optional shelf-life constraint. Scoped strictly to the calling tenant.
- **Frontend Integration (`frontend/src/pages/InventoryPage.tsx` & `api.ts`)**:
  - Enhanced batch cell in the inventory table with dynamic risk badges: `EXPIRED`, `CRITICAL (Nd)`, `NEAR EXP (Nd)`, `{N}d shelf life`, or `Unknown exp`.
  - Added authenticated client helpers `getInventoryExpiryRisk()` and `allocateInventoryFefo()`.

---

## 3. Files Changed

1. `backend/app/services/expiry_service.py`: New deterministic expiry risk and FEFO allocation engine.
2. `backend/app/schemas/entities.py`: Added `BatchExpiryRiskItem`, `ExpiryRiskSummaryResponse`, `FEFOAllocationRequest`, `BatchAllocationItem`, `FEFOAllocationResponse`.
3. `backend/app/api/entities.py`: Added `GET /api/inventory/expiry-risk` and `POST /api/inventory/fefo-allocate` endpoints with tenant isolation.
4. `frontend/src/services/api.ts`: Added `getInventoryExpiryRisk` and `allocateInventoryFefo` with authenticated headers.
5. `frontend/src/pages/InventoryPage.tsx`: Enhanced batch and expiry rendering with live shelf-life calculation and visual risk badges.
6. `backend/tests/test_phase6_expiry.py`: Small, dedicated 9-test suite validating all Phase 6 acceptance criteria.
7. `docs/phase-6-expiry-intelligence.md`: Completion report.
8. `docs/implementation-status.md`: Updated roadmap status.

---

## 4. Migration Requirements

- **Database Schema**: No destructive or new DDL migration was required. The `inventory_snapshots` table already contains `batch_number`, `expiry_date`, and `owner_org_id` from migration `002_network_design`.
- All queries utilize existing indexes on `inventory_snapshots` (`ix_inventory_snapshots_owner_org_id`, `uq_snapshot_sku_location`).

---

## 5. Tests Actually Executed & Exact Results

### 1. Phase 6 Dedicated Test Suite (`backend/tests/test_phase6_expiry.py`)
- **Command:** `pytest tests/test_phase6_expiry.py`
- **Result:** **9 passed in 0.33s** (100% pass rate)
  - `test_earliest_eligible_expiry_prioritized`: PASS
  - `test_expired_batches_strictly_excluded`: PASS
  - `test_blocked_and_reserved_quantities_respected`: PASS
  - `test_insufficient_stock_produces_unmet_demand`: PASS
  - `test_missing_expiry_remains_unknown`: PASS
  - `test_min_remaining_shelf_life_respected`: PASS
  - `test_api_expiry_risk_tenant_isolated`: PASS
  - `test_api_fefo_allocation_tenant_isolated`: PASS
  - `test_existing_inventory_api_remains_compatible`: PASS

### 2. Full Backend Regression Suite (`backend/tests/`)
- **Command:** `pytest tests/`
- **Result:** **91 passed in 17.71s** across 9 test modules with 0 failures:
  - `tests/test_distribution_intelligence.py`: 12 passed
  - `tests/test_distribution_network.py`: 12 passed
  - `tests/test_health.py`: 6 passed
  - `tests/test_imports.py`: 13 passed
  - `tests/test_logistics_execution.py`: 9 passed
  - `tests/test_missing_features_and_utsav.py`: 9 passed
  - `tests/test_phase5_security.py`: 18 passed
  - `tests/test_phase6_expiry.py`: 9 passed
  - `tests/test_production_readiness.py`: 3 passed

### 3. Frontend Production Build (`frontend/`)
- **Command:** `tsc -b && vite build`
- **Result:** **Exit code 0** (2012 modules transformed, built in 462ms, 0 typescript/vite errors).

---

## 6. Features Deferred Due to Time Limit

In accordance with strict sprint rules, the following non-critical items are documented as pending:
1. **Direct OR-Tools Solver Objective Integration**: The FEFO allocator operates as a verified pre-allocation/post-allocation helper service and dedicated endpoint (`/api/inventory/fefo-allocate`). Deep integration into the core OR-Tools CP-SAT solver formulation (which prioritizes primary service level and transport cost minimization) was deferred to avoid destabilizing optimal solver performance.
2. **Dedicated Batch Tracking Tab**: A dedicated multi-tab view on `/inventory` for warehouse QA managers to place specific batch IDs on quality holds (`blocked += qty`).
