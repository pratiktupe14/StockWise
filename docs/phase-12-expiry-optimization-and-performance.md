# StockWise — Phase 12: Expiry-Aware Optimization & Frontend Performance Report

**Project:** StockWise — FMCG Distribution Intelligence & Finished-Goods Inventory Optimization  
**Phase:** 12 — Expiry-Aware Optimization & Frontend Performance  
**Verdict:** **PASS**  
**Date:** October 2026  

---

## 1. Executive Summary

Phase 12 addresses the two primary operational and performance frontiers identified at the end of Phase 11:
1. **Preventing Infeasible Expiry-Sensitive Optimization:** Previously, the primary linear programming solver operated on aggregate SKU volumes, leaving batch-level FEFO and shelf-life enforcement exclusively to the warehouse staging/dispatch boundary. We implemented a continuous LP pre-filtering stage that computes destination-specific, transit-aware batch eligibility and establishes arc-level capacity constraints. This guarantees the optimizer never recommends stock known to be expired or unable to meet destination shelf-life requirements, while preserving the fast, scalable 2-stage lexicographic GLOP LP solver without introducing mixed-integer combinatorial slowdown.
2. **Frontend Route-Level Code Splitting:** Previously, the frontend bundled all workspaces and portals into a single monolithic 613.67 kB JavaScript asset. By implementing `React.lazy()` and `Suspense` across all secondary workspaces and portal routes, the initial application entry bundle dropped to **336.43 kB** (a **45.2% reduction**), completely resolving Vite chunk size warnings and generating 11 dedicated route chunks.

All 131 backend tests pass (100% pass rate across 15 test suites), frontend linting completed with 0 errors, and the production build compiled cleanly in 711ms.

---

## 2. Expiry-Aware Optimization Engine

### 2.1 Pre-Solver Eligibility & Arc Capacity Formulation
Rather than altering the continuous GLOP LP solver into a Mixed-Integer Linear Program (MILP/SCIP)—which would introduce exponential combinatorial complexity on multi-echelon FMCG networks—we introduced a deterministic pre-filtering pipeline in `backend/app/services/optimizer_service.py`:

1. **Inventory Grouping:**
   Raw `InventorySnapshot` records are grouped by `(sku_id, location_id)` to prevent record overwrites or double-counting across multi-batch warehouse positions.
2. **Transit-Aware Arrival Calculation:**
   For each candidate arc between source $src$ and destination $d$, the expected arrival date is computed based on active route lead time:
   $$T_{arrival} = T_{as\_of} + \Delta t_{lead\_time}$$
   If route lead time is missing, a conservative fallback rejects the corridor from automated planning.
3. **Destination Shelf-Life Policy:**
   - Explicit `request.min_remaining_shelf_life_days` is honored if provided.
   - When batch expiry tracking is present in the network, retail destinations (`retailer` / `retail_destination`) default to a standard FMCG threshold of **10 days** remaining shelf life at dock receipt.
   - Unspecified legacy requests without batch data continue to operate with 0-day thresholds for full backwards compatibility.
4. **Batch Filtering Rules:**
   - **Expired Batches:** Any batch with $\text{expiry\_date} \le T_{as\_of}$ is strictly excluded.
   - **In-Transit Expiry:** Any batch where $\text{expiry\_date} \le T_{arrival}$ is excluded.
   - **Insufficient Arrival Shelf Life:** Any batch where $(\text{expiry\_date} - T_{arrival}) < \text{min\_shelf\_life\_required}$ is excluded.
   - **Reserved & Blocked Stock:** Dispatchable batch stock is strictly computed as:
     $$\text{dispatchable} = \max(0, \text{on\_hand} - \text{reserved} - \text{blocked})$$
     Only positive dispatchable stock is eligible.
5. **Linear Solver Arc Capacity Constraint:**
   The sum of eligible dispatchable units across all qualifying batches at $(s, src)$ for destination $d$ forms an arc upper bound:
   $$0 \le x_{s, src, d} \le \text{arc\_capacities}[(s, src, d)]$$
   If $\text{eligible\_qty} \le 0$, the arc is completely excluded from the candidate arc set.
6. **Source Capacity Constraint:**
   Total shipments across all destinations from source $src$ cannot exceed the source's total unexpired dispatchable stock:
   $$\sum_d x_{s, src, d} \le S_{s, src}$$

