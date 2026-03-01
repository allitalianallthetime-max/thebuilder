"""
auth_service.py — The Security Guard
======================================
Fully Thread-Safe implementation.
Handles JWT issuance, License management, and the Notification Queue.
"""

import os
import psycopg2
import psycopg2.pool
import jwt
import secrets
import datetime
import logging
import json
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [AUTH] %(levelname)s %(message)s")
log = logging.getLogger("auth")

app = FastAPI(title="The Builder - Auth Security")

# ── Configuration ─────────────────────────────────────────────────────────────
DATABASE_URL     = os.getenv("DATABASE_URL")
JWT_SECRET       = os.getenv("JWT_SECRET", secrets.token_hex(32))
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

# ── Database (Thread-Safe Connection Pool) ──────────────────────────────────
db_pool = None
try:
    db_pool = psycopg2.pool.ThreadedConnectionPool(minconn=2, maxconn=15, dsn=DATABASE_URL)
    log.info("Auth DB Pool initialized.")
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

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
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

try: init_db()
except Exception as e: log.warning(f"DB Init: {e}")

# ── Security ──────────────────────────────────────────────────────────────────
def verify_internal(x_internal_key: str = Header(None)):
    if not x_internal_key or not INTERNAL_API_KEY or not secrets.compare_digest(x_internal_key, INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid internal key")

def generate_license_key() -> str:
    parts = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"BUILDER-{'-'.join(parts)}"

# ── Models ────────────────────────────────────────────────────────────────────
class LicenseCreateRequest(BaseModel): email: str; name: str = "Builder"; stripe_customer_id: str = ""; days: int = 30; tier: str = "pro"; notes: str = ""
class NotifyRequest(BaseModel): type: str; to: str; name: str = ""; payload: dict = {}
class VerifyRequest(BaseModel): license_key: str
class DeactivateByCustomerRequest(BaseModel): stripe_customer_id: str; reason: str = "Subscription cancelled"

# ── ENDPOINTS (Standard 'def' for Auto-Threading) ───────────────────────────

@app.get("/health")
def health(): return {"status": "healthy"}

@app.post("/verify-license")
def verify_license(data: VerifyRequest, _=Depends(verify_internal)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, expires_at, tier, email, name FROM licenses WHERE license_key = %s", (data.license_key,))
            result = cur.fetchone()

    if not result: raise HTTPException(status_code=404, detail="License not found")
    status, expires_at, tier, email, name = result

    if status != "active": raise HTTPException(status_code=403, detail="License is inactive")
    if expires_at < datetime.datetime.utcnow(): raise HTTPException(status_code=403, detail="License expired")

    token = jwt.encode({
        "sub": data.license_key, "email": email, "name": name, "tier": tier,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, JWT_SECRET, algorithm="HS256")

    return {"token": token, "tier": tier, "name": name, "email": email}

@app.post("/auth/create", dependencies=[Depends(verify_internal)])
def create_license(req: LicenseCreateRequest):
    license_key = generate_license_key()
    expires_at  = datetime.datetime.utcnow() + datetime.timedelta(days=req.days)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO licenses (license_key, email, name, stripe_customer_id, status, tier, expires_at, notes)
                VALUES (%s, %s, %s, %s, 'active', %s, %s, %s) RETURNING id
            """, (license_key, req.email, req.name, req.stripe_customer_id, req.tier, expires_at, req.notes))
            conn.commit()

    log.info(f"License created: {license_key} for {req.email}")
    return {"key": license_key, "email": req.email, "tier": req.tier, "expires_at": str(expires_at), "status": "active"}

@app.post("/notify/queue", dependencies=[Depends(verify_internal)])
def queue_notification(req: NotifyRequest):
    import json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO notification_queue (type, to_email, name, payload, status) VALUES (%s, %s, %s, %s, 'pending')",
                (req.type, req.to, req.name, json.dumps(req.payload))
            )
            conn.commit()
    return {"status": "queued", "type": req.type, "to": req.to}

@app.get("/admin/licenses", dependencies=[Depends(verify_internal)])
def get_all_licenses():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT license_key, email, name, status, tier, expires_at, build_count, created_at FROM licenses ORDER BY created_at DESC")
            rows = cur.fetchall()
    return [{"license_key": r[0], "email": r[1], "name": r[2], "status": r[3], "tier": r[4], "expires_at": str(r[5]), "build_count": r[6], "created_at": str(r[7])} for r in rows]

@app.delete("/auth/history/{license_key}", dependencies=[Depends(verify_internal)])
def delete_license_history(license_key: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE licenses SET status = 'deleted' WHERE license_key = %s", (license_key,))
            conn.commit()
    return {"status": "deleted", "license_key": license_key}

@app.post("/auth/deactivate-by-customer", dependencies=[Depends(verify_internal)])
def deactivate_by_customer(req: DeactivateByCustomerRequest):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE licenses SET status = 'cancelled', notes = %s WHERE stripe_customer_id = %s AND status = 'active' RETURNING license_key, email", (req.reason, req.stripe_customer_id))
            rows = cur.fetchall()
            conn.commit()
    return {"deactivated": len(rows), "licenses": [{"key": r[0], "email": r[1]} for r in rows]}

@app.get("/auth/check-session/{session_id}", dependencies=[Depends(verify_internal)])
def check_session_provisioned(session_id: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT license_key, email, tier FROM licenses WHERE notes LIKE %s LIMIT 1", (f"%{session_id}%",))
            row = cur.fetchone()
    if row: return {"provisioned": True, "license_key": row[0], "email": row[1], "tier": row[2]}
    return {"provisioned": False}

@app.get("/notify/pending", dependencies=[Depends(verify_internal)])
def get_pending_notifications():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, type, to_email, name, payload FROM notification_queue WHERE status = 'pending' ORDER BY created_at ASC LIMIT 50")
            rows = cur.fetchall()
    return [{"id": r[0], "type": r[1], "to": r[2], "name": r[3], "payload": r[4]} for r in rows]

@app.post("/notify/mark-sent/{notification_id}", dependencies=[Depends(verify_internal)])
def mark_notification_sent(notification_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE notification_queue SET status = 'sent' WHERE id = %s", (notification_id,))
            conn.commit()
    return {"status": "marked_sent"}
