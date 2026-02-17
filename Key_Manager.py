"""
key_manager.py — The Builder License & Key Management System
Handles: key generation, validation, expiry, user data deletion, email alerts
"""

import sqlite3
import secrets
import string
import hashlib
import smtplib
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─────────────────────────────────────────────
#  CONFIG — fill these in your .env or directly
# ─────────────────────────────────────────────
DB_FILE       = "builder_licenses.db"
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "your_gmail@gmail.com")
GMAIL_APP_PW  = os.environ.get("GMAIL_APP_PW",  "your_16char_app_password")
APP_URL       = os.environ.get("APP_URL",        "https://your-streamlit-app-url.com")
PRICE         = "$29.99"
APP_NAME      = "The Builder"

# ─────────────────────────────────────────────
#  DATABASE SETUP
# ─────────────────────────────────────────────

def init_db():
    """Create the SQLite database and all tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            key_hash        TEXT    UNIQUE NOT NULL,
            key_plain       TEXT    UNIQUE NOT NULL,   -- store plain for admin display only
            email           TEXT    NOT NULL,
            name            TEXT    DEFAULT '',
            created_at      TEXT    NOT NULL,
            expires_at      TEXT    NOT NULL,
            last_renewed    TEXT,
            status          TEXT    DEFAULT 'active',  -- active | warned_30 | warned_40 | expired | revoked
            stripe_session  TEXT,
            notes           TEXT    DEFAULT ''
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS build_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            key_hash    TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            entry       TEXT NOT NULL,
            FOREIGN KEY(key_hash) REFERENCES licenses(key_hash)
        )
    """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
#  KEY GENERATION & HASHING
# ─────────────────────────────────────────────

def generate_license_key() -> str:
    """Generate a human-readable license key: BLDR-XXXX-XXXX-XXXX"""
    chars = string.ascii_uppercase + string.digits
    segments = [''.join(secrets.choice(chars) for _ in range(4)) for _ in range(3)]
    return "BLDR-" + "-".join(segments)

def hash_key(key: str) -> str:
    """SHA-256 hash of the key for secure DB storage."""
    return hashlib.sha256(key.strip().upper().encode()).hexdigest()


# ─────────────────────────────────────────────
#  LICENSE CRUD
# ─────────────────────────────────────────────

def create_license(email: str, name: str = "", stripe_session: str = "") -> str:
    """
    Generate and store a new 30-day license.
    Returns the plain-text key to be emailed to the user.
    """
    init_db()
    key       = generate_license_key()
    key_hash  = hash_key(key)
    now       = datetime.utcnow()
    expires   = now + timedelta(days=30)

    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("""
        INSERT INTO licenses (key_hash, key_plain, email, name, created_at, expires_at,
                              last_renewed, status, stripe_session)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
    """, (key_hash, key, email, name,
          now.isoformat(), expires.isoformat(),
          now.isoformat(), stripe_session))
    conn.commit()
    conn.close()
    return key


def validate_key(key: str) -> dict:
    """
    Validate a key. Returns a dict with:
      valid (bool), status, days_remaining, email, name, warning (str|None)
    """
    init_db()
    key_hash = hash_key(key)
    conn     = sqlite3.connect(DB_FILE)
    c        = conn.cursor()
    c.execute("SELECT * FROM licenses WHERE key_hash = ?", (key_hash,))
    row = c.fetchone()
    conn.close()

    if not row:
        return {"valid": False, "status": "not_found", "warning": None}

    cols   = ["id","key_hash","key_plain","email","name","created_at",
              "expires_at","last_renewed","status","stripe_session","notes"]
    data   = dict(zip(cols, row))
    now    = datetime.utcnow()
    expiry = datetime.fromisoformat(data["expires_at"])
    days_left = (expiry - now).days

    if data["status"] == "revoked":
        return {"valid": False, "status": "revoked", "warning": None, **data}

    if data["status"] == "expired" or days_left < 0:
        return {"valid": False, "status": "expired", "days_remaining": 0, "warning": None, **data}

    warning = None
    if days_left <= 10:
        warning = f"⚠️ Your license expires in {days_left} day(s). Renew now at {APP_URL} to keep your data."
    elif days_left <= 15:
        warning = f"🔔 Your license expires in {days_left} days. Renew soon to avoid losing your build history."

    return {
        "valid": True,
        "status": data["status"],
        "days_remaining": days_left,
        "email": data["email"],
        "name": data["name"],
        "warning": warning,
        **data
    }


def renew_license(key: str) -> bool:
    """Extend license by 30 days from today. Returns True on success."""
    init_db()
    key_hash = hash_key(key)
    now      = datetime.utcnow()
    new_exp  = now + timedelta(days=30)

    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("""
        UPDATE licenses
        SET expires_at = ?, last_renewed = ?, status = 'active'
        WHERE key_hash = ?
    """, (new_exp.isoformat(), now.isoformat(), key_hash))
    updated = c.rowcount
    conn.commit()
    conn.close()
    return updated > 0