### 2.2 Handling of Missing Expiry Information
In accordance with food safety standards:
- When a destination or request mandates a minimum remaining shelf life ($\text{min\_shelf\_life} > 0$) or when `require_batch_expiry=True` is specified:
  - Inventory batches lacking an explicit `expiry_date` cannot be certified for arrival shelf-life compliance.
  - They are conservatively marked as ineligible and excluded from automated allocation.
- In legacy snapshot modes where no positive shelf-life duration is mandated (`min_shelf_life == 0` and `require_batch_expiry == False`), unexpired stock is permitted as dispatchable, ensuring backwards compatibility with non-perishable datasets.

### 2.3 Decision Receipts & Rejection Transparency
When a candidate source is rejected or partially restricted due to expiry or shelf-life rules, explicit reasons are recorded in `rejection_reasons_by_dest_sku` and propagated directly to:
1. `rejected_alternatives` on `DecisionReceiptSchema` for every proposed shipment.
2. `reasons` on each item in `unmet_demand_breakdown` when demand cannot be satisfied.

Examples of generated receipt evidence:
- `"Bangalore Central Plant: Excluded 200 units: expired on 2026-10-24."`
- `"Hyderabad Regional DC: Excluded 200 units: insufficient shelf life upon arrival (8d < required 15d for Chennai Hypermarket)."`
- `"Bangalore Central Plant: Excluded 100 units with unknown expiry date: cannot certify 10d minimum shelf life required for Chennai Hypermarket."`

---

## 3. Frontend Route-Level Code Splitting

### 3.1 Implementation
In `frontend/src/App.tsx` and `frontend/src/components/layout/AppShell.tsx`:
- Converted all 11 secondary workspaces and portal pages to dynamic imports using `React.lazy()`:
  - `DistributorPortalPage`
  - `RetailerPortalPage`
  - `ShipmentsPage`
  - `NetworkManagementPage`
  - `UtsavSensePage`
  - `PlanComparisonPage`
  - `ImportCentrePage`
  - `InventoryPage`
  - `OptimizePlanPage`
  - `ApprovalExportPage`
  - `RiskDemandPage`
- Preserved synchronous loading for `OverviewPage` (root landing view) and `AppShell` (persistent navigation chrome).
- Integrated `<Suspense fallback={<RouteLoadingFallback />}>` inside `AppShell` around `<Outlet />`. The fallback provides an elegant spinner with light-theme text matching the application's clean visual language.

### 3.2 Before-and-After Bundle Metrics (Vite Production Build)

| Bundle Metric | Phase 11 (Monolithic) | Phase 12 (Route-Split) | Change |
|---|---|---|---|
| **Main JS Entry Bundle** | `613.67 kB` (`144.23 kB` gzip) | **`336.43 kB`** (`101.75 kB` gzip) | **-277.24 kB (-45.2%)** |
| **Vite Chunk Warnings** | 1 warning (> 500 kB chunk) | **0 warnings** (all chunks < 350 kB) | **Resolved** |
| **CSS Bundle** | `60.83 kB` | `61.05 kB` | +0.22 kB |
| **Route Chunks Generated** | 0 (all in single file) | **11 discrete route chunks** | Isolated portal downloads |
| **Build Time** | `436ms` | `711ms` | Clean compilation |

#### Discrete Route Chunks Produced:
- `DistributorPortalPage-4GLpnUZ_.js` (28.22 kB)
- `RetailerPortalPage-CId4hnlt.js` (28.70 kB)
- `ShipmentsPage-CdVWwDoG.js` (62.33 kB)
- `NetworkManagementPage-CV7-NIJV.js` (35.04 kB)
- `UtsavSensePage-DXXGwUmF.js` (25.60 kB)
- `PlanComparisonPage-B_Q75iDS.js` (25.49 kB)
- `ImportCentrePage-CumRap1D.js` (18.98 kB)
- `InventoryPage-CE-a3G-r.js` (15.90 kB)
- `OptimizePlanPage-DYLqVJza.js` (15.83 kB)
- `ApprovalExportPage-B2A6WTg_.js` (14.62 kB)
- `RiskDemandPage-6qEcT97n.js` (10.19 kB)

---

## 4. Verification & Regression Metrics

