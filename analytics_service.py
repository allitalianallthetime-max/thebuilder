"""
analytics_service.py — The Logbook
=====================================
High-performance asynchronous data tracking using FastAPI BackgroundTasks.
"""

import os
import secrets
import psycopg2
import psycopg2.pool
import logging
import json
from fastapi import FastAPI, Header, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from contextlib import contextmanager
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ANALYTICS] %(levelname)s %(message)s")
log = logging.getLogger("analytics")

app = FastAPI(title="The Builder - Analytics")

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
DATABASE_URL     = os.getenv("DATABASE_URL")

db_pool = psycopg2.pool.ThreadedConnectionPool(1, 15, DATABASE_URL)

@contextmanager
def get_db():
    conn = db_pool.getconn()
    try: yield conn
    finally: db_pool.putconn(conn)

class EventRequest(BaseModel):
    event_type: str
    user_email: str = "anonymous"
    metadata:   dict = {}

def verify_internal(x_internal_key: str = Header(None)):
    if not x_internal_key or not secrets.compare_digest(x_internal_key, INTERNAL_API_KEY):
        raise HTTPException(status_code=403)

@app.get("/health")
def health(): return {"status": "healthy"}

# ── 1. Ultra-Fast Background Event Tracking ──────────────────────────────────
def save_event_to_db(event_type: str, user_email: str, metadata: dict):
    """Executes silently in the background."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO events (event_type, user_email, metadata) VALUES (%s, %s, %s)",
                    (event_type, user_email, json.dumps(metadata))
                )
                conn.commit()
    except Exception as e:
        log.error(f"Event tracking failed: {e}")

@app.post("/track/event", dependencies=[Depends(verify_internal)])
def track_event(req: EventRequest, background_tasks: BackgroundTasks):
    """
    FastAPI immediately returns 200 OK to the UI, 
    and saves the data to Postgres in the background. Zero latency added.
    """
    background_tasks.add_task(save_event_to_db, req.event_type, req.user_email, req.metadata)
    return {"status": "tracked_in_background"}

# ── 2. Thread-Safe Data Reads ────────────────────────────────────────────────
@app.get("/stats/overview", dependencies=[Depends(verify_internal)])
def get_overview():
    """Thread-safe synchronous execution."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM builds")
            total_builds = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM licenses WHERE status = 'active'")
            active_licenses = cur.fetchone()[0]
            cur.execute("SELECT project_type, COUNT(*) as cnt FROM builds GROUP BY project_type ORDER BY cnt DESC LIMIT 1")
            top_row = cur.fetchone()

    return {
        "total_builds": total_builds,
        "active_licenses": active_licenses,
        "top_build_type": top_row[0] if top_row else "N/A",
        "generated_at": str(datetime.utcnow())
    }

@app.get("/stats/revenue", dependencies=[Depends(verify_internal)])
def get_revenue_stats():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tier, COUNT(*) as count FROM licenses WHERE status = 'active' GROUP BY tier")
            by_tier = cur.fetchall()

    pricing = {"starter": 29, "pro": 49, "master": 99}
    revenue_data = []
    total_mrr = 0

    for tier, count in by_tier:
        price = pricing.get(tier, 49)
        mrr = price * count
        total_mrr += mrr
        revenue_data.append({"tier": tier, "count": count, "price": f"${price}", "mrr": f"${mrr}"})

    return {"tiers": revenue_data, "total_mrr": f"${total_mrr}"}