def revoke_license(key: str, reason: str = "") -> bool:
    """Admin: immediately revoke a key."""
    init_db()
    key_hash = hash_key(key)
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("UPDATE licenses SET status = 'revoked', notes = ? WHERE key_hash = ?",
              (reason, key_hash))
    updated = c.rowcount
    conn.commit()
    conn.close()
    return updated > 0


def extend_license(key: str, days: int = 30) -> bool:
    """Admin: manually extend a key by N days."""
    init_db()
    key_hash = hash_key(key)
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("SELECT expires_at FROM licenses WHERE key_hash = ?", (key_hash,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    current_expiry = datetime.fromisoformat(row[0])
    new_expiry     = max(current_expiry, datetime.utcnow()) + timedelta(days=days)
    c.execute("UPDATE licenses SET expires_at = ?, status = 'active' WHERE key_hash = ?",
              (new_expiry.isoformat(), key_hash))
    conn.commit()
    conn.close()
    return True


def get_all_licenses() -> list:
    """Admin: return all license rows as list of dicts."""
    init_db()
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("SELECT * FROM licenses ORDER BY created_at DESC")
    rows = c.fetchall()
    cols = ["id","key_hash","key_plain","email","name","created_at",
            "expires_at","last_renewed","status","stripe_session","notes"]
    return [dict(zip(cols, r)) for r in rows]


# ─────────────────────────────────────────────
#  BUILD HISTORY (per-key, replaces JSON file)
# ─────────────────────────────────────────────

def save_build_entry(key: str, entry: str):
    """Save a build history entry tied to this license key."""
    init_db()
    key_hash = hash_key(key)
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("INSERT INTO build_history (key_hash, timestamp, entry) VALUES (?, ?, ?)",
              (key_hash, datetime.utcnow().isoformat(), entry))
    conn.commit()
    conn.close()


def get_build_history(key: str, limit: int = 20) -> list:
    """Return the last N build history entries for this key."""
    init_db()
    key_hash = hash_key(key)
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("SELECT timestamp, entry FROM build_history WHERE key_hash = ? ORDER BY id DESC LIMIT ?",
              (key_hash, limit))
    rows = c.fetchall()
    conn.close()
    return [{"timestamp": r[0], "entry": r[1]} for r in rows]


def delete_user_data(key: str):
    """Permanently delete all build history for a key (called at day 45)."""
    init_db()
    key_hash = hash_key(key)
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("DELETE FROM build_history WHERE key_hash = ?", (key_hash,))
    c.execute("UPDATE licenses SET status = 'expired' WHERE key_hash = ?", (key_hash,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
#  EMAIL SYSTEM (Gmail SMTP)
# ─────────────────────────────────────────────

def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Core Gmail SMTP sender. Returns True on success."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{APP_NAME} <{GMAIL_ADDRESS}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PW)
            server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


def send_welcome_email(to_email: str, name: str, key: str) -> bool:
    subject = f"🔨 Welcome to {APP_NAME} — Your License Key Inside"
    html = f"""
    <div style="font-family:monospace;background:#0A0F1A;color:#E0E0FF;padding:40px;border-radius:12px;">
        <h1 style="color:#FF6B00;letter-spacing:3px;">THE BUILDER</h1>
        <p>Hey {name or 'Boss'},</p>
        <p>You're in. Here's your license key — keep it safe:</p>
        <div style="background:#1A1F2E;border:3px solid #FF6B00;border-radius:8px;padding:20px;
                    text-align:center;font-size:1.6rem;letter-spacing:4px;color:#FF6B00;margin:20px 0;">
            {key}
        </div>
        <p>Your license is active for <strong>30 days</strong>.</p>
        <p>Access the app here: <a href="{APP_URL}" style="color:#FF6B00;">{APP_URL}</a></p>
        <hr style="border-color:#FF6B0040;"/>
        <p style="font-size:0.85rem;color:#888;">
            You'll receive a renewal reminder before your key expires.<br/>
            Price: {PRICE}/month. Junk In → Robots Out.<br/>
            — Anthony, The Builder
        </p>
    </div>
    """
    return _send_email(to_email, subject, html)


def send_renewal_warning_email(to_email: str, name: str, days_left: int, stripe_url: str) -> bool:
    subject = f"⚠️ {APP_NAME} — Your license expires in {days_left} days"
    html = f"""
    <div style="font-family:monospace;background:#0A0F1A;color:#E0E0FF;padding:40px;border-radius:12px;">
        <h1 style="color:#FF6B00;letter-spacing:3px;">THE BUILDER</h1>
        <p>Hey {name or 'Boss'},</p>
        <p>Your <strong>{APP_NAME}</strong> license expires in <strong>{days_left} days</strong>.</p>
        <p>Renew now to keep all your build history and blueprints intact.</p>
        <div style="text-align:center;margin:30px 0;">
            <a href="{stripe_url}"
               style="background:linear-gradient(#FF6B00,#FF4B4B);color:#000;font-weight:700;
                      padding:14px 36px;border-radius:8px;text-decoration:none;font-size:1.1rem;">
               🔨 Renew for {PRICE}/month
            </a>
        </div>
        <p style="color:#FF4B4B;"><strong>Warning:</strong> If you don't renew within {days_left} days,
        your build history will be permanently deleted after 45 days.</p>
        <hr style="border-color:#FF6B0040;"/>
        <p style="font-size:0.85rem;color:#888;">— Anthony, The Builder</p>
    </div>
    """
    return _send_email(to_email, subject, html)


def send_deletion_warning_email(to_email: str, name: str, stripe_url: str) -> bool:
    subject = f"🚨 {APP_NAME} — Your data will be DELETED in 5 days"
    html = f"""
    <div style="font-family:monospace;background:#0A0F1A;color:#E0E0FF;padding:40px;border-radius:12px;">
        <h1 style="color:#FF4B4B;letter-spacing:3px;">⚠️ FINAL WARNING</h1>
        <p>Hey {name or 'Boss'},</p>
        <p>Your <strong>{APP_NAME}</strong> license has been expired for <strong>40 days</strong>.</p>
        <p style="color:#FF4B4B;font-size:1.1rem;"><strong>
            Your build history and all blueprints will be permanently deleted in 5 days.
        </strong></p>
        <p>This cannot be undone. Renew now to save everything:</p>
        <div style="text-align:center;margin:30px 0;">
            <a href="{stripe_url}"
               style="background:#FF4B4B;color:#fff;font-weight:700;
                      padding:14px 36px;border-radius:8px;text-decoration:none;font-size:1.1rem;">
               🚨 Save My Data — Renew Now
            </a>
        </div>
        <hr style="border-color:#FF6B0040;"/>
        <p style="font-size:0.85rem;color:#888;">— Anthony, The Builder</p>
    </div>
    """
    return _send_email(to_email, subject, html)


def send_deletion_complete_email(to_email: str, name: str, stripe_url: str) -> bool:
    subject = f"🗑️ {APP_NAME} — Your data has been deleted"
    html = f"""
    <div style="font-family:monospace;background:#0A0F1A;color:#E0E0FF;padding:40px;border-radius:12px;">
        <h1 style="color:#888;letter-spacing:3px;">THE BUILDER</h1>
        <p>Hey {name or 'Boss'},</p>
        <p>Your <strong>{APP_NAME}</strong> build history has been permanently deleted
           due to non-renewal after 45 days.</p>
        <p>You can still resubscribe and start fresh:</p>
        <div style="text-align:center;margin:30px 0;">
            <a href="{stripe_url}"
               style="background:linear-gradient(#FF6B00,#FF4B4B);color:#000;font-weight:700;
                      padding:14px 36px;border-radius:8px;text-decoration:none;font-size:1.1rem;">
               🔨 Resubscribe — {PRICE}/month
            </a>
        </div>
        <hr style="border-color:#FF6B0040;"/>
        <p style="font-size:0.85rem;color:#888;">— Anthony, The Builder</p>
    </div>
    """
    return _send_email(to_email, subject, html)


# ─────────────────────────────────────────────
#  LIFECYCLE CHECKER (run daily via scheduler)
# ─────────────────────────────────────────────

def run_daily_lifecycle(stripe_payment_url: str):
    """
    Call this once per day (cron / APScheduler / Streamlit background thread).
    Handles: 30-day warning, 40-day final warning, 45-day data deletion.
    """
    init_db()
    now  = datetime.utcnow()
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("SELECT key_hash, key_plain, email, name, expires_at, status FROM licenses")
    rows = conn.fetchall() if False else c.fetchall()
    conn.close()

    for key_hash, key_plain, email, name, expires_at, status in rows:
        if status == "revoked":
            continue

        expiry    = datetime.fromisoformat(expires_at)
        days_left = (expiry - now).days
        days_over = (now - expiry).days   # positive = past expiry

        # ── 30-day warning (10 days before expiry) ──────────────────
        if 0 <= days_left <= 10 and status == "active":
            send_renewal_warning_email(email, name, days_left, stripe_payment_url)
            _update_status(key_hash, "warned_30")

        # ── 40-day mark (10 days past expiry) ───────────────────────
        elif days_over >= 10 and status in ("active", "warned_30", "expired"):
            send_deletion_warning_email(email, name, stripe_payment_url)
            _update_status(key_hash, "warned_40")

        # ── 45-day mark — DELETE data ────────────────────────────────
        elif days_over >= 15 and status == "warned_40":
            delete_user_data(key_plain)
            send_deletion_complete_email(email, name, stripe_payment_url)


def _update_status(key_hash: str, status: str):
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("UPDATE licenses SET status = ? WHERE key_hash = ?", (status, key_hash))
    conn.commit()
    conn.close()