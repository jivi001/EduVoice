# Deploying EduVoice (GitHub + Vercel + Supabase)

EduVoice is architected as two applications in a single monorepo deployed to **Vercel** with a managed **Supabase PostgreSQL** database.

```
Browser ──► Vercel Project 1: Frontend (Next.js)
                 │  /api/* is proxied via rewrites to
                 ▼
            Vercel Project 2: Backend (FastAPI ASGI) ──► Supabase PostgreSQL (Project hjowkdcdrrzedamodluq)
```

Target Vercel Domains:
- **Frontend**: `https://eduvoice-frontend.vercel.app/`
- **Backend**: `https://eduvoice-backend.vercel.app/`

---

## 1. Supabase Database Configuration

The database schema and initial seed data for EduVoice have already been provisioned via Supabase MCP on project `hjowkdcdrrzedamodluq`:
- **Project Ref**: `hjowkdcdrrzedamodluq`
- **Supabase URL**: `https://hjowkdcdrrzedamodluq.supabase.co`
- **Tables Provisioned**: 23 core relational tables (`complaint_cases`, `case_histories`, `case_relationships`, `institutions`, `bureaus`, `users`, `notifications`, `sla_configs`, etc.).

### Connection String Options
In your Supabase project dashboard (**Settings → Database → Connection string**):
- **Transaction Pooler (Supavisor - Port 6543, recommended for Vercel Serverless)**:
  ```
  postgresql://postgres.[project-ref]:[DB-PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require
  ```
- **Direct Connection (Port 5432)**:
  ```
  postgresql://postgres:[DB-PASSWORD]@db.hjowkdcdrrzedamodluq.supabase.co:5432/postgres?sslmode=require
  ```

> [!NOTE]
> EduVoice's database engine in `backend/app/db.py` is configured with `poolclass=NullPool` and `prepare_threshold=None`, making it natively compatible with Supabase's Supavisor transaction pooler on port 6543.
> Additionally, `backend/app/config.py` automatically detects `POSTGRES_URL` or `POSTGRES_PRISMA_URL` injected by the Vercel-Supabase integration.

---

## 2. Deploy the Backend (Vercel Project: eduvoice-backend)

1. Open your [Vercel Dashboard](https://vercel.com/dashboard) and click **Add New → Project**.
2. Select your repository: `jivi001/EduVoice`.
3. Configure the project:
   - **Project Name**: `eduvoice-backend` (will deploy to `https://eduvoice-backend.vercel.app`)
   - **Framework Preset**: Other
   - **Root Directory**: Click "Edit" and choose `backend`
4. Set **Environment Variables**:

| Variable | Value | Description |
|---|---|---|
| `ENVIRONMENT` | `production` | Enables production security checks |
| `DATABASE_URL` | `postgresql://postgres.[project-ref]:[pass]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require` | Supabase Transaction Pooler URL (or link Supabase Integration for auto `POSTGRES_URL`) |
| `JWT_SECRET` | *(64-char random string)* | Run `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `SIGNING_KEY_PEM_B64` | *(Base64 Ed25519 key)* | Run `python -m app.bootstrap genkey` in `backend/` |
| `COOKIE_SECURE` | `true` | Required for HTTPS cookies in production |
| `FRONTEND_ORIGIN` | `https://eduvoice-frontend.vercel.app` | Allow frontend origin for CORS and session cookies |
| `AICTE_CROSS_BUREAU_ENABLED` | `true` | Enables AICTE cross-bureau overlap detection & tracking |
| `AICTE_SLA_DAYS_DEFAULT` | `30` | Default SLA disposal window |

5. Click **Deploy**.
6. Verify deployment by checking:
   ```bash
   curl https://eduvoice-backend.vercel.app/health
   # Expected response: {"status":"ok"}
   ```

> [!TIP]
> If Vercel prompts with "Authentication Required" when visiting `/health`, go to **Settings → Deployment Protection** in the Vercel project and toggle it **Off** or allow public traffic.

---

## 3. Deploy the Frontend (Vercel Project: eduvoice-frontend)

1. In the Vercel Dashboard, click **Add New → Project**.
2. Select the same repository: `jivi001/EduVoice`.
3. Configure the project:
   - **Project Name**: `eduvoice-frontend` (will deploy to `https://eduvoice-frontend.vercel.app`)
   - **Framework Preset**: Next.js
   - **Root Directory**: Click "Edit" and choose `frontend`
4. Set **Environment Variables**:

| Variable | Value | Description |
|---|---|---|
| `BACKEND_URL` | `https://eduvoice-backend.vercel.app` | Backend target for `/api/*` rewrite proxies |
| `NEXT_PUBLIC_APP_NAME` | `EduVoice` | System branding |

5. Click **Deploy**.
6. Open `https://eduvoice-frontend.vercel.app/` in your browser. All API requests made to `/api/*` will automatically proxy to `https://eduvoice-backend.vercel.app/` while maintaining same-site secure cookie isolation.

---

## 4. Supabase Vercel Integration (Alternative / One-Click Linking)

If you prefer using Vercel's native Supabase integration:
1. In the `eduvoice-backend` project on Vercel, navigate to the **Integrations** tab.
2. Search for **Supabase** and click **Add Integration**.
3. Select your Supabase project: `hjowkdcdrrzedamodluq`.
4. Vercel will automatically inject `POSTGRES_URL`, `POSTGRES_PRISMA_URL`, and `POSTGRES_URL_NON_POOLING`.
5. EduVoice automatically parses these environment variables without requiring any code modifications.

---

## 5. Seed Accounts & Default Credentials

The Supabase database has been seeded with standard AICTE demonstration roles for evaluation:

| Role | Username | Initial Password | Bureau / Jurisdiction |
|---|---|---|---|
| **Central Admin** | `admin` | `Admin@123456` | All Bureaus / National |
| **PGRC Officer** | `officer_pgrc` | `Officer@123456` | Public Grievance Redressal Cell (PGRC) |
| **Approval Bureau Officer** | `officer_ab` | `Officer@123456` | Approval Bureau (AB) |
| **Regional Officer** | `officer_rb` | `Officer@123456` | Regional Bureau (RB) |
| **Regional Supervisor** | `supervisor_rb` | `Supervisor@123456` | Regional Bureau (RB - Northern Region) |
| **Read-Only Auditor** | `auditor` | `Auditor@123456` | Read-only oversight |
| **Student** | `student_01` | `Student@123456` | Anonymous feedback & complaint portal |

> [!IMPORTANT]
> When transitioning to full production, rotate default passwords and update `ADMIN_PASSWORD` via `python -m app.bootstrap init` or through the EduVoice Admin panel.
