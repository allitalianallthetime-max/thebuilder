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
import jwt
import secrets
import hashlib
import datetime
import logging
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from contextlib import contextmanager
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

# ── Database ──────────────────────────────────────────────────────────────────
@contextmanager
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Create all required tables."""
    with get_db() as conn:
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

try:
    init_db()
except Exception as e:
    log.warning(f"DB Init: {e}")

# ── Security ──────────────────────────────────────────────────────────────────
async def verify_internal(x_internal_key: str = Header(None)):
    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal key")

def generate_license_key() -> str:
    """Generate a unique BUILDER-XXXX-XXXX-XXXX license key."""
    parts = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"BUILDER-{'-'.join(parts)}"

def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

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

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, expires_at, tier, email, name FROM licenses WHERE license_key = %s",
                (data.license_key,)
            )
            result = cur.fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="License not found")

    status, expires_at, tier, email, name = result

    if status != "active":
        raise HTTPException(status_code=403, detail="License is inactive")

    if expires_at < datetime.datetime.now():
        raise HTTPException(status_code=403, detail="License expired")

    # Increment build count
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE licenses SET build_count = build_count + 1 WHERE license_key = %s",
                    (data.license_key,)
                )
                conn.commit()
    except Exception:
        pass

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

    try:
        with get_db() as conn:
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
        log.error(f"License creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"License creation failed: {str(e)}")

@app.post("/notify/queue")
async def queue_notification(
    req: NotifyRequest,
    x_internal_key: str = Header(None)
):
    """Queue an email notification for the scheduler to send."""
    await verify_internal(x_internal_key)

    import json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO notification_queue (type, to_email, name, payload, status)
                VALUES (%s, %s, %s, %s, 'pending')
            """, (req.type, req.to, req.name, json.dumps(req.payload)))
            conn.commit()

    log.info(f"Notification queued: {req.type} → {req.to}")
    return {"status": "queued", "type": req.type, "to": req.to}

@app.get("/admin/licenses")
async def get_all_licenses(x_internal_key: str = Header(None)):
    """Admin endpoint — returns all licenses for lifecycle management."""
    await verify_internal(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT license_key, email, name, status, tier,
                       expires_at, build_count, created_at
                FROM licenses ORDER BY created_at DESC
            """)
            rows = cur.fetchall()

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

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM licenses WHERE license_key = %s", (license_key,))
            row = cur.fetchone()

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

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE licenses SET status = 'deleted' WHERE license_key = %s",
                (license_key,)
            )
            conn.commit()

    return {"status": "deleted", "license_key": license_key}

@app.get("/notify/pending")
async def get_pending_notifications(x_internal_key: str = Header(None)):
    """Called by scheduler to get pending emails."""
    await verify_internal(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, type, to_email, name, payload
                FROM notification_queue WHERE status = 'pending'
                ORDER BY created_at ASC LIMIT 50
            """)
            rows = cur.fetchall()

    import json
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

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE notification_queue SET status = 'sent' WHERE id = %s",
                (notification_id,)
            )
            conn.commit()

    return {"status": "marked_sent"}
