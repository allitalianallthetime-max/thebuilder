"""
auth_service.py — The Builder Auth Service
==========================================
FastAPI service for license management, key validation, JWT issuance,
build history, and notification queue management.

Deploy on Render as a separate Web Service.
Set env vars: INTERNAL_API_KEY, DATABASE_URL, JWT_SECRET,
              RESEND_API_KEY, FROM_EMAIL, APP_URL
"""

import os
import logging
import sqlite3
import secrets
import string
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

import httpx
import jwt                     # pip install PyJWT
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from pydantic import BaseModel, EmailStr

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [AUTH] %(levelname)s %(message)s")
log = logging.getLogger("auth_service")

# ── Config ────────────────────────────────────────────────────────────────────
INTERNAL_API_KEY = os.environ["INTERNAL_API_KEY"]
DATABASE_URL     = os.environ.get("DATABASE_URL", "builder.db")
JWT_SECRET       = os.environ["JWT_SECRET"]            # random 64-char string
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "2"))
RESEND_API_KEY   = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL       = os.environ.get("FROM_EMAIL", "The Builder <noreply@yourdomain.com>")
APP_URL          = os.environ.get("APP_URL", "")

app = FastAPI(title="Builder Auth Service", docs_url=None, redoc_url=None)


# ── DB ─────────────────────────────────────────────────────────────────────────
@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS licenses (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key        TEXT UNIQUE NOT NULL,
                email              TEXT NOT NULL,
                name               TEXT DEFAULT '',
                stripe_customer_id TEXT DEFAULT '',
                status             TEXT DEFAULT 'active',
                expires_at         TEXT NOT NULL,
                notes              TEXT DEFAULT '',
                created_at         TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS build_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT NOT NULL,
                entry       TEXT NOT NULL,
                timestamp   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS notification_queue (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                type       TEXT NOT NULL,
                to_email   TEXT NOT NULL,
                name       TEXT DEFAULT '',
                payload    TEXT DEFAULT '{}',
                status     TEXT DEFAULT 'pending',
                retries    INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                sent_at    TEXT
            );
        """)
    log.info("Database initialized")


init_db()


# ── Helpers ───────────────────────────────────────────────────────────────────
def generate_key() -> str:
    chars = string.ascii_uppercase + string.digits
    segments = ["".join(secrets.choice(chars) for _ in range(4)) for _ in range(3)]
    return "BLDR-" + "-".join(segments)


def require_internal_key(x_internal_key: str = Header(None)):
    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")


# ── Models ────────────────────────────────────────────────────────────────────
class CreateLicenseRequest(BaseModel):
    email:              str
    name:               str = ""
    stripe_customer_id: str = ""
    days:               int = 30
    notes:              str = ""

class ValidateRequest(BaseModel):
    license_key: str

class RevokeRequest(BaseModel):
    license_key: str
    reason:      str = ""

class RevokeByStripeRequest(BaseModel):
    stripe_customer_id: str
    reason:             str = ""

class ExtendRequest(BaseModel):
    license_key: str
    days:        int = 30

class SaveBuildRequest(BaseModel):
    license_key: str
    entry:       str

class NotifyQueueRequest(BaseModel):
    type:    str          # "welcome" | "expiry_warning" | "final_warning"
    to:      str
    name:    str = ""
    payload: dict = {}


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    with get_db() as conn:
        try:
            conn.execute("SELECT 1 FROM licenses LIMIT 1")
            db_ok = True
        except Exception:
            db_ok = False
    return {"status": "ok" if db_ok else "degraded", "service": "auth", "db": db_ok}


# ── License CRUD ──────────────────────────────────────────────────────────────
@app.post("/auth/create")
async def create_license(req: CreateLicenseRequest, _=Depends(require_internal_key)):
    key        = generate_key()
    expires_at = (datetime.utcnow() + timedelta(days=req.days)).isoformat()

    with get_db() as conn:
        conn.execute(
            """INSERT INTO licenses (license_key, email, name, stripe_customer_id, expires_at, notes)
               VALUES (?,?,?,?,?,?)""",
            (key, req.email, req.name, req.stripe_customer_id, expires_at, req.notes)
        )

    log.info(f"License created: {key} for {req.email} (expires {expires_at[:10]})")
    return {"key": key, "email": req.email, "expires_at": expires_at}


@app.post("/auth/validate")
async def validate_license(req: ValidateRequest):
    """
    Validate a license key. Returns a short-lived JWT on success.
    Called by Streamlit UI — does NOT require internal key (users call this directly).
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM licenses WHERE license_key=?", (req.license_key,)
        ).fetchone()

    if not row:
        return {"valid": False, "status": "not_found"}

    if row["status"] == "revoked":
        return {"valid": False, "status": "revoked"}

    # Check expiry
    expires_at   = datetime.fromisoformat(row["expires_at"])
    now          = datetime.utcnow()
    days_remaining = (expires_at - now).days

    if days_remaining < -15:  # 15-day grace period, then truly expired
        return {"valid": False, "status": "expired", "days_remaining": days_remaining}

    # Issue a short-lived JWT
    token_payload = {
        "sub":  req.license_key,
        "name": row["name"],
        "exp":  datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat":  datetime.now(timezone.utc),
    }
    token = jwt.encode(token_payload, JWT_SECRET, algorithm="HS256")

    return {
        "valid":          True,
        "status":         row["status"],
        "email":          row["email"],
        "name":           row["name"],
        "days_remaining": days_remaining,
        "token":          token,
    }


