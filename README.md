# AICTE CaseTrack (SIH26264)
**Integrated Dashboard for Monitoring and Tracking Institution-Related Complaint Cases Across AICTE Bureaus/Cells**

Problem Statement ID: **SIH26264**  
Organization: **All India Council for Technical Education (AICTE)**  
Category: **Software** | Theme: **Smart Automation**

---

## Overview

AICTE receives grievances and regulatory complaints regarding technical education institutions across multiple internal divisions, including:
- **Regulation Bureau (RB)**
- **Public Grievance Redressal Cell (PGRC)**
- **Approval Bureau (AB)**

Previously, fragmented systems resulted in multiple cells handling overlapping cases for the same institution without real-time synchronization, causing redundant inspections, tracking gaps, and conflicting actions.

**AICTE CaseTrack** provides an integrated single-window command dashboard that connects internal divisions, synchronously detects cross-bureau overlaps, enforces strict 5-stage case lifecycle rules, protects high-confidentiality whistleblower complaints, monitors SLA deadlines, and produces bureau/regional MIS reports.

---

## Key Features

1. **Single-Window Command Dashboard:** Consolidated tracking of all technical institution complaints across AICTE Bureaus.
2. **Deterministic Cross-Bureau Overlap Engine:** Synchronously detects whenever multiple active cases exist for the same AICTE Permanent ID across different bureaus (e.g. RB vs. PGRC). Automatically alerts officers and auto-resolves when qualifying conditions terminate.
3. **Strict 5-Stage Lifecycle State Machine:**
   - Active: `Pending`, `Under Process`, `Transferred`, `Escalated`.
   - Terminal: `Disposed` (direct disposal from Pending is strictly rejected).
4. **Bureau Transfers & Escalations:** Audited transfers with explicit receiving-bureau acceptance, supervisor escalation queues, and immutable `CaseHistory` trails.
5. **Cross-Bureau Confidentiality:** Role-aware visibility policy where `HIGH` confidentiality cases expose only Case ID, Institution, and Bureau to other divisions; all private remarks, narratives, and complainant details are redacted at the API layer.
6. **CSV Ingestion & Registry Protection:** Batch uploads (capped at 200 rows) with authoritative Permanent ID matching, duplicate external record idempotency, and review queue (`ImportIssue`).
7. **SLA Deadlines & Testable Clock:** Deterministic calendar-day SLA calculations, approaching-deadline warnings, overdue breach detection, and an injectable time machine for demonstration.
8. **MIS Analytics & Safe CSV Export:** Workload, regional, and ageing distributions with spreadsheet formula-injection prevention (`=`, `+`, `-`, `@` neutralized).

---

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy 2.0, Pydantic, Python 3.11+ (SQLite dev / PostgreSQL prod)
- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS design system
- **Security:** Argon2id password hashing, HttpOnly session cookies, role & bureau-scope authorization, formula-safe CSV export
- **Testing:** Pytest, Starlette TestClient (33 automated integration tests)

---

## Local Setup & Quick Start

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Run idempotent development seed (Institutions, Bureaus, Demo cases, SLA rules)
python -m app.seed

# Start backend server (http://localhost:8000, docs at /docs)
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

---

## Development Logins (Pre-Seeded)

| Role | Username | Password | Permitted Scope |
| :--- | :--- | :--- | :--- |
| **Central Administrator** | `admin` | `admin123` | Global system-wide access across all bureaus & settings |
| **PGRC Bureau Officer** | `officer_pgrc` | `officer123` | Public Grievance Redressal Cell cases |
| **Regulation Bureau Officer**| `officer_rb` | `officer123` | Regulation Bureau cases |
| **Approval Bureau Officer** | `officer_ab` | `officer123` | Approval Bureau cases |
| **RB Supervisor** | `supervisor_rb` | `super123` | Regulation Bureau supervisor & Northern Region |
| **Compliance Auditor** | `auditor` | `auditor123` | Read-only compliance auditor |

*Quick 1-click login buttons are also available directly on the login landing page.*

---

## Running Automated Verification Tests

Execute the 33-test comprehensive verification suite covering all SIH26264 criteria:

```bash
cd backend
.venv/bin/pytest tests
```

To run frontend TypeScript type checking and production build:

```bash
cd frontend
npm run typecheck
npm run build
```

---

## End-to-End Judge Demonstration Sequence

Demonstrate the full lifecycle and smart automation to hackathon evaluators in 5 minutes:

1. **Sign in as `admin`:** View the **Single-Window Dashboard** with live metrics, overdue indicators, and active cross-bureau overlap banners.
2. **Inspect Institution 360° Profile:** Navigate to **Institutions**, select `1-10928374` (Apex Institute of Technology), and review its concurrent complaints across PGRC and Regulation Bureau.
3. **Inspect Active Overlap Alert:** Navigate to **Overlaps** to see the deterministic alert generated between `AICTE/2026/000001` (PGRC) and `AICTE/2026/000002` (RB).
4. **Verify Confidentiality Filtering:** Sign in as `officer_pgrc` and view the high-confidentiality whistleblower case `AICTE/2026/000003` in Regulation Bureau. Notice that category, narrative, complainant, and restricted remarks are masked at the API layer.
5. **Transfer & Acceptance:** Sign back in as `admin`, transfer the RB case to **Approval Bureau (AB)** with an official reason. Sign in as `officer_ab` to observe the pending transfer notification and click **Accept Transfer** to transition the case to `Under Process`.
6. **Demonstrate SLA Time Machine:** Use the top bar's `+30d` button to advance simulated time. Refresh the dashboard to witness active cases dynamically transition to `OVERDUE` (red badge).
7. **Dispose & Auto-Resolve Overlap:** From a case detail view, click **Dispose Case** with a resolution summary. Return to **Overlaps** to verify the paired overlap alert automatically transitions to `RESOLVED` with recorded audit notes.
8. **Export Safe CSV:** Navigate to **MIS Reports** to inspect bureau workload, disposal rates, and regional charts, then click **Export Safe CSV Report** to verify formula injection sanitization.
