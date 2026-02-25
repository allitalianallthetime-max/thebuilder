<p align="center">
  <img src="https://img.shields.io/badge/PYTHON-3.11-ff6600?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/STREAMLIT-1.x-ff6600?style=for-the-badge&logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/FASTAPI-0.100+-ff6600?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/POSTGRESQL-15-ff6600?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/RENDER-DEPLOYED-00cc66?style=for-the-badge&logo=render&logoColor=white" />
</p>

<h1 align="center">⚙️ THE BUILDER</h1>
<h3 align="center">AI-Powered Engineering Forge</h3>

<p align="center">
  <strong>AoC3P0 Systems</strong> · Est. 2024 · All Rights Reserved
</p>

<p align="center">
  <em>"Where AI logic meets heavy metal."</em>
</p>

---

Why settle for **one AI** when you can have a **Board of Directors?**

The Builder puts **Gemini, Grok, and Claude** in the same room to tackle your toughest engineering challenges. Upload a photo of junk equipment, let AI identify it down to every bolt, then forge a tiered blueprint with three AI models collaborating as a Round Table of elite engineers.

Whether we're repurposing **medical X-ray machines for armor plating** or engineering **off-road chassis for 500hp builds**, the Round Table logic ensures every bolt and wire is accounted for.

**It's not just a program — it's an automated engineering department.**

---

## 🔥 What It Does

| Feature | Description |
|---|---|
| **🔬 X-Ray Scanner** | Upload a photo of any equipment. Gemini Vision identifies it, maps internal schematics, tears down every component, assesses hazards, estimates salvage value, and suggests what it could become. |
| **⚡ Round Table AI** | Three AI models collaborate on every build. Grok handles mechanical logic, Claude designs control systems and code, Gemini synthesizes the final tiered blueprint. |
| **🔩 Workshop Manager** | Phase-gated project tracking with AI-generated tasks, parts checklists, safety gates, and build logging. Takes a blueprint from concept to completion. |
| **📸 Photo → Blueprint Pipeline** | Snap a photo → AI identifies equipment → extract components → forge blueprint → track build. End-to-end automation. |
| **📄 Export** | Download blueprints as styled PDF or plain text. |
| **💳 Stripe Billing** | Tiered subscription plans with automated license provisioning and welcome emails. |
| **🔐 License System** | JWT-based auth, auto-generated license keys, expiry management, admin controls. |
| **📊 Analytics** | Build stats, popular parts tracking, revenue metrics, usage trends. |
| **🗓 Scheduler** | Daily cron job handles license lifecycle, expiry warnings, email queue processing, and data cleanup. |

---

## 🏗 Architecture

