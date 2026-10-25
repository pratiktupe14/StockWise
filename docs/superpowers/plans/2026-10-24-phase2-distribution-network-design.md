# Phase 2: Real-World FMCG Distribution Network Design Implementation Plan

> **For agentic workers:** Implementation plan for Phase 2: Real-World Distribution Network Design. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement real-world Indian FMCG distribution network modeling in StockWise, distinguishing inventory ownership, facility operation, transport agencies, and decision approval across the 3 role-based portals (Company Admin, Distribution Intelligence, Warehouse & Logistics).

**Architecture:**
- **Database (Supabase PostgreSQL):** Alembic migration `002_real_world_distribution_network.py` adding `organizations`, extending `locations` (owner/operator orgs, city, coords, capacities), extending `inventory_snapshots` (owner org, batch, expiry), extending `routes` (carrier agency, active status, min/max shipment capacity, pricing basis), and adding `shipments` and `stock_movements`.
- **Backend (FastAPI):** Domain models in `backend/app/models/entities.py`, Pydantic schemas in `backend/app/schemas/network.py`, validation & eligibility services in `backend/app/services/network_service.py` and `validators.py`, API endpoints in `backend/app/api/network.py` and `backend/app/api/shipments.py`.
- **Frontend (React 19 + TypeScript + Tailwind):** Interactive 3-Portal Switcher in TopBar (`Company Admin`, `Distribution Intelligence`, `Warehouse & Logistics`), Network Management screen (`/network`) for organizations/facilities/routes, enhanced Inventory Page (`/inventory`) with ownership & batch tracking, Shipments & Dispatch Manager (`/shipments`), and Network Eligibility Analyzer.
- **Automated Tests:** Comprehensive Pytest suite covering all 12 acceptance criteria.

---

## Task Decomposition

### Task 1: Database Models & Alembic Migration
- Modify `backend/app/models/entities.py` to add `Organization`, `Shipment`, `StockMovement`, and extend `Location`, `InventorySnapshot`, and `Route` with ownership, operation, carrier agency, and capacity fields.
- Create Alembic revision `002_real_world_distribution_network.py`.
- Apply migration live to Supabase PostgreSQL and verify tables.

### Task 2: Pydantic Schemas & Network Services
- Create `backend/app/schemas/network.py` with request/response models for organizations, facilities, routes, shipments, eligibility checks, and approval actions.
- Implement `backend/app/services/network_service.py` to evaluate route eligibility, check non-interchangeable responsibilities (ownership vs storage vs carriage), enforce dispatchable stock limits, and prevent forbidden routes.
- Update `backend/app/services/validators.py` and `file_parser.py` to support importing organizations and updated location/route formats.

### Task 3: Backend REST API Endpoints
- Implement `backend/app/api/network.py`:
  - `GET /api/organizations`, `POST /api/organizations`
  - `GET /api/network/eligibility` (calculates valid source-to-destination routes, flags unserviceable locations, explains eligibility/rejection)
  - `POST /api/routes` (create/update routes with carrier agency, validation)
- Implement `backend/app/api/shipments.py`:
  - `GET /api/shipments` (list proposed/approved shipments)
  - `POST /api/shipments/propose` (propose shipment with strict validation: forbidden route rejection & stock capacity check)
  - `POST /api/shipments/{shipment_id}/approve` (authorize approval without auto vehicle dispatch)
  - `POST /api/shipments/{shipment_id}/status` (update shipment status with audit movement tracking)
- Register routers in `backend/app/main.py`.

### Task 4: Frontend Portal Switcher & 3-Portal Role Adaptation
- Update `TopBar.tsx` to provide an interactive **Portal Switcher**:
  - `Company Admin Portal`
  - `Distribution Intelligence Portal`
  - `Warehouse & Logistics Portal`
- Update `Sidebar.tsx` and `types/navigation.ts` to dynamically adapt navigation and workflow badges based on active portal context.
- Create `/network` (Network Management Page) in Company Admin Portal.
- Create `/shipments` (Warehouse & Logistics Dispatch Page).
- Extend `/inventory` with inventory ownership (Company vs Distributor vs C&F stored), batch numbers, and expiry.
- Extend `/approval` with shipment approval and governance audit log.

### Task 5: Automated Testing (All 12 Acceptance Criteria)
- Create `backend/tests/test_distribution_network.py` testing:
  1. Register company warehouse and separate C&F facility.
  2. C&F facility stores company-owned inventory without ownership change.
  3. Distributor represented as independent organization and destination.
  4. 3PL provider assigned to route without becoming inventory owner.
  5. Dispatchable stock calculation excludes reserved & blocked.
  6. Forbidden route rejection and source stock limit enforcement.
  7. Incomplete/invalid route cost/lead-time flagging.
  8. Inactive facility and route exclusion from eligibility.
  9. Duplicate import and invalid reference rejection.
  10. Shipment approval governance without false delivery claims.
  11. Multi-portal integration and accessibility.
  12. Existing 19 backend tests passing without regression.

### Task 6: Verification, Production Build & Implementation Status Report
- Run `pytest` on all tests.
- Run `npm run lint` and `npm run build`.
- Update `docs/implementation-status.md`.
