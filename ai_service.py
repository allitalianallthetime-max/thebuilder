"""
ai_service.py — The Round Table API Gateway
============================================
Highly robust FastAPI gateway.
Checks credits, deducts usage immediately, and queues background AI tasks.
Zero timeouts. Zero API bleeding.
"""

import os
import secrets
import logging
import time
import psycopg2
import psycopg2.pool
import redis
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from celery.result import AsyncResult
from celery import Celery
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [AI-API] %(levelname)s %(message)s")
log = logging.getLogger("ai-api")

app = FastAPI(title="The Builder - AI Gateway")

# ── 1. Redis & Celery Setup ───────────────────────────────────────────────────
# Use Redis for both Celery messaging and distributed rate limiting
REDIS_URL = os.getenv("REDIS_URL", "redis://builder-redis:6379/0")
celery_app = Celery("ai_tasks", broker=REDIS_URL, backend=REDIS_URL)
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# ── 2. Configuration & Security ───────────────────────────────────────────────
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
DATABASE_URL     = os.getenv("DATABASE_URL")

def verify_key(provided: str) -> bool:
    if not provided or not INTERNAL_API_KEY:
        return False
    return secrets.compare_digest(provided, INTERNAL_API_KEY)

# ── 3. Enterprise Distributed Rate Limiting ───────────────────────────────────
def is_rate_limited(key: str, limit: int, window: int) -> bool:
    """Uses Redis to track rate limits across ALL active Gunicorn workers."""
    try:
        current = redis_client.incr(key)
        if current == 1:
            redis_client.expire(key, window)
        return current > limit
    except Exception as e:
        log.error(f"Redis rate limiter failed: {e}")
        return False # Fail open so customers aren't blocked by Redis hiccups

# ── 4. Database & Billing Protection ──────────────────────────────────────────
db_pool = psycopg2.pool.ThreadedConnectionPool(minconn=2, maxconn=10, dsn=DATABASE_URL)

TIER_LIMITS = {"starter": 25, "pro": 100, "master": 999}

def deduct_credit_safely(user_email: str) -> dict:
    """
    PROFIT PROTECTION: Checks limits and deducts credit in a single, locked 
    database transaction to prevent spam/double-click API draining.
    """
    if user_email in ("admin", "anonymous"):
        return {"allowed": True, "tier": "master", "used": 0, "limit": 999, "remaining": 999}

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            # FOR UPDATE locks the row so concurrent requests queue up safely
            cur.execute("""
                SELECT tier, status, expires_at, build_count 
                FROM licenses 
                WHERE email = %s AND status = 'active' 
                ORDER BY created_at DESC LIMIT 1
                FOR UPDATE
            """, (user_email,))
            lic = cur.fetchone()

            if not lic:
                return {"allowed": False, "reason": "No active license found."}

            tier, status, expires_at, build_count = lic
            
            if expires_at < datetime.utcnow():
                return {"allowed": False, "reason": "License expired. Renew to continue forging."}
                
            limit = TIER_LIMITS.get(tier, 25)

            if build_count >= limit:
                return {"allowed": False, "reason": f"{tier.upper()} tier limit reached ({build_count}/{limit}). Upgrade required."}

            # DEDUCT CREDIT BEFORE GENERATION STARTS
            cur.execute("""
                UPDATE licenses SET build_count = build_count + 1 
                WHERE email = %s AND status = 'active'
            """, (user_email,))
            conn.commit()
            
            return {
                "allowed": True, "tier": tier, "used": build_count + 1, 
                "limit": limit, "remaining": max(0, limit - (build_count + 1))
            }
    except Exception as e:
        conn.rollback()
        log.error(f"Billing transaction error: {e}")
        raise HTTPException(status_code=500, detail="Billing system unavailable.")
    finally:
        db_pool.putconn(conn)

