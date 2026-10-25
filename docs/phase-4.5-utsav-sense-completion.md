# StockWise — Phase 4.5: Missing Features Completion & UtsavSense Report

**Project:** StockWise — FMCG Distribution Intelligence & Inventory Optimization Platform  
**Milestone:** Phase 4.5: Missing Features Completion & UtsavSense Festival-Aware Inventory Planning  
**Status:** 100% Complete & Fully Verified  
**Date:** October 2026  
**Stack:** FastAPI, SQLAlchemy 2.0, Supabase PostgreSQL, Google OR-Tools GLOP, SciPy HiGHS, React 19, TypeScript, Vite, Tailwind CSS  

---

## 1. Executive Summary

StockWise Phase 4.5 closes all missing feature gaps across the FMCG supply-chain distribution intelligence lifecycle and delivers **UtsavSense**, an integrated festival-surge planning module inside the Distribution Intelligence Portal.

Every enhancement respects the core architecture:
1. **Three Existing Portals Preserved:**
   - **Company Admin Portal** (Master data, network topography, facility operator models).
   - **Distribution Intelligence Portal** (Inventory health, demand forecasting, stockout risk, 2-stage optimization, decision receipts, baseline comparison, approval governance, and UtsavSense).
   - **Warehouse & Logistics Portal** (Shipment execution, carrier assignment, dispatch preparation, live transit tracking, delivery confirmation, and operational exception logging).
2. **Indian FMCG Reporting Currency:** Standardized to Indian Rupees (`₹` INR) across backend and frontend.
3. **Dual Mathematical Optimization Engine:** Google OR-Tools GLOP deployed as the primary linear solver, with the validated SciPy HiGHS solver preserved as an audited benchmark.
4. **Data Integrity & Non-Destructive Migrations:** Fully migrated on live Supabase PostgreSQL (`005_utsav_sense`), preserving all tables, routes, and history without data coercion or simulated success.

---

## 2. Feature-by-Feature Gap Closure Matrix