The Builder is a **microservice architecture** with 8 services, 1 database, and a cron worker — all deployed to [Render](https://render.com) via Infrastructure-as-Code.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        THE BUILDER — AoC3P0 Systems                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐       │
│   │  🖥 DASHBOARD │────▶│ ⚡ AI ENGINE  │────▶│  🔬 SCANNER  │       │
│   │  (Streamlit)  │     │ (Round Table)│     │ (Gemini Vis) │       │
│   │   app.py      │     │ ai_service   │     │              │       │
│   └──────┬───────┘     └──────────────┘     │ workshop_    │       │
│          │                                    │ service      │       │
│          │              ┌──────────────┐     └──────────────┘       │
│          ├─────────────▶│  🛡 AUTH      │                            │
│          │              │ (Licenses/JWT)│                            │
│          │              │ auth_service  │                            │
│          │              └──────┬───────┘                            │
│          │                     │                                     │
│          │              ┌──────┴───────┐                            │
│          ├─────────────▶│  💳 BILLING   │                            │
│          │              │ (Stripe)      │                            │
│          │              │ billing_svc   │                            │
│          │              └──────────────┘                            │
│          │                                                          │
│          │              ┌──────────────┐     ┌──────────────┐       │
│          ├─────────────▶│  📊 ANALYTICS │     │  🔐 ADMIN    │       │
│          │              │ analytics_svc │     │ admin_service │      │
│          │              └──────────────┘     └──────────────┘       │
│          │                                                          │
│          │              ┌──────────────┐     ┌──────────────┐       │
│          └─────────────▶│  📄 EXPORT    │     │  🗓 SCHEDULER │       │
│                         │ export_svc    │     │ (Daily Cron) │       │
│                         └──────────────┘     └──────────────┘       │
│                                                                     │
│                         ┌──────────────┐                            │
│                         │  🗄 POSTGRES  │  ◀── All services         │
│                         │   builder-db  │                            │
│                         └──────────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Services

| # | Service | File | Role | Endpoints |
|---|---------|------|------|-----------|
| 1 | `builder-ui` | `app.py` | Streamlit dashboard — all tabs, styling, routing | — |
| 2 | `builder-ai` | `ai_service.py` | Round Table AI engine (Grok + Claude + Gemini) | 4 |
| 3 | `builder-auth` | `auth_service.py` | License verification, JWT issuance, user management | 9 |
| 4 | `builder-billing` | `billing_service.py` | Stripe webhooks, checkout, license provisioning | 4 |
| 5 | `builder-analytics` | `analytics_service.py` | Usage stats, build analytics, revenue metrics | 6 |
| 6 | `builder-admin` | `admin_service.py` | Admin dashboard, license CRUD, system health | 8 |
| 7 | `builder-export` | `export_service.py` | PDF and text blueprint export | 3 |
| 8 | `builder-workshop` | `workshop_service.py` | Workshop projects, X-Ray Scanner, parts intelligence | 19 |
| — | `scheduler` | `scheduler_worker.py` | Daily cron: license lifecycle, emails, cleanup | — |

**Total: 53 API endpoints across 7 FastAPI services**

---

## 🔬 X-Ray Scanner — How It Works

The X-Ray Scanner uses **Gemini 2.0 Flash Vision** to perform forensic-level equipment analysis from a single photo.

### The Pipeline

```
📸 Upload Photo
       │
       ▼
🔬 Gemini Vision Analysis (~15-30s)
       │
       ├──▶ Equipment Identification (manufacturer, model, year, category)
       ├──▶ Internal Schematic Mapping (power, control, fluid, mechanical systems)
       ├──▶ ASCII Electrical Diagrams
       ├──▶ Full Component Teardown (name, location, specs, condition, salvage $)
       ├──▶ Specification Extraction (voltage, pressure, dimensions, weight)
       ├──▶ Hazard Assessment (materials, PPE, lockout/tagout, disposal)
       ├──▶ Salvage Valuation (per-component + total + scrap metal)
       └──▶ Build Potential (3+ repurposing ideas)
       │
       ▼
┌─────────────────────────────────────┐
│  📋 Send to Workbench               │  ← Auto-fills New Build form
│  🔩 Send to Workshop                │  ← Creates tracked project
│  🔥 Forge Blueprint (Round Table)   │  ← 3 AIs collaborate on the build
└─────────────────────────────────────┘
```

### What Gets Identified

- **Equipment**: Name, manufacturer, model, year/era, original purpose, common aliases
- **Schematics**: System overview, power distribution, control systems, fluid systems, mechanical systems, signal chains, ASCII electrical diagrams
- **Components**: Every salvageable part with category, location, specifications, condition assessment, salvage value, and reuse potential (high/medium/low)
- **Specifications**: Input voltage, power consumption, dimensions, weight, operating pressure, flow rates
- **Hazards**: Hazard level (none → critical), specific warnings, required PPE, lockout/tagout procedures, disposal requirements
- **Salvage**: Total estimated value, high-value components, scrap metal value, teardown difficulty (1-10), estimated hours, required tools, recommended teardown strategy

---

## ⚡ The Round Table — AI Collaboration

Every blueprint is built by three AI models working in sequence:

```
┌─────────────────────┐
│  ⚡ GROK             │  Step 1: The Shop Foreman
│  (xAI)               │  Mechanical analysis, torque specs,
│                      │  structural integrity, drive systems
└──────────┬──────────┘
           │ feeds into
           ▼
┌─────────────────────┐
│  🤖 CLAUDE           │  Step 2: The Precision Engineer
│  (Anthropic)         │  Control systems, Python code,
│                      │  wiring diagrams, safety interlocks
└──────────┬──────────┘
           │ feeds into
           ▼
┌─────────────────────┐
│  🔵 GEMINI           │  Step 3: The General Contractor
│  (Google)            │  Synthesizes all inputs into a
│                      │  tiered blueprint (Novice/Journey/Master)
└─────────────────────┘
```

**Output Format**: Every blueprint includes Novice Tier (basic build), Journeyman Tier (enhanced), Master Tier (full integration), Parts Manifest, and Safety Protocols.

---

## 🔩 Workshop — Project Management

The Workshop turns blueprints into tracked, phase-gated build projects.

### Six Build Phases

```
📐 PLANNING ──▶ 🔥 FABRICATION ──▶ 🔩 ASSEMBLY ──▶ ⚡ ELECTRICAL ──▶ 🧪 TESTING ──▶ 🏆 COMPLETE
```

Each phase has:
- **AI-generated tasks** specific to the build
- **Safety checkpoint tasks** that must be completed before advancing
- **Safety gates** requiring explicit confirmation (e.g., "All welds inspected, measurements verified")
- **Parts checklist** with status tracking (needed → sourced → installed)
- **Build log** for notes, observations, and safety warnings

---

## 📁 File Structure

```
the-builder/
├── app.py                    # 1,704 lines — Streamlit UI dashboard
├── ai_service.py             #   351 lines — Round Table AI engine
├── auth_service.py           #   356 lines — License/JWT auth
├── billing_service.py        #   230 lines — Stripe billing
├── analytics_service.py      #   208 lines — Usage analytics
├── admin_service.py          #   261 lines — Admin control room
├── export_service.py         #   202 lines — PDF/text export
├── workshop_service.py       # 1,313 lines — Workshop + X-Ray Scanner
├── scheduler_worker.py       #   228 lines — Daily cron worker
├── builder_styles.py         #   737 lines — CSS theme system
├── key_manager.py            #   229 lines — (Legacy render config)
├── render.yaml               #   187 lines — Render IaC deployment
├── requirements-services.txt #    17 lines — FastAPI service deps
├── requirements-ui.txt       #     7 lines — Streamlit UI deps
├── CHANGELOG.md              #            — Version history
└── README.md                 #            — This file
```

**Total: ~6,000 lines of Python + YAML across 15 files**

---

## 🗄 Database Schema

Single PostgreSQL 15 instance shared by all services.

```sql
── builds ──────────────────────────────────────
id, user_email, junk_desc, project_type, blueprint,
grok_notes, claude_notes, tokens_used, created_at

── licenses ────────────────────────────────────
id, license_key, email, name, stripe_customer_id,
status, tier, expires_at, build_count, notes, created_at

── notification_queue ──────────────────────────
id, type, to_email, name, payload (JSONB),
status, created_at

── events ──────────────────────────────────────
id, event_type, user_email, metadata (JSONB), created_at

── workshop_projects ───────────────────────────
id, build_id (FK→builds), user_email, title, project_type,
junk_desc, current_phase, difficulty, est_hours, est_cost,
status, created_at, updated_at

── workshop_tasks ──────────────────────────────
id, project_id (FK→projects), phase, title, description,
is_complete, is_safety, sort_order, completed_at, created_at

── workshop_parts ──────────────────────────────
id, project_id (FK→projects), name, category, source,
quantity, status, est_value, notes, created_at

── workshop_notes ──────────────────────────────
id, project_id (FK→projects), phase, content,
note_type, created_at

── equipment_scans ─────────────────────────────
id, user_email, image_hash, equipment_name, manufacturer,
model, year_range, category, scan_result (JSONB),
parts_found, est_salvage, hazard_level, status, created_at
```

---

## 🚀 Deployment — Render (One Click)

The Builder deploys to [Render](https://render.com) using the `render.yaml` Infrastructure-as-Code blueprint.

### Prerequisites

You'll need API keys for:

| Key | Source | Used By |
|-----|--------|---------|
| `XAI_API_KEY` | [x.ai](https://x.ai) | Grok (Shop Foreman) |
| `ANTHROPIC_API_KEY` | [anthropic.com](https://www.anthropic.com) | Claude (Precision Engineer) |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | Gemini (General Contractor + X-Ray Scanner) |
| `STRIPE_SECRET_KEY` | [stripe.com](https://stripe.com) | Billing |
| `STRIPE_WEBHOOK_SEC` | Stripe Dashboard → Webhooks | Webhook verification |
| `MASTER_KEY` | You choose | Admin access |
| `RESEND_API_KEY` | [resend.com](https://resend.com) (optional) | Email notifications |

### Deploy Steps

1. **Fork this repo** to your GitHub account

2. **Go to [Render Dashboard](https://dashboard.render.com)** → New → Blueprint

3. **Connect your repo** and select it

4. **Render reads `render.yaml`** and creates all 8 services + database automatically

5. **Set environment variables** — Render will prompt you for all `sync: false` keys:
   - `MASTER_KEY` — your admin password
   - `XAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` — AI model keys
   - `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SEC` — Stripe keys
   - `STRIPE_PAYMENT_URL` — your Stripe payment link
   - `APP_URL` — your `builder-ui` URL after deploy

6. **Deploy** — Render provisions everything. First deploy takes ~5 minutes.

7. **(Optional) Add Cron Job** — Create a Render Cron Job:
   - Command: `python scheduler_worker.py`
   - Schedule: `0 8 * * *` (daily at 8am UTC)
   - Set `AUTH_SERVICE_URL`, `INTERNAL_API_KEY`, `RESEND_API_KEY`, `FROM_EMAIL`

### What Render Creates

| Resource | Type | Plan |
|----------|------|------|
| `builder-ui` | Web Service | Starter |
| `builder-ai` | Web Service | Starter |
| `builder-auth` | Web Service | Starter |
| `builder-billing` | Web Service | Starter |
| `builder-analytics` | Web Service | Starter |
| `builder-admin` | Web Service | Starter |
| `builder-export` | Web Service | Starter |
| `builder-workshop` | Web Service | Starter |
| `builder-db` | PostgreSQL | Basic |

---

## 🖥 Local Development

### Requirements

- Python 3.11+
- PostgreSQL 15+
- API keys (see above)

### Setup

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/the-builder.git
cd the-builder

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements-ui.txt
pip install -r requirements-services.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys and DATABASE_URL
```

### `.env` Template

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/builder

# AI Keys
XAI_API_KEY=xai-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AI...

# Internal Security
INTERNAL_API_KEY=any-random-string-here
MASTER_KEY=your-admin-password
JWT_SECRET=another-random-string

# Stripe (optional for local dev)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SEC=whsec_...

# Service URLs (local)
AUTH_SERVICE_URL=http://localhost:8001
AI_SERVICE_URL=http://localhost:8002
BILLING_SERVICE_URL=http://localhost:8003
ANALYTICS_SERVICE_URL=http://localhost:8004
ADMIN_SERVICE_URL=http://localhost:8005
EXPORT_SERVICE_URL=http://localhost:8006
WORKSHOP_SERVICE_URL=http://localhost:8007
```

### Run Locally

Open separate terminals for each service:

```bash
# Terminal 1 — Auth
uvicorn auth_service:app --host 0.0.0.0 --port 8001

# Terminal 2 — AI Engine
uvicorn ai_service:app --host 0.0.0.0 --port 8002

# Terminal 3 — Billing
uvicorn billing_service:app --host 0.0.0.0 --port 8003

# Terminal 4 — Analytics
uvicorn analytics_service:app --host 0.0.0.0 --port 8004

# Terminal 5 — Admin
uvicorn admin_service:app --host 0.0.0.0 --port 8005

# Terminal 6 — Export
uvicorn export_service:app --host 0.0.0.0 --port 8006

# Terminal 7 — Workshop + Scanner
uvicorn workshop_service:app --host 0.0.0.0 --port 8007

# Terminal 8 — UI (start last)
streamlit run app.py
```

Or run with a process manager like `honcho` / `foreman` with a `Procfile`.

---

## 💳 Subscription Tiers

| Plan | Price | Builds/mo | Features |
|------|-------|-----------|----------|
| **Starter** | $29/mo | 25 | Basic Round Table access |
| **Pro** | $49/mo | 100 | Full Round Table, priority processing |
| **Master** | $99/mo | Unlimited | All AI models, API access, white label |

Billing is handled by Stripe. When a payment completes, the webhook automatically provisions a license key, sends a welcome email, and activates the account.

---

## 🔒 Security

- **Internal API Key** — All service-to-service communication is authenticated with a shared `INTERNAL_API_KEY` header
- **Master Key** — Admin access requires a separate `MASTER_KEY`
- **JWT Tokens** — License verification issues short-lived JWT badges (24hr expiry)
- **License Keys** — Format: `BUILDER-XXXX-XXXX-XXXX`, cryptographically generated
- **Stripe Signature Verification** — Webhooks are verified using Stripe's signing secret
- **No public endpoints** — Every endpoint (except `/health` and `/plans`) requires authentication

---

## 📡 API Reference

<details>
<summary><strong>AI Engine</strong> — <code>ai_service.py</code></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/generate` | Generate a Round Table blueprint |
| `GET` | `/builds` | List all builds |
| `GET` | `/builds/{id}` | Get build detail |
| `GET` | `/health` | Health check |

</details>

<details>
<summary><strong>Auth</strong> — <code>auth_service.py</code></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/verify-license` | Verify license key, issue JWT |
| `POST` | `/auth/create` | Create new license |
| `POST` | `/notify/queue` | Queue email notification |
| `GET` | `/notify/pending` | Get pending notifications |
| `POST` | `/notify/mark-sent/{id}` | Mark notification sent |
| `GET` | `/admin/licenses` | List all licenses |
| `GET` | `/admin/licenses/{key}` | Get license detail |
| `DELETE` | `/auth/history/{key}` | Soft-delete license |
| `GET` | `/health` | Health check |

</details>

<details>
<summary><strong>Billing</strong> — <code>billing_service.py</code></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/webhook` | Stripe webhook receiver |
| `GET` | `/plans` | Get pricing plans |
| `POST` | `/create-checkout` | Create Stripe checkout session |
| `GET` | `/health` | Health check |

</details>

<details>
<summary><strong>Analytics</strong> — <code>analytics_service.py</code></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/stats/overview` | Dashboard summary |
| `GET` | `/stats/builds` | Build analytics by type/day |
| `GET` | `/stats/revenue` | Revenue by tier |
| `GET` | `/stats/popular-parts` | Most submitted parts |
| `POST` | `/track/event` | Log custom event |
| `GET` | `/health` | Health check |

</details>

<details>
<summary><strong>Admin</strong> — <code>admin_service.py</code></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/dashboard` | Full admin overview |
| `GET` | `/users` | All users with license details |
| `POST` | `/licenses/create` | Admin create license |
| `POST` | `/licenses/extend` | Extend license expiry |
| `POST` | `/licenses/revoke` | Revoke a license |
| `GET` | `/builds/recent` | Recent builds across users |
| `GET` | `/system/health` | Ping all services |
| `GET` | `/health` | Health check |

</details>

<details>
<summary><strong>Export</strong> — <code>export_service.py</code></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/export/pdf` | Generate styled PDF |
| `POST` | `/export/text` | Generate plain text |
| `GET` | `/health` | Health check |

</details>

<details>
<summary><strong>Workshop + Scanner</strong> — <code>workshop_service.py</code></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/projects/create` | Create project with AI analysis |
| `GET` | `/projects` | List all projects |
| `GET` | `/projects/{id}` | Full project detail |
| `PATCH` | `/projects/{id}/phase` | Advance phase (safety gate) |
| `DELETE` | `/projects/{id}` | Archive project |
| `GET` | `/projects/{id}/tasks` | Task list |
| `PATCH` | `/projects/{id}/tasks/{tid}` | Toggle task completion |
| `POST` | `/projects/{id}/tasks` | Add custom task |
| `POST` | `/projects/{id}/notes` | Add build log entry |
| `POST` | `/parts/analyze` | AI parts analysis |
| `GET` | `/projects/{id}/parts` | Parts checklist |
| `PATCH` | `/projects/{id}/parts/{pid}` | Update part status |
| `GET` | `/workshop/stats` | Workshop statistics |
| `POST` | `/scan/upload` | Upload image for X-Ray scan |
| `POST` | `/scan/base64` | Scan base64 image |
| `GET` | `/scans` | List all scans |
| `GET` | `/scans/{id}` | Full scan detail |
| `POST` | `/scans/{id}/to-workbench` | Convert scan to workbench text |
| `GET` | `/health` | Health check |

</details>

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Streamlit, custom CSS/HTML |
| **Backend** | FastAPI, Uvicorn |
| **AI Models** | Google Gemini 2.0 Flash (vision + text), xAI Grok, Anthropic Claude |
| **Database** | PostgreSQL 15 |
| **Payments** | Stripe (Checkout Sessions + Webhooks) |
| **Auth** | PyJWT, SHA-256 hashing |
| **Email** | Resend API |
| **HTTP** | httpx (async) |
| **Deployment** | Render (IaC via render.yaml) |
| **Export** | ReportLab (PDF generation) |

---

## 🗺 Roadmap

- [ ] Image gallery — store uploaded scan photos alongside results
- [ ] Multi-image scanning — upload multiple angles of the same equipment
- [ ] Parts marketplace — buy/sell identified components
- [ ] 3D model generation from schematics
- [ ] Mobile app (React Native)
- [ ] Real-time collaboration on workshop projects
- [ ] Integration with parts suppliers (McMaster-Carr, Grainger)
- [ ] Cost tracking with actual vs. estimated spend
- [ ] Build templates — save and share common project types
- [ ] Conception AI integration

---

## 📜 License

**Proprietary** — AoC3P0 Systems · All Rights Reserved

This software is the property of AoC3P0 Systems. Unauthorized copying, distribution, or modification is prohibited. Contact AoC3P0 Systems for licensing inquiries.

---

<p align="center">
  <strong>Built by Anthony · Powered by AoC3P0 Systems · 2024-2026</strong><br>
  <em>Junk in. Robots out. ⚙️</em>
</p>