# ── 5. Models & Endpoints ─────────────────────────────────────────────────────
class BuildRequest(BaseModel):
    junk_desc: str
    project_type: str
    detail_level: str = "Full Blueprint (All 3 Tiers)"
    user_email: str = "anonymous"

@app.post("/generate")
def generate_blueprint(req: BuildRequest, x_internal_key: str = Header(None)):
    """Accepts request, deducts credit, queues job to Celery, returns instantly."""
    if not verify_key(x_internal_key):
        raise HTTPException(status_code=403, detail="Invalid Security Badge")

    if is_rate_limited(f"rate:gen:{req.user_email}", limit=10, window=300):
        raise HTTPException(status_code=429, detail="Too many builds. Try again in 5 minutes.")

    if len(req.junk_desc) > 5000:
        raise HTTPException(status_code=400, detail="Parts description too long.")

    # 1. Secure Authorization & Immediate Credit Deduction
    limits = deduct_credit_safely(req.user_email)
    if not limits.get("allowed"):
        raise HTTPException(status_code=402, detail=limits.get("reason"))

    # 2. Fire and Forget: Send to Background Worker
    task = celery_app.send_task(
        "ai_worker.forge_blueprint_task",
        args=[req.junk_desc, req.project_type, req.user_email, req.detail_level]
    )

    return {
        "status": "processing",
        "task_id": task.id,
        "message": "The Round Table has convened. Blueprint generation is underway.",
        "usage": {"tier": limits["tier"], "used": limits["used"], "limit": limits["limit"], "remaining": limits["remaining"]}
    }

@app.get("/generate/status/{task_id}")
def check_generation_status(task_id: str, x_internal_key: str = Header(None)):
    """UI polls this endpoint. Does not block the main API threads."""
    if not verify_key(x_internal_key):
        raise HTTPException(status_code=403, detail="Unauthorized")

    task_result = AsyncResult(task_id, app=celery_app)
    
    if task_result.state == 'PENDING':
        return {"status": "pending", "message": "Waiting for engineers..."}
    elif task_result.state == 'PROGRESS':
        return {"status": "processing", "message": task_result.info.get("message", "AIs are deliberating...")}
    elif task_result.state == 'SUCCESS':
        return {"status": "complete", "result": task_result.result}
    elif task_result.state == 'FAILURE':
        return {"status": "failed", "error": str(task_result.info)}
    else:
        return {"status": "processing", "message": task_result.state}

@app.get("/builds")
def get_all_builds(x_internal_key: str = Header(None), user_email: str = None):
    if not verify_key(x_internal_key): raise HTTPException(status_code=403)
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            if user_email:
                cur.execute("SELECT id, user_email, project_type, junk_desc, created_at FROM builds WHERE user_email = %s ORDER BY created_at DESC LIMIT 100", (user_email,))
            else:
                cur.execute("SELECT id, user_email, project_type, junk_desc, created_at FROM builds ORDER BY created_at DESC LIMIT 100")
            rows = cur.fetchall()
            return [{"id": r[0], "email": r[1], "type": r[2], "parts": r[3][:80], "created": str(r[4])} for r in rows]
    finally:
        db_pool.putconn(conn)

@app.get("/builds/{build_id}")
def get_build(build_id: int, x_internal_key: str = Header(None)):
    if not verify_key(x_internal_key): raise HTTPException(status_code=403)
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, user_email, junk_desc, project_type, blueprint, grok_notes, claude_notes, tokens_used, created_at FROM builds WHERE id = %s", (build_id,))
            row = cur.fetchone()
            if not row: raise HTTPException(status_code=404, detail="Build not found")
            return {"id": row[0], "email": row[1], "junk_desc": row[2], "project_type": row[3], "blueprint": row[4], "grok_notes": row[5], "claude_notes": row[6], "created": str(row[8])}
    finally:
        db_pool.putconn(conn)

@app.get("/health")
def health():
    return {"status": "online", "engine": "gateway", "queue": "active"}
