# StockWise

> **The right stock. At the right place. Before it is too late.**  
> Enterprise FMCG distribution intelligence and inventory optimization platform.

---

## Overview

StockWise is a decision-support system designed to solve network-wide distribution challenges in FMCG supply chains. Instead of isolated stockout warnings, StockWise calculates which products to move, in what quantities, from which warehouse, to which destination, by when—and why that choice is feasible.

This repository represents **Phase 1: Clean Light-Theme UI & Project Foundation**.

---

## Phase 1 Architecture

```
StockWise/
├── codex_StockWise__PRD.md     # Product Requirements Document
├── docker-compose.yml          # Local PostgreSQL 16 container definition
├── .gitignore                  # Git ignore rules for Python, Node, & secrets
├── README.md                   # Setup & developer documentation
├── docs/
│   └── implementation-status.md# Verified Phase 1 status and acceptance criteria
├── backend/                    # Python FastAPI service
│   ├── .env.example            # Environment variables placeholder
│   ├── .env                    # Local development configuration
│   ├── requirements.txt        # Pinned dependencies
│   ├── alembic.ini             # Alembic migration configuration
│   ├── alembic/                # Migration scripts
│   ├── app/
│   │   ├── main.py             # FastAPI entry point & CORS
│   │   ├── core/               # App configuration & SQLAlchemy database engine
│   │   ├── api/                # Health check endpoint (/api/health)
│   │   └── schemas/            # Pydantic validation contracts
│   └── tests/                  # Pytest automated test suite
└── frontend/                   # React + TypeScript + Vite + Tailwind CSS
    ├── index.html              # HTML shell with Google Inter font
    ├── vite.config.ts          # Vite configuration with proxy to port 8000
    ├── src/
    │   ├── styles/             # Light-theme design tokens
    │   ├── types/              # TypeScript contracts for all domains
    │   ├── services/           # Live API client
    │   ├── hooks/              # useHealth status hook
    │   ├── components/         # Reusable UI primitives & layout shell
    │   └── pages/              # 7 navigable page foundations
```

---

## Design System & Theme

StockWise uses a bespoke **light-theme** corporate supply chain design system:

| Token | Hex Value | Usage |
|---|---|---|
| **Page Background** | `#F7F8FA` | Neutral, spacious workspace canvas |
| **Surface / Cards** | `#FFFFFF` | Clean white cards with subtle borders |
| **Primary Text** | `#172033` | Deep navy for high-contrast legibility |
| **Secondary Text** | `#667085` | Muted slate for metadata and descriptions |
| **Primary Accent** | `#2563EB` | Refined blue for primary actions & active states |
| **Borders** | `#E5E7EB` | Subtle light grey boundary dividers |
| **Success** | `#16A34A` / `#DCFCE7` | Restrained green for connected/healthy indicators |
| **Warning** | `#D97706` / `#FEF3C7` | Restrained amber for degraded / high-risk states |
| **Critical Risk** | `#DC2626` / `#FEE2E2` | Restrained red for disconnected / critical stockouts |

---

## Getting Started (Windows PowerShell)

### Prerequisites
- Python 3.12+
- Node.js 20+ & npm
- (Optional) Docker Desktop for local PostgreSQL

---

### Step 1: Start PostgreSQL (Optional for local DB)

If Docker Desktop is installed, start PostgreSQL:
```powershell
docker compose up -d
```
*Note: If Docker is not running, the FastAPI service will still launch normally and report `status: "degraded"` with `database: "disconnected"`. It will never crash or fake connectivity.*

---

### Step 2: Start Backend API Service

Open a Windows PowerShell terminal:

```powershell
# Navigate to backend directory
cd backend

# Create virtual environment if not already present
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start FastAPI development server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API Root: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Interactive OpenAPI Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Live Health Check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

### Step 3: Run Backend Tests

```powershell
# From the backend directory
pytest tests -v
```
All 6 automated tests verify root metadata, health schemas, database connectivity checks, and CORS headers.

---

### Step 4: Start Frontend Development Server

Open a second Windows PowerShell terminal:

```powershell
# Navigate to frontend directory
cd frontend

# Install npm dependencies (if not already installed)
npm install

# Start Vite development server
npm run dev
```

Open your browser to: **[http://127.0.0.1:5173](http://127.0.0.1:5173)**

---

### Step 5: Frontend Quality Checks

```powershell
# From the frontend directory:

# Run linter (oxlint)
npm run lint

# Run TypeScript type-check and production build
npm run build
```

---

## 7 Core Application Pages

1. **Overview (`/`):** Executive summary with 4 neutral summary cards, onboarding checklist, end-to-end planning workflow visual progression, live system health diagnostics, and an empty activity log.
2. **Import Centre (`/imports`):** Catalogs the 5 supported dataset categories (*Products, Current Inventory, Sales History, Locations, Permitted Routes*), expected schemas, and validation rules.
3. **Inventory (`/inventory`):** Multi-location dispatchable stock table layout (`max(0, OH - Reserved - Blocked)`) with search and filter controls.
4. **Risk & Demand (`/risk-demand`):** Configurable risk scoring tiers (*Critical, High, Medium, Low*), 7-day planning horizon selector, and demand shortfall table layout.
5. **Optimize Plan (`/optimize`):** Explains the 2-stage lexicographic solver policy, displays prerequisite verification gates, and features a locked solver action.
6. **Plan Comparison (`/comparison`):** Transparent benchmarking methodology against a deterministic nearest-eligible-source policy.
7. **Approval & Export (`/approval`):** Highlights the operational dispatch boundary (*recommendation only; no direct vehicle dispatch*), Decision Receipt format, and shipment recommendations table.

---

## Strict Scope Boundaries (Phase 1)

In adherence to the PRD:
- No synthetic operational data or fake charts are presented.
- No mock savings percentages or false stock numbers are displayed.
- The UI features typed, honest empty states across all screens.
- Full CSV parsing, demand forecasting, OR-Tools optimization, and Decision Receipt generation will be implemented in subsequent phases.
