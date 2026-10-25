# StockWise — Phase 5 Security Hardening, Tenant Isolation & Production Reliability

**Document Version:** 1.0  
**Status:** Completed & Fully Verified  
**Date:** October 2026  
**Scope:** Security Audit, Fail-Closed Authentication, Multi-Tenant Isolation, Concurrency Safeguards & Reliable Production Hardening  

---

## 1. Executive Summary

Phase 5 addresses critical security vulnerabilities, multi-tenant isolation risks, and concurrency hazards identified during a comprehensive pre-portal security audit of StockWise. Prior to opening portals to external third parties (Distributors, C&F Agents, 3PL Carriers, and Retail Outlets), StockWise required enterprise-grade guarantees:
1. **Fail-Closed JWT Authentication**: Cryptographic signature validation with PyJWT, eliminating mock/demo bypass tokens in production environments.
2. **Server-Side Role & Tenant Derivation**: Preventing privilege escalation via self-signed or client-editable Supabase `user_metadata`.
3. **Strict Organization-Level Tenant Isolation**: Enforcing tenant boundaries across inventory queries, data imports, optimization runs, Decision Receipts, shipment governance, physical dispatch, and audit event logs.
4. **Idempotency & Concurrency Safeguards**: Atomically locking rows (`SELECT ... FOR UPDATE`) during status transitions and stock movements, preventing duplicate physical dispatch, rolling back reservations on shipment cancellation, and returning HTTP 409 Conflict when an idempotency key is reused with a conflicting payload.
5. **Frontend Security & Authenticated Downloads**: Replacing direct `<a href>` export links with authenticated Blob fetch requests containing `Authorization: Bearer` tokens, removing demo persona switchers from production bundles, and guaranteeing that `isAuthenticated` reflects only verified sessions.

---

## 2. Audit Findings & Severity Classification

Before modifying codebase components, an exhaustive audit was performed across all backend API routers, models, services, frontend contexts, API clients, and configuration files.

