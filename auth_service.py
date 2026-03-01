"""
auth_service.py — The Security Guard
======================================
Handles:
- License verification & JWT issuance
- License creation (called by billing)
- User management
- Notification queue
- Admin endpoints
"""

import os
import psycopg2
import psycopg2.pool
import jwt
import secrets
import datetime
import logging
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [AUTH] %(levelname)s %(message)s")
log = logging.getLogger("auth")

app = FastAPI()

# ── Configuration ─────────────────────────────────────────────────────────────
DATABASE_URL     = os.getenv("DATABASE_URL")
JWT_SECRET       = os.getenv("JWT_SECRET", secrets.token_hex(32))
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

# ── Database (connection pool) ────────────────────────────────────────────────
db_pool = None

def get_pool():
    global db_pool
    if db_pool is None:
        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2, maxconn=10, dsn=DATABASE_URL
        )
    return db_pool

def get_conn():
    return get_pool().getconn()

def put_conn(conn):
    get_pool().putconn(conn)

def init_db():
    """Create all required tables."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Licenses table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS licenses (
                    id               SERIAL PRIMARY KEY,
                    license_key      TEXT UNIQUE NOT NULL,
                    email            TEXT NOT NULL,
                    name             TEXT DEFAULT 'Builder',
                    stripe_customer_id TEXT,
                    status           TEXT DEFAULT 'active',
                    tier             TEXT DEFAULT 'pro',
                    expires_at       TIMESTAMP NOT NULL,
                    build_count      INTEGER DEFAULT 0,
                    notes            TEXT,
                    created_at       TIMESTAMP DEFAULT NOW()
                )
            """)
            # Notification queue
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notification_queue (
                    id         SERIAL PRIMARY KEY,
                    type       TEXT NOT NULL,
                    to_email   TEXT NOT NULL,
                    name       TEXT,
                    payload    JSONB,
                    status     TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
        log.info("Database initialized.")
    finally:
        put_conn(conn)

try:
    init_db()
except Exception as e:
    log.warning(f"DB Init: {e}")

# ── Security ──────────────────────────────────────────────────────────────────
async def verify_internal(x_internal_key: str = Header(None)):
    if not x_internal_key or not INTERNAL_API_KEY or \
       not secrets.compare_digest(x_internal_key, INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid internal key")

def generate_license_key() -> str:
    """Generate a unique BUILDER-XXXX-XXXX-XXXX license key."""
    parts = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"BUILDER-{'-'.join(parts)}"


# ── Models ────────────────────────────────────────────────────────────────────
class LicenseCreateRequest(BaseModel):
    email:             str
    name:              str = "Builder"
    stripe_customer_id: str = ""
    days:              int = 30
    tier:              str = "pro"
    notes:             str = ""

class NotifyRequest(BaseModel):
    type:    str
    to:      str
    name:    str = ""
    payload: dict = {}

class VerifyRequest(BaseModel):
    license_key: str

# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/verify-license")
async def verify_license(
    data: VerifyRequest,
    x_internal_key: str = Header(None)
):
    await verify_internal(x_internal_key)

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, expires_at, tier, email, name FROM licenses WHERE license_key = %s",
                (data.license_key,)
            )
            result = cur.fetchone()
    finally:
        if conn:
            put_conn(conn)

    if not result:
        raise HTTPException(status_code=404, detail="License not found")

    status, expires_at, tier, email, name = result

    if status != "active":
        raise HTTPException(status_code=403, detail="License is inactive")

    if expires_at < datetime.datetime.utcnow():
        raise HTTPException(status_code=403, detail="License expired")

    # NOTE: We do NOT increment build_count here.
    # build_count is incremented by the AI service when a build is actually generated.
    # This endpoint is for authentication only.

    # Issue JWT badge
    token = jwt.encode({
        "sub":   data.license_key,
        "email": email,
        "name":  name,
        "tier":  tier,
        "exp":   datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, JWT_SECRET, algorithm="HS256")

    return {"token": token, "tier": tier, "name": name, "email": email}

@app.post("/auth/create")
async def create_license(
    req: LicenseCreateRequest,
    x_internal_key: str = Header(None)
):
    """Called by billing service when a payment is completed."""
    await verify_internal(x_internal_key)

    license_key = generate_license_key()
    expires_at  = datetime.datetime.utcnow() + datetime.timedelta(days=req.days)

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO licenses
                    (license_key, email, name, stripe_customer_id, status, tier, expires_at, notes)
                VALUES (%s, %s, %s, %s, 'active', %s, %s, %s)
                RETURNING id
            """, (
                license_key, req.email, req.name,
                req.stripe_customer_id, req.tier,
                expires_at, req.notes
            ))
            conn.commit()

        log.info(f"License created: {license_key} for {req.email}")
        return {
            "key":        license_key,
            "email":      req.email,
            "tier":       req.tier,
            "expires_at": str(expires_at),
            "status":     "active"
        }

    except Exception as e:
        if conn:
            conn.rollback()
        log.error(f"License creation failed: {e}")
        raise HTTPException(status_code=500, detail="License creation failed. Please try again.")
    finally:
        if conn:
            put_conn(conn)

@app.post("/notify/queue")
async def queue_notification(
    req: NotifyRequest,
    x_internal_key: str = Header(None)
):
    """Queue an email notification for the scheduler to send."""
    await verify_internal(x_internal_key)

    import json
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO notification_queue (type, to_email, name, payload, status)
                VALUES (%s, %s, %s, %s, 'pending')
            """, (req.type, req.to, req.name, json.dumps(req.payload)))
            conn.commit()
    finally:
        put_conn(conn)

    log.info(f"Notification queued: {req.type} → {req.to}")
    return {"status": "queued", "type": req.type, "to": req.to}

@app.get("/admin/licenses")
async def get_all_licenses(x_internal_key: str = Header(None)):
    """Admin endpoint — returns all licenses for lifecycle management."""
    await verify_internal(x_internal_key)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT license_key, email, name, status, tier,
                       expires_at, build_count, created_at
                FROM licenses ORDER BY created_at DESC
            """)
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    return [
        {
            "license_key": r[0], "email": r[1], "name": r[2],
            "status": r[3], "tier": r[4], "expires_at": str(r[5]),
            "build_count": r[6], "created_at": str(r[7])
        }
        for r in rows
    ]

@app.get("/admin/licenses/{license_key}")
async def get_license(license_key: str, x_internal_key: str = Header(None)):
    await verify_internal(x_internal_key)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Explicit columns — no SELECT * to avoid index drift
            cur.execute("""
                SELECT id, license_key, email, name, stripe_customer_id,
                       status, tier, expires_at, build_count, notes, created_at
                FROM licenses WHERE license_key = %s
            """, (license_key,))
            row = cur.fetchone()
    finally:
        put_conn(conn)

    if not row:
        raise HTTPException(status_code=404, detail="License not found")

    return {
        "id": row[0], "license_key": row[1], "email": row[2],
        "name": row[3], "status": row[5], "tier": row[6],
        "expires_at": str(row[7]), "build_count": row[8]
    }

@app.delete("/auth/history/{license_key}")
async def delete_license_history(license_key: str, x_internal_key: str = Header(None)):
    """Called by scheduler to clean up expired data."""
    await verify_internal(x_internal_key)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE licenses SET status = 'deleted' WHERE license_key = %s",
                (license_key,)
            )
            conn.commit()
    finally:
        put_conn(conn)

    return {"status": "deleted", "license_key": license_key}

# ── 1.6: Subscription Cancellation ───────────────────────────────────────────
class DeactivateByCustomerRequest(BaseModel):
    stripe_customer_id: str
    reason: str = "Subscription cancelled"

@app.post("/auth/deactivate-by-customer")
async def deactivate_by_customer(
    req: DeactivateByCustomerRequest,
    x_internal_key: str = Header(None)
):
    """Deactivate all licenses for a Stripe customer (subscription cancelled)."""
    await verify_internal(x_internal_key)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE licenses SET status = 'cancelled', notes = %s
                WHERE stripe_customer_id = %s AND status = 'active'
                RETURNING license_key, email
            """, (req.reason, req.stripe_customer_id))
            rows = cur.fetchall()
            conn.commit()
    finally:
        put_conn(conn)

    if rows:
        log.info(f"Deactivated {len(rows)} license(s) for Stripe customer {req.stripe_customer_id}")
    else:
        log.warning(f"No active licenses found for Stripe customer {req.stripe_customer_id}")

    return {
        "deactivated": len(rows),
        "licenses": [{"key": r[0], "email": r[1]} for r in rows]
    }