@app.post("/auth/revoke")
async def revoke_license(req: RevokeRequest, _=Depends(require_internal_key)):
    with get_db() as conn:
        result = conn.execute(
            "UPDATE licenses SET status='revoked', notes=? WHERE license_key=?",
            (req.reason, req.license_key)
        )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Key not found")
    log.info(f"License revoked: {req.license_key} — reason: {req.reason}")
    return {"ok": True}


@app.post("/auth/revoke-by-stripe-id")
async def revoke_by_stripe(req: RevokeByStripeRequest, _=Depends(require_internal_key)):
    with get_db() as conn:
        result = conn.execute(
            "UPDATE licenses SET status='revoked', notes=? WHERE stripe_customer_id=?",
            (req.reason, req.stripe_customer_id)
        )
    if result.rowcount == 0:
        log.warning(f"No license found for Stripe customer: {req.stripe_customer_id}")
        return {"ok": False, "detail": "Not found"}
    log.info(f"License revoked for Stripe customer: {req.stripe_customer_id}")
    return {"ok": True}


@app.post("/auth/extend")
async def extend_license(req: ExtendRequest, _=Depends(require_internal_key)):
    with get_db() as conn:
        row = conn.execute(
            "SELECT expires_at FROM licenses WHERE license_key=?", (req.license_key,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Key not found")

        current_expiry = datetime.fromisoformat(row["expires_at"])
        base           = max(current_expiry, datetime.utcnow())
        new_expiry     = (base + timedelta(days=req.days)).isoformat()

        conn.execute(
            "UPDATE licenses SET expires_at=?, status='active' WHERE license_key=?",
            (new_expiry, req.license_key)
        )
    return {"ok": True, "new_expiry": new_expiry}


@app.get("/admin/licenses")
async def list_licenses(_=Depends(require_internal_key)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM licenses ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Build History ─────────────────────────────────────────────────────────────
@app.post("/auth/save-build")
async def save_build(req: SaveBuildRequest, _=Depends(require_internal_key)):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO build_history (license_key, entry) VALUES (?,?)",
            (req.license_key, req.entry)
        )
    return {"ok": True}


@app.get("/auth/history/{license_key}")
async def get_history(license_key: str, limit: int = 30, _=Depends(require_internal_key)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT entry, timestamp FROM build_history WHERE license_key=? ORDER BY timestamp DESC LIMIT ?",
            (license_key, limit)
        ).fetchall()
    return [dict(r) for r in rows]


@app.delete("/auth/history/{license_key}")
async def delete_history(license_key: str, _=Depends(require_internal_key)):
    with get_db() as conn:
        conn.execute("DELETE FROM build_history WHERE license_key=?", (license_key,))
        conn.execute("DELETE FROM licenses WHERE license_key=?", (license_key,))
    return {"ok": True}


# ── Notification Queue ────────────────────────────────────────────────────────
@app.post("/notify/queue")
async def queue_notification(req: NotifyQueueRequest, _=Depends(require_internal_key)):
    """Add a notification job to the queue. Processed by the Scheduler Worker."""
    import json
    with get_db() as conn:
        conn.execute(
            "INSERT INTO notification_queue (type, to_email, name, payload) VALUES (?,?,?,?)",
            (req.type, req.to, req.name, json.dumps(req.payload))
        )
    log.info(f"Queued {req.type} notification for {req.to}")
    return {"ok": True}


@app.get("/notify/pending")
async def get_pending_notifications(limit: int = 50, _=Depends(require_internal_key)):
    """Scheduler Worker polls this to get pending jobs."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM notification_queue
               WHERE status='pending' AND retries < 3
               ORDER BY created_at ASC LIMIT ?""",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/notify/mark-sent/{job_id}")
async def mark_sent(job_id: int, _=Depends(require_internal_key)):
    with get_db() as conn:
        conn.execute(
            "UPDATE notification_queue SET status='sent', sent_at=datetime('now') WHERE id=?",
            (job_id,)
        )
    return {"ok": True}


@app.post("/notify/mark-failed/{job_id}")
async def mark_failed(job_id: int, _=Depends(require_internal_key)):
    with get_db() as conn:
        conn.execute(
            "UPDATE notification_queue SET retries=retries+1 WHERE id=?",
            (job_id,)
        )
    return {"ok": True}