| Finding ID | Severity | Category | Description | Remediation Status |
|---|---|---|---|---|
| **CRIT-1** | Critical | Authentication | Bearer token validation accepted unverified tokens and allowed arbitrary mock persona tokens (`demo-admin-token`, `demo-planner-token`) in all environments. | **Resolved**: Enforced fail-closed PyJWT signature validation; disabled all demo tokens when `ALLOW_DEMO_AUTH=False` or `ENVIRONMENT=production`. |
| **CRIT-2** | Critical | Authorization | Roles and organization IDs were read directly from untrusted client-editable `user_metadata`, permitting unauthorized self-elevation to `admin` or cross-tenant org impersonation. | **Resolved**: Implemented `derive_trusted_role_and_org()`. Demotes self-assigned roles to `viewer` unless explicitly backed by server-controlled `app_metadata` or verified server mapping. |
| **CRIT-3** | Critical | Tenant Isolation | Key endpoints (`/api/inventory`, `/api/imports`, `/api/optimization/runs`, `/api/shipments`) returned global database records or lacked tenant scoping filters, allowing cross-tenant data leaks. | **Resolved**: Added `owner_org_id` / `org_id` query filters and tenant access validators across all operational routes. |
| **CRIT-4** | Critical | Concurrency | Cancellation of shipments did not atomically release reserved inventory; duplicate dispatch calls could trigger race conditions and double stock deduction. | **Resolved**: Added `with_row_lock()` (`FOR UPDATE` on PostgreSQL, no-op on SQLite) during reservation release and physical dispatch; enforced state guard `DUPLICATE_DISPATCH_REJECTED`. |
| **HIGH-1** | High | Reliability | Idempotency service did not verify payload matching, returning cached 200 responses even when the caller sent a completely different payload under the same key. | **Resolved**: Added SHA-256 payload fingerprinting and enforced HTTP 409 Conflict on payload mismatch. |
| **HIGH-2** | High | Security | CSV and Excel file downloads (`/export/receipts.csv`, `/errors.csv`, `/utsav/uplift/export`) relied on unauthenticated native browser links (`<a href>`), bypassing `Authorization: Bearer` headers. | **Resolved**: Built `downloadAuthenticatedFile()` helper in frontend; converted all export UI elements to authenticated fetch + Blob triggers. |
| **HIGH-3** | High | Tenant Isolation | Planning runs and Decision Receipts were not bound to an organization identity, permitting cross-company visibility into confidential supplier costs and allocation logic. | **Resolved**: Added `org_id` and `created_by_user_id` persistence to `PlanningRun` model and scoped all retrieval/export endpoints. |
| **HIGH-4** | High | Data Ingestion | Import executions could be inspected and downloaded by any authenticated user regardless of organization affiliation. | **Resolved**: Scoped `ImportRun` by `org_id` and protected error CSV export endpoints with tenant checks. |
| **MED-1** | Medium | Frontend Auth | `AuthContext` held `isAuthenticated: true` indefinitely based on local storage cache, even after token expiry or server revocation. | **Resolved**: Added active session check and token validity verification on mount and state transitions. |
| **MED-2** | Medium | Attack Surface | Demo persona selector was rendered in production bundles, allowing end-users to simulate administrative identities. | **Resolved**: Gated persona selector strictly behind `isDemoAllowed() && user.isDemo` with an unambiguous `DEV MODE` badge. |
| **MED-3** | Medium | Authorization | Global network topology endpoints (`/api/organizations`, `/api/network/locations`, `/api/network/routes`) allowed unauthenticated reads and unverified non-admin writes. | **Resolved**: Required authentication for read operations and restricted mutating operations strictly to `admin`. |
| **MED-4** | Medium | Data Isolation | UtsavSense festival uplift calculations and scenario runs did not associate optimization runs with tenant boundaries. | **Resolved**: Injected tenant identity into Utsav festival optimization executions. |
| **LOW-1** | Low | Configuration | Environment example configuration files lacked explicit JWT algorithm, audience, and demo flag guidelines. | **Resolved**: Updated `backend/.env.example` and `frontend/.env.example` with safe production defaults. |
| **LOW-2** | Low | Error Handling | Error responses on cross-tenant unauthorized access returned HTTP 403, confirming the existence of competitor resource IDs. | **Resolved**: Standardized on HTTP 404 Not Found for cross-tenant resource queries to prevent tenant ID harvesting. |

---

## 3. Architecture & Security Implementation

### 3.1 Authentication & Token Verification (`backend/app/core/security.py`)
- **Cryptographic Validation**: Uses `jwt.decode` with the HMAC-SHA256 algorithm (`settings.SUPABASE_JWT_ALGORITHM`), verifying token signature, expiration (`exp`), and audience (`aud="authenticated"`).
- **Production Fail-Closed Guarantee**:
  ```python
  if settings.is_production() or not settings.is_demo_allowed():
      if not token:
          raise HTTPException(status_code=401, detail="Missing authorization token.")
      claims = verify_supabase_jwt(token)
  ```
  Mock demo tokens (`demo-admin-token`, `demo-planner-token`, etc.) are unconditionally rejected in production.

### 3.2 Trusted Role & Tenant Derivation
Supabase authentication allows clients to supply arbitrary JSON in `user_metadata` upon registration. To prevent privilege escalation:
- Only claims in server-controlled `app_metadata` or pre-configured server mappings (`DEMO_USERS`) are granted privileged roles (`admin`, `planner`, `logistics`).
- Client-supplied claims in `user_metadata` attempting to declare `role: "admin"` or `role: "planner"` are strictly demoted to `viewer`.
- If an organization ID is not present in trusted claims, the user cannot access tenant-scoped records.

