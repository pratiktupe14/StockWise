# StockWise — Production Operations & Deployment Guide

## 1. System Architecture Overview

StockWise is an enterprise-grade FMCG Distribution Intelligence and Inventory Optimization platform designed to handle multi-echelon supply networks, demand forecasting, LP/MIP optimization, Utsav festival demand uplifts, and logistics shipment lifecycle execution.

```
                    +------------------------------------+
                    |        Frontend Client (SPA)       |
                    |   React 19 / TypeScript / Vite     |
                    |    Tailwind CSS / Lucide Icons     |
                    +-----------------+------------------+
                                      |
                     Reverse Proxy    | HTTPS / Bearer JWT
                     & Static Nginx   | (or Demo Identity)
                                      v
                    +-----------------+------------------+
                    |        FastAPI Backend App         |
                    |     Python 3.12 / Uvicorn ASGI     |
                    |  - Structured Logging (Request-ID) |
                    |  - Server-side RBAC (4 Roles)      |
                    |  - Idempotency Hash & Replay       |
                    +--------+------------------+--------+
                             |                  |
      OR-Tools / HiGHS LP    |                  | PostgreSQL Pool
                             v                  v
                    +--------+-------+  +-------+--------+
                    | Linear Solver  |  | Supabase       |
                    | SciPy / GLOP   |  | PostgreSQL DB  |
                    | Cost Optimizer |  | (Row Locking)  |
                    +----------------+  +----------------+
```

### Portals Preserved
1. **Company Admin Portal:**
   - Network Management (`/network`): Organizations, Tier 1/2 facilities, and permitted route matrices.
   - Import Centre (`/imports`): Bulk CSV/JSON ingest with dry-run validation preview.
2. **Distribution Intelligence Portal:**
   - Inventory Tracking (`/inventory`): Multi-echelon stock levels, transit stock, days-of-cover.
   - Risk & Demand (`/risk-demand`): Safety stock calculation, stockout risks, demand forecasts.
   - Plan Optimization (`/optimize`): HiGHS / OR-Tools MIP solver with custom cost weights.
   - Baseline Comparison (`/comparison`): Solver vs Nearest-Source heuristic comparison with Decision Receipts.
   - UtsavSense (`/utsav-sense`): Regional Indian festival calendar, festive uplift multipliers, and demand overrides.
3. **Warehouse & Logistics Portal:**
   - Shipment Management (`/shipments`): Stage-gate workflow (Draft -> Approved -> Prepared -> Dispatched -> Delivered).
   - Approval & Export (`/approval`): Dispatch revalidation, carrier assignment, CSV manifest exports.

---

## 2. Authentication & Server-Side RBAC

### Role Matrix

| Role | Permitted Actions | Restricted Actions |
| :--- | :--- | :--- |
| **`admin`** | Full network topology configuration, partner onboarding, data imports, planning, approvals, dispatch, delivery, and system health checks. | None. |
| **`planner`** | Ingest data, trigger demand forecasts, run optimizations, configure UtsavSense scenarios, approve shipments, and export manifests. | Cannot alter physical network topology (create/delete nodes or routes). |
| **`logistics`**| Inspect approved shipments, allocate carriers, reserve inventory, record physical dispatch, confirm delivery, and report exceptions. | Cannot approve plans, run optimization, edit demand forecasts, or alter routes. |
| **`viewer`** | Read-only inspection of dashboards, inventory levels, routes, and shipments. | All mutation endpoints (`POST`, `PUT`, `DELETE`) return `403 Forbidden`. |

### Backend Token Validation Flow
1. **Supabase Auth Integration:** Clients authenticate against Supabase Auth (`supabase.auth.signInWithPassword` or OAuth).
2. **JWT Verification:** Backend validates `Authorization: Bearer <token>` using `SUPABASE_JWT_SECRET` (HS256) or JWKS endpoints.
3. **Role Extraction:** Evaluates `user_metadata.role` or `app_metadata.role`.
4. **Development/Demo Mode Fallback:** When `ALLOW_DEMO_AUTH=true` and `REQUIRE_AUTH=false`, development requests can supply `X-StockWise-Role` and `X-User-Id` for rapid integration testing without an active identity server. In production (`REQUIRE_AUTH=true`), all requests must supply a cryptographically signed Bearer JWT.

---

## 3. Database Reliability & Concurrency Safeguards

### Dialect-Aware Row Locking (`with_row_lock`)
To prevent concurrent race conditions during shipment preparation, stock movements, and delivery confirmations:
- Inventory rows are locked using `with_row_lock(query, db)`.
- On PostgreSQL (Production Supabase), this compiles to `SELECT ... FOR UPDATE`, guaranteeing serializable reservation safety.
- On SQLite (Test/Development), it safely falls back to standard queries, ensuring 100% test suite compatibility without lock dialect errors.

