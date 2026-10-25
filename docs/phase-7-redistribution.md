# StockWise — Phase 7: Authorized Redistribution & Expiry Prevention

**Document Version:** 1.0  
**Status:** Completed & Fully Verified  
**Date:** October 2026  
**Scope:** Authorized Inter-Facility Redistribution, Deterministic Candidate Ranking, Expiry Prevention & Shipment Lifecycle Integration  

---

## 1. Executive Summary

Phase 7 implements an intelligent, authorized redistribution recommendation engine designed to prevent FMCG finished-goods inventory waste. In multi-echelon FMCG networks, stock can become stranded at certain warehouses or depots near expiry while regional distribution hubs experience unmet customer demand and stockout risks.

StockWise Phase 7 identifies near-expiry or surplus batches at source facilities and pairs them with eligible destination nodes facing inventory shortfalls, factoring in route lead times, destination arrival shelf life, and freight costs. The engine strictly preserves Phase 5 security controls (JWT signature verification, server-side role derivation, organization isolation) and integrates with the existing Phase 4 shipment governance lifecycle (`proposed` $\to$ `approved` $\to$ `ready_for_dispatch` $\to$ `in_transit` $\to$ `delivered`).

---

## 2. Features Actually Implemented

### 2.1 Redistribution Candidate Generation (`backend/app/services/redistribution_service.py`)
- **Source Stock Eligibility:** Evaluates dispatchable inventory strictly as $max(0, \text{on\_hand} - \text{reserved} - \text{blocked})$. Expired (`days_remaining <= 0`) and quality-blocked batches are strictly rejected.
- **Surplus & Near-Expiry Detection:** Selects batches where remaining shelf life is $\le 60$ days or where local dispatchable stock exceeds safety stock thresholds.
- **Route & Corridor Feasibility:** Discovers permitted active transport corridors from `Route` master records (`from_location_id != to_location_id`, `is_active == True`).
- **Destination Demand & Shortfall Analysis:** Evaluates destination dispatchable stock against 14-day demand based on historical sales velocity from `SalesHistory`. Computes exact `destination_shortfall = max(0, target_demand - dest_dispatchable)`.
- **Destination Shelf-Life & Transit Validation:** Calculates expected arrival date ($\text{today} + \text{lead\_time\_days}$) and remaining shelf life upon arrival ($\text{days\_remaining} - \text{lead\_time\_days}$). Rejects any candidate that would arrive expired ($\le 0$ days) or with less than 10 days of shelf life (standard FMCG retail acceptance buffer).
- **Quantity Capping:** Caps proposed redistribution quantity by $min(\text{source\_dispatchable}, \text{destination\_shortfall})$.
- **Transport Freight Estimation:** Computes estimated transport cost based on route rates: $\text{recommended\_qty} \times \text{cost\_rate}$.

### 2.2 Transparent Deterministic Ranking & Scoring
Candidates are ranked using a multi-factor score ($0 - 100$ points):
- **Expiry Urgency ($5 - 50$ pts):** 50 pts for critical ($\le 15$d), 35 pts for near-expiry ($\le 30$d), 20 pts for medium ($\le 60$d), 5 pts otherwise.
- **Service Impact ($0 - 35$ pts):** Proportion of destination shortfall fulfilled.
- **Lead-Time Bonus ($0 - 15$ pts):** Faster corridors receive higher feasibility scores ($\max(0, 15 - \text{lead\_time})$).
- **Explainable Rationale:** Every recommendation generates human-readable operational reasoning citing source stock, destination shortfall, arrival shelf life, and freight cost.

### 2.3 Ownership & Authorization (Phase 5 Preservation)
- **Same-Owner Principle:** Source inventory must belong to the user's authorized organization (`owner_org_id == current_user.org_id`).
- **No Cross-Owner Transfers:** Distributor-owned stock, C&F operator stock, and brand company stock are never pooled or transferred without explicit multi-party authority.
- **Tenant Isolation:** Users cannot query recommendations or propose transfers for other organizations' facilities. Cross-tenant access attempts return HTTP 404.

### 2.4 Proposal Creation & Shipment Lifecycle Integration
- **Proposal Submission:** Transforming a recommendation into an authorized proposal calls `create_redistribution_shipment_proposal()`.
- **State Machine Integration:** Creates a formal `Shipment` record with:
  - `status = "proposed"`
  - `approval_status = "pending"`
  - `planning_run_id = "REDIST-<UUID>"`
  - Emits an immutable `StockMovement(movement_type="proposed_dispatch")` and `ShipmentEvent`.
- **Zero Premature Movement:** Physical inventory is **not** altered and stock is **not** automatically dispatched. Governance approval (`POST /api/shipments/{id}/approve`) and physical staging/dispatch remain strictly required.