### 3.3 Multi-Tenant Isolation Enforcement
All operational resources are segregated by `owner_org_id` / `org_id`:
- **Inventory (`/api/inventory`)**: Filtered by `InventorySnapshot.owner_org_id == current_user.org_id`.
- **Import Runs (`/api/imports`)**: Scoped to the importing tenant. Downloading another organization's validation errors returns HTTP 404.
- **Optimization & Receipts (`/api/optimization/runs`)**: `PlanningRun` records store `org_id` and `created_by_user_id`. Reading runs or exporting Decision Receipts of another tenant returns HTTP 404.
- **Shipments & Logistics (`/api/shipments`)**: Verified via `check_shipment_tenant_access()`. A tenant can only read, approve, dispatch, or cancel shipments where `owner_org_id == current_user.org_id` (or where the user belongs to the assigned carrier agency). Non-existent or competitor shipments return HTTP 404.
- **Network Administration (`/api/organizations`, `/api/network/*`)**: Creating or mutating organizations, locations, and routes requires verified `admin` role.

### 3.4 Concurrency, Idempotency & Inventory Safety
- **Row-Level Locking (`with_row_lock`)**: Uses `with_for_update()` on PostgreSQL transactions to prevent concurrent updates from racing on stock deductions and reservation releases.
- **Atomic Reservation Release**: When a shipment in `ready_for_dispatch` is cancelled, its reserved quantity is atomically released back into dispatchable stock (`reserved = max(0, reserved - quantity)`).
- **Duplicate Dispatch Prevention**: If a shipment is already `in_transit`, any subsequent dispatch call is rejected with `DUPLICATE_DISPATCH_REJECTED` (HTTP 400), ensuring physical inventory cannot be double-deducted.
- **Strict Idempotency Conflict Handling**: Replaying an `Idempotency-Key` with an identical payload returns the cached result. Reusing the same key with a different payload returns **HTTP 409 Conflict**:
  ```python
  if cached_req != incoming_req:
      raise HTTPException(
          status_code=409,
          detail=f"Idempotency conflict: key '{key}' was previously used with a different request payload."
      )
  ```

### 3.5 Frontend Security & Authenticated Downloads
- **Authenticated File Downloads (`downloadAuthenticatedFile`)**:
  ```typescript
  export async function downloadAuthenticatedFile(url: string, filename: string): Promise<void> {
    const headers = getAuthHeaders();
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error(`Download failed: HTTP ${res.status}`);
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    // Trigger download & immediately revokeObjectURL
  }
  ```
  Applied across:
  - Decision Receipts CSV export (`ApprovalExportPage.tsx`)
  - Comparative Plan Summary CSV export (`ApprovalExportPage.tsx`)
  - Import quarantine error reports (`ImportCentrePage.tsx`)
  - UtsavSense festival uplift CSV export (`UtsavSensePage.tsx`)
- **Demo Mode Isolation**: The persona selector in `TopBar.tsx` is only rendered if `isDemoAllowed() && user.isDemo`. In production deployments (`VITE_ALLOW_DEMO_AUTH=false`), the selector is completely stripped from view.

---

## 4. Verification & Test Evidence

### 4.1 Automated Backend Security Test Suite (`backend/tests/test_phase5_security.py`)
18 dedicated security and reliability tests were developed and executed:
1. `test_missing_authorization_header_rejected_fail_closed`: Verifies HTTP 401 on unauthenticated access.
2. `test_invalid_signature_rejected_fail_closed`: Verifies cryptographic rejection of forged tokens.
3. `test_expired_jwt_rejected`: Verifies rejection of expired JWTs.
4. `test_production_rejects_demo_tokens_unconditionally`: Verifies that mock demo tokens fail closed in production.
5. `test_privilege_escalation_user_metadata_demoted_to_viewer`: Confirms client-editable `user_metadata` cannot elevate privileges.
6. `test_server_verified_app_metadata_role_trusted`: Confirms server-controlled `app_metadata` is respected.
7. `test_tenant_cannot_read_another_organization_inventory`: Verifies strict isolation on `/api/inventory`.
8. `test_tenant_cannot_access_another_organization_import_runs`: Verifies isolation on imports and error CSVs.
9. `test_tenant_cannot_access_or_export_another_organization_planning_runs`: Verifies isolation on optimization runs and Decision Receipts.
10. `test_tenant_cannot_read_or_mutate_another_organization_shipments`: Verifies isolation on shipment listing, detail, approval, dispatch, and cancellation.
11. `test_non_admin_cannot_perform_global_network_administration`: Verifies RBAC restrictions on network master tables.
12. `test_idempotency_exact_replay_returns_cached_200`: Confirms safe replay of cached operational actions.
13. `test_idempotency_mismatched_payload_returns_409_conflict`: Confirms HTTP 409 rejection of conflicting payloads under existing keys.
14. `test_duplicate_dispatch_cannot_consume_stock_twice`: Verifies duplicate dispatch rejection and stock protection.
15. `test_shipment_cancellation_releases_reserved_stock`: Verifies atomic reservation release on cancellation.
16. `test_decision_receipt_export_tenant_isolation`: Confirms competitor cannot export Decision Receipts.
17. `test_utsav_festival_optimization_tenant_isolation`: Confirms festival scenario runs enforce tenant identity.
18. `test_options_cors_preflight_unaffected_by_auth`: Confirms CORS preflight requests continue functioning smoothly.

