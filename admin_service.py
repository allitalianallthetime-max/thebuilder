"""
admin_service.py — Anthony's Control Room
==========================================
Enterprise Admin Panel for The Builder.
Fully Thread-Safe. Tracks MRR, API Costs, and Customer Churn.
"""

import os
import secrets
import psycopg2
import psycopg2.pool
import httpx
import logging
import asyncio
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel
from contextlib import contextmanager
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ADMIN] %(levelname)s %(message)s")
log = logging.getLogger("admin")

app = FastAPI(title="The Builder - Control Room")

MASTER_KEY         = os.getenv("MASTER_KEY")
INTERNAL_API_KEY   = os.getenv("INTERNAL_API_KEY")
DATABASE_URL       = os.getenv("DATABASE_URL")

def normalize_url(raw: str, default: str) -> str:
    if not raw: return default
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return f"http://{raw}:10000"

# Internal Service URLs
AUTH_SERVICE_URL   = normalize_url(os.getenv("AUTH_SERVICE_URL", ""), "http://builder-auth:10000")
AI_SERVICE_URL     = normalize_url(os.getenv("AI_SERVICE_URL", ""),  "http://builder-ai:10000")
ANALYTICS_URL      = normalize_url(os.getenv("ANALYTICS_SERVICE_URL", ""), "http://builder-analytics:10000")

# ── 1. Thread-Safe Connection Pool ───────────────────────────────────────────
db_pool = None
try:
    db_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, DATABASE_URL)
    log.info("Database connection pool created (1-10 connections)")
except Exception as e:
    log.error(f"Failed to create connection pool: {e}")

@contextmanager
def get_db():
    conn = None
    try:
        if db_pool:
            conn = db_pool.getconn()
        else:
            conn = psycopg2.connect(DATABASE_URL)
        yield conn
    finally:
        if conn:
            if db_pool:
                db_pool.putconn(conn)
            else:
                conn.close()

def verify_master(x_master_key: str = Header(None)):
    """FastAPI Dependency: Constant-time comparison prevents timing attacks."""
    if not x_master_key or not MASTER_KEY or not secrets.compare_digest(x_master_key, MASTER_KEY):
        raise HTTPException(status_code=403, detail="Master badge required.")

HEADERS = {"X-Internal-Key": INTERNAL_API_KEY}

# ── Models ───────────────────────────────────────────────────────────────────
class RevokeRequest(BaseModel): license_key: str; reason: str = "Admin revoked"
class ExtendRequest(BaseModel): license_key: str; days: int = 30
class CreateLicenseRequest(BaseModel): email: str; name: str = "Builder"; tier: str = "pro"; days: int = 30; notes: str = "Admin created"

@app.get("/health")
def health():
    return {"status": "online", "service": "admin-control-room"}