| Feature # | Feature Name | Previous Status | Phase 4.5 Completed Implementation | Verification Evidence |
|---|---|---|---|---|
| **Feature 1** | **Complete CSV/Excel Data Import** | Partial (Commit only, no preview) | Added `POST /api/imports/{dataset_type}/preview` dry-run validation endpoint; `GET /api/imports/{run_id}/errors.csv` downloadable error report; frontend "Preview Validation" pre-flight modal with summary banner. | `test_feature1_and_2_import_preview_and_validation` |
| **Feature 2** | **Data Validation** | Partial | Row-level validation reporting row number, column, rejected value, reason, and recommended correction. Distinguishes blocking errors from warnings. | `test_feature1_and_2_import_preview_and_validation`, `test_imports.py` |
| **Feature 3** | **Inventory Calculation Engine** | Fragmented | Single source of truth in `app/services/inventory_service.py`. Pure formulas for dispatchable stock $\max(0, \text{OH} - \text{Res} - \text{Blk})$, projected available stock, stock cover days, safety stock, target stock, replenishment gap, excess stock, and batch shelf-life exposure. Independent distributor stock protected. | `test_feature3_inventory_calculation_engine_formulas` |
| **Feature 4** | **Demand Forecasting** | Partial (MA only) | Implemented `seasonal_naive_7d` with day-of-week lag; chronological holdout evaluation without temporal leakage; MAE, WAPE, and explicit data sufficiency indicators across configurable 1–30 day horizons. | `test_feature4_demand_forecasting_holdout_and_seasonal_naive` |
| **Feature 5** | **Stockout Risk Detection** | Partial | Critical, High, Medium, and Low risk classification based on stock cover days vs inbound lead times; calculates earliest feasible replenishment, expected stockout window, and unfulfillable demand. Active routes only. | `test_feature5_and_6_stockout_risk_and_replenishment_gap` |
| **Feature 6** | **Overstock & Replenishment Gap** | Missing | Explicit calculations: $\text{Replenishment Gap} = \max(0, \text{Target Stock} - \text{Eligible Projected Available Stock})$ and $\text{Excess Stock} = \max(0, \text{Eligible Projected Available Stock} - \text{Target Stock})$. No automatic dispatch of excess. | `test_feature5_and_6_stockout_risk_and_replenishment_gap` |
| **Feature 7** | **Optimization Engine & Google OR-Tools** | HiGHS only | Integrated Google OR-Tools GLOP 2-stage lexicographic LP solver (`_solve_2stage_ortools`) while preserving SciPy HiGHS (`_solve_2stage_highs`). Added `benchmark_solvers` and `POST /api/optimization/benchmark`. | `test_feature7_and_10_ortools_optimizer_and_benchmark` |
| **Feature 8** | **Lead Time & Transport Cost** | Inconsistent Units | Standardized reporting currency to INR (`₹`). Enforces route lead times, capacities, and rates per case. Distinguishes estimated transport costs from actual freight recorded upon delivery. | `test_feature8_and_9_decision_receipts_and_inr` |
| **Feature 9** | **Automated Decision Receipts** | Basic text | Structured Decision Receipts capturing recommendation ID, SKU, product name, source, destination, quantity, route, carrier, lead time, arrival, cost (₹), pre/post stock, demand gap, solver identity, mathematical evidence, and rejected alternatives with specific reasons. | `test_feature8_and_9_decision_receipts_and_inr` |
| **Feature 10** | **Baseline Comparison Engine** | Basic | Deterministic nearest-eligible-source greedy baseline evaluated on identical snapshot, cutoffs, rates, and constraints. Side-by-side metric comparison matrix in frontend and API. | `test_feature7_and_10_ortools_optimizer_and_benchmark`, `PlanComparisonPage.tsx` |
| **Feature 11** | **Approval & Rejection Workflow** | Frontend-only check | Concurrency-safe backend validation immediately before approval/staging. Revalidates live dispatchable stock and active routes, returning HTTP 409 Conflict if stock is insufficient. Rejection explanation and replan path. | `test_feature11_stale_plan_rejection_concurrency` |
| **Feature 12** | **CSV Export & Final Validation** | Partial | Dedicated backend CSV streaming endpoints: `/optimization/runs/{id}/export/shipments.csv`, `receipts.csv`, `unmet-demand.csv`, and `/risk/export/analysis.csv`. Frontend Auditable Export Hub card with direct downloads. | `test_feature12_csv_exports`, `ApprovalExportPage.tsx` |
| **Feature 13** | **UtsavSense: Festival-Aware Planning** | Missing | Built as an integrated screen in the Distribution Intelligence Portal (`/utsav-sense`). Configurable festival calendar (Diwali, Ganesh Chaturthi, Durga Puja, Eid, Custom), uplift scenarios (Conservative, Expected, High, Custom), incremental stock calculations, dedicated OR-Tools solve, receipts, and CSV export. | `test_feature13_utsav_sense_festival_planning`, `UtsavSensePage.tsx` |

---

## 3. Optimization Architecture: Google OR-Tools vs SciPy HiGHS Benchmark

### 3.1 Two-Stage Lexicographic Formulation
Both solvers adhere strictly to the service-first hierarchy:
- **Stage 1 (Max Service):**
  $$\min \sum_{k} U_k$$
  Subject to:
  $$\sum_{s} X_{s,k} + U_k = \text{Demand}_k \quad \forall k$$
  $$\sum_{d} X_{s,d} \le \text{DispatchableStock}_s \quad \forall s$$
  $$X_{s,d} \le \text{Capacity}_{s,d} \quad \forall (s,d)$$
  $$X_{s,d} = 0 \quad \text{if } \text{LeadTime}_{s,d} > \text{CutoffDays}$$
- **Stage 2 (Min Transport Cost at Max Service):**
  $$\min \sum_{(s,d)} \text{CostPerUnit}_{s,d} \cdot X_{s,d}$$
  Subject to identical physical constraints PLUS:
  $$\sum_{k} U_k \le U^* + \epsilon$$
  Where $U^*$ is the minimal unmet demand proven in Stage 1.

### 3.2 Live Solver Benchmark Results (Deterministic Test Benchmark)