### 4.1 Phase 12 Focused Test Suite
Created [backend/tests/test_phase12_expiry_optimization.py](file:///d:/TRIWIZATHON%20hackathon/StockWise/backend/tests/test_phase12_expiry_optimization.py):
- **Command:** `.\.venv\Scripts\python -m pytest tests/test_phase12_expiry_optimization.py -v`
- **Results:** **7 passed** / 7 total in **0.86s** (100% pass rate).
  1. `test_expired_stock_excluded_from_optimization`: Verifies expired stock is rejected with explicit reason.
  2. `test_near_expiry_excluded_for_destination_shelf_life`: Verifies stock failing destination shelf life at arrival is rejected.
  3. `test_eligible_stock_selected_and_fulfilled`: Verifies fresh unexpired stock is fulfilled up to demand.
  4. `test_reserved_and_blocked_quantities_subtracted`: Verifies available stock correctly subtracts reserved and blocked units.
  5. `test_missing_expiry_data_handled_conservatively`: Verifies unknown expiry is excluded under strict policy.
  6. `test_arrival_date_transit_time_distinguishes_sources`: Verifies different route lead times yield different arrival shelf lives and eligibility.
  7. `test_infeasible_recommendations_produce_explicit_reasons_in_receipts`: Verifies Decision Receipts report explicit reasons for all rejected sources.

### 4.2 Full Backend Pytest Suite
- **Command:** `.\.venv\Scripts\python -m pytest tests/`
- **Results:** **131 passed**, 4 warnings in **12.52s** across 15 test files with **0 failures**.

### 4.3 Frontend Linting & Production Build
- **Linting:** `npm run lint` -> 39 files checked in 146ms, **0 errors**, 25 informational warnings.
- **Production Build:** `npm run build` -> transformed 2015 modules, built in **711ms** with **0 errors**.

---

## 5. Summary of Files Changed & Added

1. [`backend/app/schemas/planning.py`](file:///d:/TRIWIZATHON%20hackathon/StockWise/backend/app/schemas/planning.py):
   - Added `min_remaining_shelf_life_days` and `require_batch_expiry` to `OptimizationRequest`.
2. [`backend/app/services/optimizer_service.py`](file:///d:/TRIWIZATHON%20hackathon/StockWise/backend/app/services/optimizer_service.py):
   - Grouped inventory by `(sku_id, location_id)` to avoid double-counting.
   - Added transit-aware arrival date and destination shelf-life filtering.
   - Enforced arc-level capacity constraints in `_solve_2stage_ortools` and `_solve_2stage_highs`.
   - Updated nearest-source baseline comparison to honor arc capacities.
   - Enriched Decision Receipts and unmet demand breakdown with clear expiry rejection reasons.
3. [`backend/tests/test_phase12_expiry_optimization.py`](file:///d:/TRIWIZATHON%20hackathon/StockWise/backend/tests/test_phase12_expiry_optimization.py):
   - Dedicated 7-test regression suite for expiry-aware optimization.
4. [`frontend/src/App.tsx`](file:///d:/TRIWIZATHON%20hackathon/StockWise/frontend/src/App.tsx):
   - Implemented route-level code splitting using `React.lazy()` for all portal and workflow routes.
5. [`frontend/src/components/layout/AppShell.tsx`](file:///d:/TRIWIZATHON%20hackathon/StockWise/frontend/src/components/layout/AppShell.tsx):
   - Wrapped `<Outlet />` in `<Suspense>` with responsive `RouteLoadingFallback`.
6. [`docs/phase-12-expiry-optimization-and-performance.md`](file:///d:/TRIWIZATHON%20hackathon/StockWise/docs/phase-12-expiry-optimization-and-performance.md):
   - Complete technical and verification documentation.
7. [`docs/implementation-status.md`](file:///d:/TRIWIZATHON%20hackathon/StockWise/docs/implementation-status.md):
   - Updated milestone to Phase 12 and recorded release readiness.

---

## 6. Route and Role Compatibility Confirmation

All existing application routes, navigation items, and personas remain fully preserved:
- `/` -> Overview Dashboard
- `/network` -> Network Management (Company Admin)
- `/imports` -> Import Centre (Company Admin)
- `/inventory` -> Inventory Position (Warehouse & Logistics)
- `/distributor` -> Distributor Portal (Authorized Distributor)
- `/retailer` -> Retail Shop Portal (Authorized Retailer)
- `/shipments` -> Consignment Operations (Warehouse & Logistics)
- `/risk-demand` -> Distribution Intelligence
- `/optimize` -> Optimization & Decision Receipts
- `/comparison` -> Solver Baseline Benchmarks
- `/utsav-sense` -> Festival-Aware Planning
- `/approval` -> Approval & Dispatch Center

Role-based access checks and session states remain intact.
