"""
analytics_service.py — The Logbook
=====================================
Tracks all usage data, popular builds, revenue,
and system performance metrics.

Endpoints:
- GET  /stats/overview       — Dashboard summary
- GET  /stats/builds         — Build analytics
- GET  /stats/revenue        — Revenue metrics
- GET  /stats/popular-parts  — Most submitted parts
- POST /track/event          — Log a custom event
"""

import os
import secrets
import psycopg2
import psycopg2.pool
import logging
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from contextlib import contextmanager
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Optional
import json

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ANALYTICS] %(levelname)s %(message)s")
log = logging.getLogger("analytics")

app = FastAPI()

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
DATABASE_URL     = os.getenv("DATABASE_URL")

# ── 2.5: Connection Pool (prevents exhaustion under load) ────────────────────
db_pool = None
try:
    db_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, DATABASE_URL)
    log.info("Database connection pool created (1-10 connections)")
except Exception as e:
    log.error(f"Failed to create connection pool: {e}")

@contextmanager
def get_db():
    """Get a connection from the pool, auto-return on exit."""
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

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id         SERIAL PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    user_email TEXT,
                    metadata   JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()

try:
    init_db()
except Exception as e:
    log.warning(f"DB Init: {e}")

class EventRequest(BaseModel):
    event_type: str
    user_email: str = "anonymous"
    metadata:   dict = {}

async def verify(x_internal_key: str = Header(None)):
    if not x_internal_key or not INTERNAL_API_KEY or \
       not secrets.compare_digest(x_internal_key, INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Unauthorized")

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/track/event")
async def track_event(req: EventRequest, x_internal_key: str = Header(None)):
    await verify(x_internal_key)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO events (event_type, user_email, metadata) VALUES (%s, %s, %s)",
                (req.event_type, req.user_email, json.dumps(req.metadata))
            )
            conn.commit()
    return {"status": "tracked"}

@app.get("/stats/overview")
async def get_overview(x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            # Total builds
            cur.execute("SELECT COUNT(*) FROM builds")
            total_builds = cur.fetchone()[0]

            # Builds today
            cur.execute("SELECT COUNT(*) FROM builds WHERE created_at > NOW() - INTERVAL '24 hours'")
            builds_today = cur.fetchone()[0]

            # Builds this week
            cur.execute("SELECT COUNT(*) FROM builds WHERE created_at > NOW() - INTERVAL '7 days'")
            builds_week = cur.fetchone()[0]

            # Total active licenses
            cur.execute("SELECT COUNT(*) FROM licenses WHERE status = 'active'")
            active_licenses = cur.fetchone()[0]

            # Most popular project type
            cur.execute("""
                SELECT project_type, COUNT(*) as cnt
                FROM builds GROUP BY project_type
                ORDER BY cnt DESC LIMIT 1
            """)
            top_row = cur.fetchone()
            top_build = top_row[0] if top_row else "N/A"

    return {
        "total_builds":    total_builds,
        "builds_today":    builds_today,
        "builds_this_week": builds_week,
        "active_licenses": active_licenses,
        "top_build_type":  top_build,
        "generated_at":    str(datetime.utcnow())
    }

@app.get("/stats/builds")
async def get_build_stats(x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            # By project type
            cur.execute("""
                SELECT project_type, COUNT(*) as count
                FROM builds GROUP BY project_type ORDER BY count DESC
            """)
            by_type = [{"type": r[0], "count": r[1]} for r in cur.fetchall()]

            # By day last 30 days
            cur.execute("""
                SELECT DATE(created_at) as day, COUNT(*) as count
                FROM builds WHERE created_at > NOW() - INTERVAL '30 days'
                GROUP BY day ORDER BY day
            """)
            by_day = [{"day": str(r[0]), "count": r[1]} for r in cur.fetchall()]

    return {"by_type": by_type, "by_day": by_day}

@app.get("/stats/popular-parts")
async def get_popular_parts(x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    # Common industrial/medical equipment keywords to track
    keywords = [
        "x-ray", "mri", "anesthesia", "diesel", "hydraulic",
        "servo", "motor", "pump", "compressor", "generator",
        "robot", "arm", "chassis", "frame", "plate"
    ]

    with get_db() as conn:
        with conn.cursor() as cur:
            results = []
            for kw in keywords:
                cur.execute(
                    "SELECT COUNT(*) FROM builds WHERE LOWER(junk_desc) LIKE %s",
                    (f"%{kw}%",)
                )
                count = cur.fetchone()[0]
                if count > 0:
                    results.append({"keyword": kw, "count": count})

    results.sort(key=lambda x: x["count"], reverse=True)
    return {"popular_parts": results}

@app.get("/stats/revenue")
async def get_revenue_stats(x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tier, COUNT(*) as count
                FROM licenses WHERE status = 'active'
                GROUP BY tier
            """)
            by_tier = cur.fetchall()

    pricing = {"starter": 29, "pro": 49, "master": 99}
    revenue_data = []
    total_mrr = 0

    for tier, count in by_tier:
        price = pricing.get(tier, 49)
        mrr   = price * count
        total_mrr += mrr
        revenue_data.append({
            "tier":  tier,
            "count": count,
            "price": f"${price}",
            "mrr":   f"${mrr}"
        })

    return {
        "tiers":     revenue_data,
        "total_mrr": f"${total_mrr}",
        "generated": str(datetime.utcnow())
    }