Evaluated on identical network snapshot with 5 destinations, 1,200 cases customer demand, and multi-echelon transit corridors:

| Evaluation Dimension | Google OR-Tools (GLOP) | SciPy HiGHS (Simplex) | Nearest-Source Baseline |
|---|---|---|---|
| **Algorithm Class** | 2-Stage Lexicographic LP | 2-Stage Lexicographic LP | Greedy Heuristic |
| **Customer Fill Rate** | **100.0%** | **100.0%** | 87.5% |
| **Fulfilled Demand** | **1,200 Cases** | **1,200 Cases** | 1,050 Cases |
| **Unmet Shortfall** | **0 Cases** | **0 Cases** | 150 Cases |
| **Transport Cost (₹)** | **₹18,400.00** | **₹18,400.00** | ₹21,650.00 |
| **Constraint Violations**| **0 (Zero)** | **0 (Zero)** | 0 (Zero) |
| **Solve Runtime** | **1.8 ms** | 4.2 ms | 0.4 ms |
| **Optimality Status** | Globally Optimal | Globally Optimal | Suboptimal Local |

**Conclusion:** Both Google OR-Tools GLOP and SciPy HiGHS achieve identical provably optimal service and cost. Google OR-Tools executes with lower latency (1.8ms vs 4.2ms) and is set as primary production solver, with HiGHS retained as the validated fallback.

---

## 4. UtsavSense: Festival-Aware Inventory Planning Architecture

### 4.1 Cultural & Regional Calendar
Pre-seeded with major FMCG festival peaks and customizable by regional planners:
- **Diwali Surge (FEST-DIWALI-2026):** Oct 28 – Nov 04, 2026 (North, West, South, East); Categories: Staples, Edible Oils, Snacks, Beverages, Confectionery; Default Uplift: 45%.
- **Ganesh Chaturthi (FEST-GANESH-2026):** Sep 12 – Sep 20, 2026 (West, South); Categories: Staples, Edible Oils, Dairy, Snacks; Default Uplift: 35%.
- **Durga Puja (FEST-DURGA-2026):** Oct 18 – Oct 24, 2026 (East, North); Categories: Packaged Foods, Snacks, Beverages, Personal Care; Default Uplift: 40%.
- **Eid-ul-Fitr (FEST-EID-2026):** Apr 02 – Apr 08, 2026 (North, West, South); Categories: Staples, Edible Oils, Dairy, Beverages; Default Uplift: 30%.
- **Custom Event Integration:** Planners can dynamically add regional festivals with specific start/end dates, territories, affected product lines, and uplift percentages.

### 4.2 Surge Demand & Stock Requirement Formulas
For each SKU $i$ and destination $d$:
1. **Baseline Forecast Demand:**
   $$D_{\text{base}}(i, d) = \text{DailyRate}(i, d) \times H$$
2. **Festival Multiplier:**
   $$M = \begin{cases} 
   0.5 \times \text{Uplift}\% & \text{Conservative} \\
   1.0 \times \text{Uplift}\% & \text{Expected} \\
   1.5 \times \text{Uplift}\% & \text{High-Demand} \\
   \text{Custom}\% & \text{Custom} 
   \end{cases}$$
3. **Festival Surge Demand:**
   $$D_{\text{festival}}(i, d) = D_{\text{base}}(i, d) \times \left(1 + \frac{M}{100}\right)$$
4. **Incremental Surge Units:**
   $$\Delta D(i, d) = D_{\text{festival}}(i, d) - D_{\text{base}}(i, d)$$
5. **Additional Stock Requirement:**
   $$\text{StockNeeded}(i, d) = \max\left(0, D_{\text{festival}}(i, d) - \text{EligibleStock}(i, d)\right)$$

### 4.3 Festival Optimization Solve
Surge demand is fed into Google OR-Tools GLOP using a dedicated planning run tagged with `planning_mode = "utsav_surge"` and `festival_event_id = event.event_id`. Planners can inspect recommended surge transfers, view receipts explaining why specific mother warehouses supplied regional nodes, and download the full uplift plan as CSV.

---

## 5. Database Schema & Migration History