# ── 2. The Profit Dashboard (SYNC / Thread-Safe) ─────────────────────────────
@app.get("/dashboard", dependencies=[Depends(verify_master)])
def get_dashboard():
    """Full system overview. Fast execution via FastAPI threadpool."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # License stats
            cur.execute("SELECT COUNT(*) FROM licenses WHERE status = 'active'")
            active_licenses = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM licenses WHERE status = 'active' AND expires_at < NOW() + INTERVAL '7 days'")
            expiring_soon = cur.fetchone()[0]

            # Build stats
            cur.execute("SELECT COUNT(*) FROM builds")
            total_builds = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM builds WHERE created_at > NOW() - INTERVAL '24 hours'")
            builds_today = cur.fetchone()[0]

            # Revenue estimate
            cur.execute("SELECT tier, COUNT(*) FROM licenses WHERE status = 'active' GROUP BY tier")
            tier_counts = dict(cur.fetchall())

            # Recent signups
            cur.execute("SELECT email, name, tier, created_at FROM licenses ORDER BY created_at DESC LIMIT 5")
            recent_signups = [{"email": r[0], "name": r[1], "tier": r[2], "joined": str(r[3])} for r in cur.fetchall()]

    # Financials (Assuming standard SaaS pricing)
    pricing   = {"starter": 29, "pro": 49, "master": 99}
    total_mrr = sum(pricing.get(t, 49) * c for t, c in tier_counts.items())
    
    # Cost Estimate: ~$0.05 per build across Gemini/Claude/Grok
    est_monthly_cost = builds_today * 30 * 0.05

    return {
        "licenses": {"active": active_licenses, "expiring_soon": expiring_soon, "by_tier": tier_counts},
        "builds": {"total": total_builds, "today": builds_today},
        "financials": {
            "estimated_mrr": f"${total_mrr:,.2f}",
            "est_api_costs_monthly": f"${est_monthly_cost:,.2f}",
            "gross_margin": f"${(total_mrr - est_monthly_cost):,.2f}",
            "by_tier": {t: f"${pricing.get(t,49) * c}" for t, c in tier_counts.items()}
        },
        "recent_signups": recent_signups,
        "generated_at": str(datetime.utcnow())
    }

@app.get("/users", dependencies=[Depends(verify_master)])
def get_all_users():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT l.license_key, l.email, l.name, l.status, l.tier,
                       l.expires_at, l.build_count, l.created_at,
                       (SELECT COUNT(*) FROM builds b WHERE b.user_email = l.email) as actual_builds
                FROM licenses l ORDER BY l.created_at DESC
            """)
            rows = cur.fetchall()
    return [{"license_key": r[0], "email": r[1], "name": r[2], "status": r[3], "tier": r[4], 
             "expires_at": str(r[5]), "build_count": r[6], "joined": str(r[7]), "actual_builds": r[8]} for r in rows]

@app.get("/builds/recent", dependencies=[Depends(verify_master)])
def get_recent_builds(limit: int = 20):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_email, project_type, junk_desc, created_at
                FROM builds ORDER BY created_at DESC LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
    return [{"id": r[0], "email": r[1], "type": r[2], "parts": r[3][:100], "created": str(r[4])} for r in rows]

@app.post("/licenses/revoke", dependencies=[Depends(verify_master)])
def revoke_license(req: RevokeRequest):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE licenses SET status = 'revoked', notes = %s WHERE license_key = %s", (req.reason, req.license_key))
            conn.commit()
    return {"status": "revoked", "license_key": req.license_key}

@app.post("/licenses/extend", dependencies=[Depends(verify_master)])
def extend_license(req: ExtendRequest):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE licenses SET expires_at = expires_at + (%s || ' days')::INTERVAL WHERE license_key = %s", (str(req.days), req.license_key))
            conn.commit()
    return {"status": "extended", "license_key": req.license_key, "days_added": req.days}

# ── 3. ASYNC HTTP ENDPOINTS (Talks to other services, safely async) ──────────
@app.post("/licenses/create", dependencies=[Depends(verify_master)])
async def create_license(req: CreateLicenseRequest):
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        resp = await client.post(f"{AUTH_SERVICE_URL}/auth/create", json=req.model_dump())
        resp.raise_for_status()
        return resp.json()

async def ping_service(client: httpx.AsyncClient, name: str, url: str):
    try:
        resp = await client.get(url, headers=HEADERS)
        return name, {"status": "online", "code": resp.status_code}
    except Exception as e:
        return name, {"status": "offline", "error": str(e)}

@app.get("/system/health", dependencies=[Depends(verify_master)])
async def check_all_services():
    services = {"auth": f"{AUTH_SERVICE_URL}/health", "ai": f"{AI_SERVICE_URL}/health", "analytics": f"{ANALYTICS_URL}/health"}
    results = {}
    async with httpx.AsyncClient(timeout=5) as client:
        tasks = [ping_service(client, name, url) for name, url in services.items()]
        results = dict(await asyncio.gather(*tasks))
    return {"services": results, "checked_at": str(datetime.utcnow())}
