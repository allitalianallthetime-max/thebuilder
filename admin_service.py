"""
admin_service.py — Anthony's Control Room
==========================================
Private admin panel for The Builder.
Only accessible with MASTER_KEY.

Endpoints:
- GET  /dashboard        — Full system overview
- GET  /users            — All users and licenses
- POST /licenses/revoke  — Revoke a license
- POST /licenses/extend  — Extend a license
- GET  /system/health    — All service health checks
- GET  /builds/recent    — Recent builds across all users
"""

import os
import psycopg2
import httpx
import logging
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from contextlib import contextmanager
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ADMIN] %(levelname)s %(message)s")
log = logging.getLogger("admin")

app = FastAPI()

MASTER_KEY         = os.getenv("MASTER_KEY")
INTERNAL_API_KEY   = os.getenv("INTERNAL_API_KEY")
DATABASE_URL       = os.getenv("DATABASE_URL")
AUTH_SERVICE_URL   = os.getenv("AUTH_SERVICE_URL")
AI_SERVICE_URL     = os.getenv("AI_SERVICE_URL")
ANALYTICS_URL      = os.getenv("ANALYTICS_SERVICE_URL", "http://builder-analytics:10000")

@contextmanager
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()

async def verify_master(x_master_key: str = Header(None)):
    if x_master_key != MASTER_KEY and x_master_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Master key required")

HEADERS = {"X-Internal-Key": INTERNAL_API_KEY}

class RevokeRequest(BaseModel):
    license_key: str
    reason:      str = "Admin revoked"

class ExtendRequest(BaseModel):
    license_key: str
    days:        int = 30

class CreateLicenseRequest(BaseModel):
    email: str
    name:  str = "Builder"
    tier:  str = "pro"
    days:  int = 30
    notes: str = "Admin created"

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "admin"}

@app.get("/dashboard")
async def get_dashboard(x_master_key: str = Header(None)):
    """Full admin dashboard — summary of everything."""
    await verify_master(x_master_key)

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

            cur.execute("SELECT COUNT(*) FROM builds WHERE created_at > NOW() - INTERVAL '7 days'")
            builds_week = cur.fetchone()[0]

            # Revenue estimate
            cur.execute("""
                SELECT tier, COUNT(*) FROM licenses
                WHERE status = 'active' GROUP BY tier
            """)
            tier_counts = dict(cur.fetchall())

            # Recent signups
            cur.execute("""
                SELECT email, name, tier, created_at
                FROM licenses ORDER BY created_at DESC LIMIT 5
            """)
            recent_signups = [
                {"email": r[0], "name": r[1], "tier": r[2], "joined": str(r[3])}
                for r in cur.fetchall()
            ]

    pricing   = {"starter": 29, "pro": 49, "master": 99}
    total_mrr = sum(pricing.get(t, 49) * c for t, c in tier_counts.items())

    return {
        "licenses": {
            "active":        active_licenses,
            "expiring_soon": expiring_soon,
            "by_tier":       tier_counts
        },
        "builds": {
            "total":       total_builds,
            "today":       builds_today,
            "this_week":   builds_week
        },
        "revenue": {
            "estimated_mrr": f"${total_mrr}",
            "by_tier":       {t: f"${pricing.get(t,49) * c}" for t, c in tier_counts.items()}
        },
        "recent_signups": recent_signups,
        "generated_at":   str(datetime.utcnow())
    }

@app.get("/users")
async def get_all_users(x_master_key: str = Header(None)):
    """All users with their license details."""
    await verify_master(x_master_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT l.license_key, l.email, l.name, l.status, l.tier,
                       l.expires_at, l.build_count, l.created_at,
                       COUNT(b.id) as actual_builds
                FROM licenses l
                LEFT JOIN builds b ON b.user_email = l.email
                GROUP BY l.license_key, l.email, l.name, l.status, l.tier,
                         l.expires_at, l.build_count, l.created_at
                ORDER BY l.created_at DESC
            """)
            rows = cur.fetchall()

    return [
        {
            "license_key":  r[0], "email": r[1], "name": r[2],
            "status":       r[3], "tier":  r[4],
            "expires_at":   str(r[5]),
            "build_count":  r[6], "joined": str(r[7]),
            "actual_builds": r[8]
        }
        for r in rows
    ]

@app.post("/licenses/revoke")
async def revoke_license(req: RevokeRequest, x_master_key: str = Header(None)):
    await verify_master(x_master_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE licenses SET status = 'revoked', notes = %s WHERE license_key = %s",
                (req.reason, req.license_key)
            )
            conn.commit()

    log.info(f"License revoked: {req.license_key} — {req.reason}")
    return {"status": "revoked", "license_key": req.license_key}

@app.post("/licenses/extend")
async def extend_license(req: ExtendRequest, x_master_key: str = Header(None)):
    await verify_master(x_master_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE licenses SET expires_at = expires_at + (%s || ' days')::INTERVAL WHERE license_key = %s",
                (str(req.days), req.license_key)
            )
            conn.commit()

    log.info(f"License extended: {req.license_key} by {req.days} days")
    return {"status": "extended", "license_key": req.license_key, "days_added": req.days}

@app.post("/licenses/create")
async def create_license(req: CreateLicenseRequest, x_master_key: str = Header(None)):
    """Admin creates a license manually (e.g. for comps or testing)."""
    await verify_master(x_master_key)

    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        resp = await client.post(
            f"{AUTH_SERVICE_URL}/auth/create",
            json={
                "email": req.email, "name": req.name,
                "tier":  req.tier,  "days": req.days,
                "notes": req.notes
            }
        )
        resp.raise_for_status()
        return resp.json()

@app.get("/builds/recent")
async def get_recent_builds(x_master_key: str = Header(None), limit: int = 20):
    await verify_master(x_master_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_email, project_type, junk_desc, created_at
                FROM builds ORDER BY created_at DESC LIMIT %s
            """, (limit,))
            rows = cur.fetchall()

    return [
        {
            "id":    r[0], "email": r[1], "type": r[2],
            "parts": r[3][:100], "created": str(r[4])
        }
        for r in rows
    ]

@app.get("/system/health")
async def check_all_services(x_master_key: str = Header(None)):
    """Ping all microservices and report their health."""
    await verify_master(x_master_key)

    services = {
        "auth":      f"{AUTH_SERVICE_URL}/health",
        "ai":        f"{AI_SERVICE_URL}/health",
        "analytics": f"{ANALYTICS_URL}/health",
    }

    results = {}
    async with httpx.AsyncClient(timeout=5) as client:
        for name, url in services.items():
            try:
                resp = await client.get(url, headers=HEADERS)
                results[name] = {"status": "online", "code": resp.status_code}
            except Exception as e:
                results[name] = {"status": "offline", "error": str(e)}

    return {"services": results, "checked_at": str(datetime.utcnow())}