### 4.2 Complete Pytest Test Suite Results
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.7.0
rootdir: D:\TRIWIZATHON hackathon\StockWise\backend
plugins: anyio-4.15.1
collected 82 items

tests\test_distribution_intelligence.py ............                     [ 14%]
tests\test_distribution_network.py ............                          [ 29%]
tests\test_health.py ......                                              [ 36%]
tests\test_imports.py .............                                      [ 52%]
tests\test_logistics_execution.py .........                              [ 63%]
tests\test_missing_features_and_utsav.py .........                       [ 74%]
tests\test_phase5_security.py ..................                         [ 96%]
tests\test_production_readiness.py ...                                   [100%]

======================= 82 passed, 4 warnings in 16.40s =======================
```

### 4.3 Frontend Compilation & Linting Results
```text
> frontend@0.0.0 build
> tsc -b && vite build

vite v8.3.5 building client environment for production...
✓ 2012 modules transformed.
dist/index.html                   1.47 kB │ gzip:   0.80 kB
dist/assets/index-Bbj9o8zn.css   58.35 kB │ gzip:  10.35 kB
dist/assets/index-B2Dq5JsW.js   544.26 kB │ gzip: 136.38 kB
✓ built in 396ms
```
Linter verification: `Found 17 warnings and 0 errors` (all 17 warnings relate to standard React Compiler dependency optimizations; 0 lint errors, 0 build blockers).

---

## 5. Configuration Guide & Production Deployment Safeguards

To deploy StockWise in a hardened production environment, configure the following environment variables:

### Backend (`backend/.env`)
```bash
ENVIRONMENT=production
DEBUG=False
REQUIRE_AUTH=True
ALLOW_DEMO_AUTH=False
SUPABASE_JWT_SECRET=<your_actual_supabase_jwt_secret>
SUPABASE_JWT_ALGORITHM=HS256
SUPABASE_JWT_AUDIENCE=authenticated
DATABASE_URL=postgresql+psycopg2://postgres.<project_ref>:<password>@<host>:5432/postgres?sslmode=require
ALLOWED_ORIGINS=https://app.stockwise.internal,https://admin.stockwise.internal
ENABLE_IDEMPOTENCY=True
```

### Frontend (`frontend/.env`)
```bash
VITE_API_BASE_URL=/api
VITE_SUPABASE_URL=https://<project_ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<your_actual_supabase_anon_key>
VITE_ALLOW_DEMO_AUTH=false
VITE_APP_ENV=production
```

---

## 6. Known Remaining Risks & Future Work

1. **Database Row-Level Security (RLS)**: Tenant isolation is currently enforced at the application/ORM service layer. For defense-in-depth, PostgreSQL RLS policies can be mirrored directly in PostgreSQL when direct client connections are enabled in future portal phases.
2. **Distributor & Retail Portals**: Multi-tenant authorization boundaries are now strictly defined and verified, creating a secure foundation for introducing external Distributor and Retailer portals in subsequent milestones.