# ── 1.9: Idempotency Check (Webhook Replay Protection) ──────────────────────
@app.get("/auth/check-session/{session_id}")
async def check_session_provisioned(session_id: str, x_internal_key: str = Header(None)):
    """Check if a license was already provisioned for a Stripe session.
    Prevents duplicate licenses from webhook replays."""
    await verify_internal(x_internal_key)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT license_key, email, tier FROM licenses
                WHERE notes LIKE %s LIMIT 1
            """, (f"%{session_id}%",))
            row = cur.fetchone()
    finally:
        put_conn(conn)

    if row:
        return {"provisioned": True, "license_key": row[0], "email": row[1], "tier": row[2]}
    return {"provisioned": False}

@app.get("/notify/pending")
async def get_pending_notifications(x_internal_key: str = Header(None)):
    """Called by scheduler to get pending emails."""
    await verify_internal(x_internal_key)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, type, to_email, name, payload
                FROM notification_queue WHERE status = 'pending'
                ORDER BY created_at ASC LIMIT 50
            """)
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    return [
        {
            "id": r[0], "type": r[1], "to": r[2],
            "name": r[3], "payload": r[4]
        }
        for r in rows
    ]

@app.post("/notify/mark-sent/{notification_id}")
async def mark_notification_sent(
    notification_id: int,
    x_internal_key: str = Header(None)
):
    await verify_internal(x_internal_key)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE notification_queue SET status = 'sent' WHERE id = %s",
                (notification_id,)
            )
            conn.commit()
    finally:
        put_conn(conn)

    return {"status": "marked_sent"}