### 2.5 API & UI Integration
- **Backend API Endpoints ([backend/app/api/redistribution.py](file:///d:/TRIWIZATHON%20hackathon/StockWise/backend/app/api/redistribution.py)):**
  - `GET /api/redistribution/recommendations`: Lists candidates with priority scores, ETA, arrival shelf life, and rationale. Protected by RBAC (`admin`, `planner`, `logistics`, `viewer`).
  - `POST /api/redistribution/propose`: Submits a recommendation as a formal shipment proposal. Protected by RBAC (`admin`, `planner`).
- **Frontend UI ([frontend/src/pages/InventoryPage.tsx](file:///d:/TRIWIZATHON%20hackathon/StockWise/frontend/src/pages/InventoryPage.tsx)):**
  - Added "Authorized Redistribution & Expiry Prevention" panel with "Analyze Redistribution" action.
  - Interactive table displaying SKU, Source, Destination, Batch & Shelf Life on Arrival, Recommended Qty, Lead Time & ETA, Freight Cost, Priority Badge, and one-click "Propose" button.

---

## 3. Modified Files

| File | Change |
|---|---|
| [backend/app/schemas/redistribution.py](file:///d:/TRIWIZATHON%20hackathon/StockWise/backend/app/schemas/redistribution.py) | Created Pydantic schemas for recommendations, rejections, and proposal requests. |
| [backend/app/services/redistribution_service.py](file:///d:/TRIWIZATHON%20hackathon/StockWise/backend/app/services/redistribution_service.py) | Created candidate generation, shelf-life validation, priority scoring, and proposal conversion engine. |
| [backend/app/api/redistribution.py](file:///d:/TRIWIZATHON%20hackathon/StockWise/backend/app/api/redistribution.py) | Created authenticated API routes for recommendation queries and proposal submissions. |
| [backend/app/main.py](file:///d:/TRIWIZATHON%20hackathon/StockWise/backend/app/main.py) | Mounted `redistribution_router` under `/api/redistribution`. |
| [frontend/src/services/api.ts](file:///d:/TRIWIZATHON%20hackathon/StockWise/frontend/src/services/api.ts) | Added `getRedistributionRecommendations` and `submitRedistributionProposal` API client functions. |
| [frontend/src/pages/InventoryPage.tsx](file:///d:/TRIWIZATHON%20hackathon/StockWise/frontend/src/pages/InventoryPage.tsx) | Added Redistribution & Expiry Prevention table and proposal workflow. |
| [backend/tests/test_phase7_redistribution.py](file:///d:/TRIWIZATHON%20hackathon/StockWise/backend/tests/test_phase7_redistribution.py) | Small, targeted 8-test suite for Phase 7. |
| [docs/phase-7-redistribution.md](file:///d:/TRIWIZATHON%20hackathon/StockWise/docs/phase-7-redistribution.md) | Phase 7 completion report. |
| [docs/implementation-status.md](file:///d:/TRIWIZATHON%20hackathon/StockWise/docs/implementation-status.md) | Updated roadmap with Phase 7 milestone. |

---

## 4. Tests Actually Executed & Exact Results

### 4.1 Phase 7 Dedicated Test Suite (`backend/tests/test_phase7_redistribution.py`)
- **Command:** `pytest tests/test_phase7_redistribution.py`
- **Result:** **8 passed in 0.49s** (100% pass rate)
  - `test_surplus_near_expiry_generates_recommendation`: PASS
  - `test_expired_or_blocked_stock_rejected`: PASS
  - `test_inadequate_remaining_shelf_life_rejects_candidate`: PASS
  - `test_recommendation_does_not_alter_physical_stock`: PASS
  - `test_create_redistribution_proposal_integrates_with_shipments`: PASS
  - `test_cross_organization_redistribution_strictly_forbidden`: PASS
  - `test_api_redistribution_recommendations_endpoint`: PASS
  - `test_api_submit_redistribution_proposal_endpoint`: PASS

### 4.2 Full Backend Regression Suite (`backend/tests/`)
- **Command:** `pytest tests/`
- **Result:** **99 passed in 16.77s** across all 10 test modules with 0 failures:
  - `tests/test_distribution_intelligence.py`: 12 passed
  - `tests/test_distribution_network.py`: 12 passed
  - `tests/test_health.py`: 6 passed
  - `tests/test_imports.py`: 13 passed
  - `tests/test_logistics_execution.py`: 9 passed
  - `tests/test_missing_features_and_utsav.py`: 9 passed
  - `tests/test_phase5_security.py`: 18 passed
  - `tests/test_phase6_expiry.py`: 9 passed
  - `tests/test_phase7_redistribution.py`: 8 passed
  - `tests/test_production_readiness.py`: 3 passed

### 4.3 Frontend Production Bundle (`frontend/`)
- **Command:** `tsc -b && vite build`
- **Result:** **Exit code 0** (2012 modules transformed, built in 579ms with 0 errors).

---

## 5. Known Limitations & Deferred Work

1. **Cross-Owner Redistribution (Consignment/Buyback):** Transfers are restricted to same-organization ownership (`owner_org_id == current_user.org_id`). Inter-organization stock transfers (e.g., buying back slow-moving inventory from an independent distributor) require commercial settlement contracts and are deferred to external portal phases.
2. **Multi-Stop Route Chaining:** Recommendations evaluate direct permitted corridors between source and destination. Multi-hop transshipment routes are deferred.
