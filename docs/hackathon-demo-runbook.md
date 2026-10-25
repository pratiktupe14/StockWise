# StockWise — Hackathon Demonstration Runbook & Release Guide

## 1. Executive Summary

- **One-Sentence Problem Statement:** FMCG supply chains suffer billions in stockouts and perishable wastage because inventory visibility is siloed across independent distributors and retailers, leading to slow, sub-optimal replenishment decisions based on intuition rather than constrained mathematics.
- **One-Sentence StockWise Solution:** StockWise is an end-to-end FMCG distribution intelligence and inventory optimization platform that continuously monitors multi-tier stock positions, forecasts store demand, optimizes replenishment via 2-stage lexicographic linear programming with explainable Decision Receipts, and enforces strict FEFO batch integrity and ownership isolation across company warehouses, distributors, and retail hypermarkets.

---

## 2. Synthetic FMCG Demo Scenario

| Attribute | Synthetic Value | Description / Business Context |
| :--- | :--- | :--- |
| **Target Product / SKU** | `SKU-GOODDAY-100` | Britannia Good Day Butter Cookies 120g (Shelf life: 180 days, Case pack: 24) |
| **Retail Destination** | `LOC-STORE-METRO` | Metro Mart Hypermarket Store #101 (Mumbai Suburban, Owned by `ORG-RETAIL-METRO`) |
| **Current Stock Position** | 35.0 cases on-hand | Initial store stock before replenishment |
| **Forecast Daily Demand** | ~24.7 cases/day | 7-day projected demand: 140.0 cases (Holdout-evaluated 7-day rolling baseline) |
| **Days of Cover** | **1.4 days** | **CRITICAL STOCKOUT DEFECT (< 2.0 days threshold; stockout in 34 hours)** |
| **Demand Gap** | **105.0 to 137.6 cases** | Deficit required to cover 7-day horizon + safety stock buffer |
| **Optimal Upstream Source** | `LOC-NDC-BHIWANDI` | Bhiwandi National Distribution Center (`ORG-FMCG-CORP`, 4,500 unexpired cases) |
| **Recommended Corridor** | `RTE-BHI-STORE` | Lead time: **2.0 days**, Freight cost: **3.20 INR/unit** via TCI BlueDart 3PL |
| **Protected Distributor Hub** | `LOC-DIST-WEST` | Apex Metro FMCG Hub (400 cases owned by `ORG-DIST-WEST` — strictly protected from company seizure) |
| **Near-Expiry Item** | `SKU-WINKIES-400` | Chocolate Swiss Roll (20 cases with 5 days remaining at Store #101 — pre-solver filtered from dispatch) |

---

## 3. Five Workspaces / Portals Overview

StockWise organizes operations into 5 dedicated, role-authorized workspaces:
1. **Company Admin (`/admin/network`):** Global supply chain network master, facility configuration, carrier agency contracts, and freight corridors.
2. **Distribution Intelligence (`/demand-risk`, `/optimize`, `/plans/compare`, `/utsav`):** Demand forecasting, stockout exposure analysis, OR-Tools lexicographic optimization, baseline comparisons, and festival uplift simulations.
3. **Warehouse & Logistics (`/inventory`, `/shipments`):** Multi-tier stock availability, batch expiry intelligence, shipment staging, FEFO reservation accounting, physical dispatch gate passes, and delivery audit logs.
4. **Distributor Portal (`/distributor`):** Dedicated distributor workspace for independent hub inventory visibility, inbound shipment tracking, and transfer requests.
5. **Retail Shop Portal (`/retailer`):** Retailer store inventory visibility, stockout warning badges, replenishment request submission, and receiving confirmation.

---

## 4. Click-by-Click Demonstration Script (5–7 Minutes)

```
       [Observe Demand] ──> [Detect Risk] ──> [Optimize Flow] ──> [Explain Decision]
              │                                                         │
       [Reconcile Stock] <── [Verify Delivery] <── [Physical Dispatch] <── [Stage & Reserve]
```

### Step 1: Open Company Admin & Inspect Distribution Network
- **Portal:** Company Admin (`/admin/network`)
- **Role Persona:** System Admin (`Bearer demo-admin-token` or role dropdown: `admin`)
- **Action:** Open Network Management tab.
- **Narrative to Judges:** *"Here in Company Admin, we see the full multi-tier FMCG network topology across Western India: 1 manufacturing plant in Khopoli, 1 central national DC in Bhiwandi, 1 regional C&F depot in Pune, 1 independent distributor hub in Apex Metro, and 1 retail destination at Metro Mart Store #101. We also see 6 permitted transit routes with negotiated freight rates and SLA lead times."*
- **Evidence:** 5 facilities displayed with node badges and 6 active transit corridors (rates ranging from 1.80 to 6.50 INR/unit).

### Step 2: View Multi-Tier Network Inventory Positions
- **Portal:** Warehouse & Logistics (`/inventory`)
- **Role Persona:** Supply Chain Planner / Logistics (`planner` or `admin`)
- **Action:** Click on Inventory. Review columns: On-Hand, Reserved, Blocked, Dispatchable Stock, Batch #, and Expiry Date.
- **Narrative to Judges:** *"Notice our strict mathematical inventory boundary: Dispatchable Stock = max(0, On-Hand - Reserved - Blocked). Goods in transit or reserved for staging never inflate dispatchable figures. In Bhiwandi DC, we have 4,500 unexpired cases of Good Day Cookies. But look at Metro Mart Store #101: it holds only 35 cases."*
- **Evidence:** Dispatchable stock strictly equals on-hand minus reserved minus blocked.

### Step 3: Show Demand Forecast & Stockout-Risk Alert
- **Portal:** Distribution Intelligence (`/demand-risk`)
- **Role Persona:** Supply Chain Planner (`planner`)
- **Action:** Select 7-Day Planning Horizon.
- **Narrative to Judges:** *"The system analyzes historical sales over the last 30 days using chronological out-of-sample moving average and seasonality baselines. It detects that Metro Mart Store sells ~24.7 cases per day. With only 35 cases on hand, days of cover is just 1.4 days. Because the earliest replenishment lead time is 2.0 days, the store will suffer an unavoidable stockout defect in 34 hours without intervention!"*
- **Evidence:** Critical stockout banner displayed with red alert badge (`cover_days = 1.4d < 2.0d`).

### Step 4: Run Constrained Optimization (2-Stage Lexicographic)
- **Portal:** Distribution Intelligence (`/optimize`)
- **Role Persona:** Supply Chain Planner (`planner`)
- **Action:** Set Strategy to "Two-Stage Lexicographic", enable "Enforce Batch Expiry", set "Min Shelf Life" to 14 days, click **Execute Optimization**.
- **Narrative to Judges:** *"Rather than guessing, we run our OR-Tools LP solver. In Stage 1, it minimizes unmet consumer demand to maximize on-shelf availability. In Stage 2, it minimizes freight costs while strictly preserving the optimal 100% service level. Within 1.1 seconds, the solver finds the mathematical optimum: ship 137.6 cases from Bhiwandi DC directly to Metro Mart Store #101."*
- **Evidence:** Solver status `optimal`, Service level 100.0%, solve time ~1,100ms.

### Step 5: Open Decision Receipt & Explain Recommendation
- **Portal:** Distribution Intelligence (`/optimize` -> Click "View Decision Receipt")
- **Role Persona:** Supply Chain Planner (`planner`)
- **Action:** Click "View Decision Receipt" on the recommended Good Day flow.
- **Narrative to Judges:** *"Judges often ask: why not send stock from the Khopoli manufacturing plant? The Decision Receipt explains the mathematical proof: Khopoli Direct takes 4.0 days (exceeding the 1.4-day stockout window) and costs 6.50 INR/case vs. 3.20 INR/case from Bhiwandi. Why not take from Apex Metro Distributor? Because that stock is owned by an independent third-party distributor (`ORG-DIST-WEST`) and legally protected from manufacturer reallocation. The decision receipt gives planners full auditability and confidence."*
- **Evidence:** Recommendation ID, Lead time (2.0d), freight cost ($3.20/case), and explicit list of rejected alternatives with quantified reasons.

### Step 6: Show Near-Expiry Scenario & Shelf-Life Eligibility
- **Portal:** Warehouse & Logistics (`/inventory`)
- **Role Persona:** Company Admin (`admin`)
- **Action:** Filter by SKU `SKU-WINKIES-400` (Chocolate Swiss Roll).
- **Narrative to Judges:** *"StockWise prevents perishable waste before it moves. Batch `BAT-WIN-STORE-NEAR` has an expiry date in just 5 days. Because our minimum customer shelf-life constraint is 14 days, our pre-solver engine automatically marks this batch ineligible for outbound replenishment, preventing expired products from entering transit."*
- **Evidence:** Expiry badge shows 5 days remaining, flagged as near-expiry.

### Step 7: Submit Replenishment Request from Retail Shop Portal
- **Portal:** Retail Shop Portal (`/retailer`)
- **Role Persona:** Retail Store Manager (`retailer`, `ORG-RETAIL-METRO`)
- **Action:** Click "New Replenishment Request". Select `SKU-GOODDAY-100`, Quantity `105`, Preferred Source `LOC-NDC-BHIWANDI`, click **Submit Request**.
- **Narrative to Judges:** *"The retail store manager sees their 35-case stock and submits an official store replenishment request for 105 cases. Notice that creating this request DOES NOT touch physical stock or warehouse allocations. Physical stock at Bhiwandi DC remains exactly 4,500."*
- **Evidence:** Request created with status `proposed`, `approval_status: pending`. Bhiwandi stock unchanged.

### Step 8: Approve Shipment with Authorized Account
- **Portal:** Warehouse & Logistics (`/shipments`)
- **Role Persona:** Central Supply Chain Approver (`admin` or `planner`)
- **Action:** Find the pending request, click "Approve", select 3PL Carrier `TCI BlueDart Consortium`.
- **Narrative to Judges:** *"The supply chain approver reviews the request against the optimizer run and clicks Approve. Crucial inventory safeguard: Approval authorizes the shipment; it NEVER dispatches vehicles or decrements physical stock. Bhiwandi on-hand remains 4,500."*
- **Evidence:** Shipment moves to `approved`. On-hand stock at source remains 4,500.

### Step 9: Stage Shipment & Verify FEFO Reservation Accounting
- **Portal:** Warehouse & Logistics (`/shipments`)
- **Role Persona:** Warehouse Operations Supervisor (`logistics`, `ORG-LOGISTICS-3PL`)
- **Action:** Click "Stage Dispatch / Prepare". Fill Bay 4, complete checklist, click **Stage**.
- **Narrative to Judges:** *"Now warehouse operations prepares the shipment. When they stage the cargo, StockWise engages FEFO reservation accounting: 105 cases are reserved against the earliest expiring fresh batch (`BAT-GD-BHI-FRESH`). On-hand is still 4,500, but dispatchable stock immediately drops to 4,395. This prevents double-allocation by any other store order."*
- **Evidence:** Shipment status `ready_for_dispatch`. Source reserved stock increments from 0.0 to 105.0. Dispatchable drops to 4,395.0.

### Step 10: Confirm Physical Dispatch & Show Shipment Tracking
- **Portal:** Warehouse & Logistics (`/shipments`)
- **Role Persona:** Warehouse Dispatch Manager (`logistics`)
- **Action:** Click "Confirm Dispatch". Enter Vehicle `MH-04-GP-8821`, Consignment `CN-TCI-2026-9812`, Driver contact, click **Confirm Dispatch**.
- **Narrative to Judges:** *"The truck is loaded and gates out. Physical dispatch confirms the movement into transit. At this exact moment, source on-hand decrements from 4,500 to 4,395, and reserved units drop back to 0. Consignment tracking number is locked in."*
- **Evidence:** Shipment status `in_transit`. Bhiwandi on-hand decremented to 4,395.0. Consignment and vehicle tracking visible.

### Step 11: Confirm Delivery & Reconcile Destination Inventory
- **Portal:** Retail Shop Portal (`/retailer`) or Warehouse & Logistics (`/shipments`)
- **Role Persona:** Receiving Officer (`retailer` or `logistics`)
- **Action:** Click "Confirm Delivery". Enter signed POD reference `POD-SIGNED-STORE-101-OCT26`, click **Confirm Delivery**.
- **Narrative to Judges:** *"The consignment arrives at Metro Mart Store #101 Dock 2. The store officer inspects cartons and enters the signed POD. Delivery confirmation credits the destination inventory: store stock increases from 35.0 to 140.0 cases. Days of cover jumps from 1.4 days to 5.6 days. The stockout defect has been completely eliminated."*
- **Evidence:** Shipment status `delivered`. Metro Mart Store #101 on-hand increases from 35.0 to 140.0 cases. Stockout badge disappears.

### Step 12: Attempt Duplicate Operation & Demonstrate Replay Protection
- **Portal:** Safe Replay Demonstration
- **Role Persona:** System Operator (`logistics`)
- **Action:** Attempt to call `POST /api/shipments/{id}/deliver` again with duplicate payload.
- **Narrative to Judges:** *"What happens if network latency causes a mobile scanner to submit the delivery confirmation twice? In inferior systems, destination stock would be credited twice, creating ghost inventory. Watch StockWise: the state machine and row lock immediately intercept the duplicate and return HTTP 400: `DUPLICATE_DELIVERY_REJECTED: Shipment has already been confirmed as delivered.` Store stock remains exactly 140.0 cases."*
- **Evidence:** API returns HTTP 400 `DUPLICATE_DELIVERY_REJECTED`. Store stock remains 140.0 cases.

### Step 13: Review Shipment Audit Trail & State Transitions
- **Portal:** Warehouse & Logistics (`/shipments` -> Click "Audit Events")
- **Role Persona:** Auditor / Supply Chain Director (`admin`)
- **Action:** Open the Shipment Audit Modal.
- **Narrative to Judges:** *"Every single action was cryptographically recorded in an immutable event log: proposed by retailer, approved by admin, staged by warehouse supervisor, dispatched by warehouse manager, and delivered by receiving officer. Full timestamped plan-to-execution traceability."*
- **Evidence:** Complete chronological chain of 6 events with actor IDs, roles, timestamps, and notes.

---

## 5. Key Decision & Inventory Safeguards

### Why Bhiwandi NDC is Recommended Over Alternatives
1. **Vs. Khopoli Manufacturing Plant:** Khopoli lead time is 4.0 days, which would arrive *after* the store's 1.4-day stockout point, causing stockout penalties. Freight rate is also 6.50 INR/case vs. 3.20 INR/case from Bhiwandi.
2. **Vs. Pune Regional C&F:** Pune freight rate is 4.80 INR/case with 3.0 days lead time (higher cost and slower transit).
3. **Vs. Apex Metro Distributor:** Apex Metro is located near Mumbai, but its 400 cases belong to an independent commercial distributor (`ORG-DIST-WEST`). StockWise enforces multi-tenant ownership boundaries and refuses to commandeer distributor-owned stock for retailer fulfillment.

### Inventory Accounting Invariants Verified
1. **Dispatchable Stock:** $\text{Dispatchable} = \max(0, \text{On-Hand} - \text{Reserved} - \text{Blocked})$.
2. **Physical Invariance:** Proposed requests and approvals do not alter physical warehouse stock.
3. **Reservation Integrity:** Staging reserves units under strict FEFO without changing physical stock.
4. **Exact Single Deduction:** Physical dispatch decrements source stock exactly once.
5. **Exact Single Credit:** Physical delivery credits destination stock exactly once.
6. **Replay Defense:** Duplicate delivery submissions return HTTP 400 and reject double-crediting.
7. **Shelf-Life Gating:** Near-expiry batches failing minimum shelf-life cutoffs are barred from replenishment.

---

## 6. Known Limitations & Honest Answers to Likely Judge Questions

| Likely Judge Question | Honest Engineering Answer |
| :--- | :--- |
| *"How does the system handle real-time IoT vehicle telematics GPS?"* | StockWise models route corridors, carrier assignments, SLA lead times, and gate-out/arrival checkpoints. Real-time GPS stream ingestion (Kafka/MQTT) is mapped into the `ShipmentEvent` lifecycle via carrier API webhooks, but live GPS map rendering is outside the current Phase 13 scope. |
| *"Can an independent distributor see company warehouse stock?"* | No. StockWise enforces strict server-side tenant isolation: non-admin distributor users can only query inventory snapshots and shipments where `owner_org_id == user.org_id` or `carrier_agency_id == user.org_id`. |
| *"What happens if the OR-Tools solver takes too long on a 100,000-SKU network?"* | StockWise supports hierarchical decomposition: solver clustering by geographical supply zone (e.g., West, North, South) and SKU velocity class (ABC classification), plus a fallback to deterministic nearest-eligible-source heuristic when solver timeouts occur. |
| *"How does StockWise handle partial damage or partial deliveries?"* | The delivery confirmation endpoint accepts partial quantity reconciliation, recording receiving condition notes, while the remainder transitions to an operational exception state (`exception_reason: damaged_in_transit`). |
| *"Is the synthetic demo reproducible on another machine?"* | Yes. The entire network, master catalog, inventory positions, and sales history are generated deterministically via `python seed_fmcg_demo.py --reset`. |

---

## 7. Environment Reset & Recovery Procedure

If any live demo step encounters an unexpected error or operator error during the presentation, run this single recovery command:

```bash
# In backend terminal:
cd backend
.venv\Scripts\python.exe seed_fmcg_demo.py --reset
```

This clears previous shipment events, movements, and snapshots, and restores the deterministic baseline:
- Good Day Butter Cookies at Store #101 = 35.0 cases (1.4 days cover).
- Good Day Butter Cookies at Bhiwandi NDC = 4,500 unexpired cases.
- Swiss Roll at Store #101 = 20 cases expiring in 5 days.
- Apex Metro Distributor stock = 400 cases protected.