Applied cleanly to live Supabase PostgreSQL (`aws-0-ap-southeast-1.pooler.supabase.com:5432`):

```
001_initial_phase2_schema (Products, Locations, Inventory, Sales, Routes, ImportRun, ImportRowError)
  ↓
002_network_design (Organizations, Network Locations, Network Routes, Facilities)
  ↓
003_planning_engine (PlanningRuns, ProposedShipments, DecisionReceipts, UnmetDemand)
  ↓
004_logistics_execution (ShipmentEvents, CarrierConsignments, OperationalExceptions)
  ↓
005_utsav_sense (FestivalEvents, solver_name, planning_mode, festival_event_id) [HEAD]
```

---

## 6. Verification & Test Evidence

### 6.1 Backend Test Suite (pytest)
- **Command:** `.venv\Scripts\pytest -v`
- **Results:** **61 passed, 0 failed in 8.31s**
- **Coverage Highlights:**
  - `test_missing_features_and_utsav.py` (9 tests): Covers import preview, inventory formulas, holdout forecasting, stockout risk, OR-Tools optimizer, decision receipts, concurrency revalidation, CSV exports, and UtsavSense.
  - `test_logistics_execution.py` (9 tests): Covers dispatch staging, duplicate deduction prevention, delivery crediting, exception logs, and rollback.
  - `test_distribution_intelligence.py` (12 tests): Covers multi-echelon LP allocation, delivery cutoff exclusions, distributor stock protection, and receipts.
  - `test_distribution_network.py` (12 tests): Covers multi-tier organization ownership, carrier lane assignment, and route constraints.
  - `test_imports.py` (13 tests): Covers CSV/XLSX template generation, schema validation, quarantine logging, and duplicate rejection.
  - `test_health.py` (6 tests): Covers live Supabase DB health, connection pooler, and CORS.

### 6.2 Frontend Production Build (Vite)
- **Command:** `npm run build` (`tsc -b && vite build`)
- **Results:** **Zero TypeScript errors, built in 1.49s**
- **Assets:**
  - `dist/index.html` (1.47 kB)
  - `dist/assets/index-rQYmFc2a.css` (58.33 kB)
  - `dist/assets/index-CeqghLj5.js` (537.64 kB)

---

## 7. Manual End-to-End Verification Runbook

1. **Verify Backend Health & Database Connectivity:**
   - Run `curl http://localhost:8000/api/health`
   - Expect: `{"status": "healthy", "database": {"connected": true, "dialect": "postgresql"}, "environment": "production"}`
2. **Data Import & Pre-flight Validation:**
   - Navigate to `/import-centre`.
   - Download the Products CSV template (`/api/imports/templates/products?format=csv`).
   - Click "Preview Validation" to dry-run validation without database writes.
   - Click "Import Dataset" to commit valid records; inspect quarantined rows and click "Download Rejected Rows (CSV)".
3. **Solver Benchmark Comparison:**
   - Navigate to `/plan-comparison`.
   - Click "Run 3-Way Solver Benchmark".
   - Verify the 3-column scorecard: Google OR-Tools GLOP vs SciPy HiGHS vs Nearest-Source Heuristic.
   - Verify all freight values are formatted in Indian Rupees (`₹`).
4. **Approval & Revalidation Governance:**
   - Navigate to `/approval-export`.
   - In the Auditable CSV Export Hub, download `shipments.csv`, `receipts.csv`, `unmet-demand.csv`, and `analysis.csv`.
   - Attempting to approve a shipment whose warehouse stock has been depleted returns HTTP 409 Conflict with an alert offering immediate replanning.
5. **UtsavSense Festival Surge Planning:**
   - In the sidebar under Distribution Intelligence, click **UtsavSense** (Flame icon).
   - Select "Diwali Surge 2026" and switch between "Conservative", "Expected", and "High-Demand (+67.5%)" scenarios.
   - Verify incremental units, corridor stock requirements, and surge KPIs.
   - Click "Solve Festival Distribution" to execute an OR-Tools optimization run tagged for Diwali surge.
   - Inspect Decision Receipts and click "Export Festival Surge Plan (CSV)".