### Idempotency Protections (`Idempotency-Key`)
Shipment operations (`/api/shipments/{id}/prepare`, `/dispatch`, `/deliver`) and network creation endpoints accept an `Idempotency-Key` header.
- **Payload Hashing:** Backend calculates a SHA-256 fingerprint of the request body and endpoint.
- **Deduplication:** If an identical key and hash exist in `idempotency_records`, the previously recorded HTTP status code and response payload are immediately replayed.
- **Conflict Guard:** If the same key is reused with a *different* payload, backend rejects the request with `409 Conflict`.

---

## 4. Deployment Configuration

### Containerized Deployment (Docker & Compose)

#### Backend Container (`backend/Dockerfile`)
- Multi-stage build based on `python:3.12-slim`.
- Dedicated non-privileged `stockwise` user (`UID 10001`).
- Built-in container healthcheck querying `/api/ready`.
- Port: `8000`.

#### Frontend Container (`frontend/Dockerfile` & `frontend/nginx.conf`)
- Multi-stage Node 20 build -> Nginx 1.27-alpine runtime.
- Security headers configured: `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`.
- Reverse proxy route: `/api/` proxies to backend service `http://backend:8000/api/`.
- Single Page Application (SPA) routing: `try_files $uri $uri/ /index.html;`.
- Port: `80`.

#### Orchestration (`docker-compose.yml`)
```bash
# Build and run the complete stack
docker compose up -d --build

# Inspect service logs
docker compose logs -f

# Check container health status
docker compose ps
```

---

## 5. Database Migration & Rollback Procedures

### Current Database Revision
The database schema is managed via Alembic:
- **Current Head:** `006_idempotency`
- **Revision History:**
  - `001_initial`: Core organizations, locations, products, and inventory items.
  - `002_network_design`: Permitted routes, multi-echelon transit matrices.
  - `003_planning_and_forecasting`: Demand forecasts and optimization plans.
  - `004_logistics_execution`: Shipment lifecycle, carrier assignments, audit trail.
  - `005_utsav_sense`: Indian regional festivals, uplift multipliers, override scenarios.
  - `006_idempotency`: Enterprise idempotency tracking table.

### Applying Migrations
```powershell
cd backend
# Verify current revision vs database
.\.venv\Scripts\alembic current

# Upgrade to latest revision
.\.venv\Scripts\alembic upgrade head
```

### Rollback Procedure
```powershell
# Roll back single revision
.\.venv\Scripts\alembic downgrade -1

# Roll back to specific revision
.\.venv\Scripts\alembic downgrade 005_utsav_sense
```

### Non-Destructive Backup & Restore (PostgreSQL / Supabase)
```bash
# Export schema and data dump
pg_dump -h db.<PROJECT-REF>.supabase.co -U postgres -d postgres -F c -b -v -f stockwise_prod_backup_$(date +%Y%m%d_%H%M%S).dump

# Restore into isolated staging database
pg_restore -h staging-db.<PROJECT-REF>.supabase.co -U postgres -d postgres -v stockwise_prod_backup_<TIMESTAMP>.dump
```

---

## 6. Health & Readiness Monitoring

### Probes

| Endpoint | Method | Purpose | Response |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | Basic liveness probe for load balancers. | `{"status": "ok", "app": "StockWise API", "version": "1.0.0"}` |
| `/api/ready` | `GET` | Deep readiness probe verifying DB pool and query latency. | `{"status": "ready", "database": "healthy", "latency_ms": 1.25, ...}` |

---

## 7. Manual Go-Live Checklist

- [ ] **Supabase Authentication Configured:** Set `REQUIRE_AUTH=true`, `ALLOW_DEMO_AUTH=false`, and provide `SUPABASE_JWT_SECRET`.
- [ ] **CORS Origins Restricted:** Replace `CORS_ORIGINS=["*"]` with explicit production domains in `.env`.
- [ ] **Alembic Head Verified:** Run `alembic current` and ensure head matches `006_idempotency`.
- [ ] **Database Connection Pool Verified:** Validate pgbouncer/session pooler limits on Supabase.
- [ ] **Readiness Probe Passing:** Verify `GET /api/ready` responds with HTTP 200 and `"database": "healthy"`.
- [ ] **Optimizer Availability:** Verify HiGHS and OR-Tools solvers instantiate without error.
- [ ] **Role Permissions Tested:** Validate that `viewer` role cannot mutate shipments or routes.
- [ ] **SSL / TLS Termination:** Verify reverse proxy enforces HTTPS with valid certificates.
