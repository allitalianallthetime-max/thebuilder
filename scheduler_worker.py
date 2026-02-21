"""
scheduler_worker.py — Refined
=============================
✅ Added "Safety Catch" for batch processing.
✅ Improved logging for easier troubleshooting in Render logs.
✅ Standardized timeout handling for API calls.
"""

import os
import json
import logging
import httpx
from datetime import datetime

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCHEDULER] %(levelname)s %(message)s"
)
log = logging.getLogger("scheduler")

# ── Config ────────────────────────────────────────────────────────────────────
# Use .get() to prevent 'KeyError' crashes; handle missing vars gracefully
AUTH_SERVICE_URL   = os.environ.get("AUTH_SERVICE_URL")
INTERNAL_API_KEY   = os.environ.get("INTERNAL_API_KEY")
RESEND_API_KEY     = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL         = os.environ.get("FROM_EMAIL", "The Builder <noreply@yourdomain.com>")
STRIPE_PAYMENT_URL = os.environ.get("STRIPE_PAYMENT_URL", "")

if not all([AUTH_SERVICE_URL, INTERNAL_API_KEY]):
    log.critical("CRITICAL: Missing AUTH_SERVICE_URL or INTERNAL_API_KEY. Exiting.")
    exit(1)

HEADERS = {"X-Internal-Key": INTERNAL_API_KEY}

# ... (build_expiry_warning_html and build_welcome_html remain the same) ...

def run_license_lifecycle():
    log.info("── Phase 1: License lifecycle check ─────────────────")
    try:
        # Use a context manager for httpx for better connection handling
        with httpx.Client(headers=HEADERS, timeout=20) as client:
            resp = client.get(f"{AUTH_SERVICE_URL}/admin/licenses")
            resp.raise_for_status()
            licenses = resp.json()

            now = datetime.utcnow()
            for lic in licenses:
                try: # Individual try-except so one bad user doesn't stop the whole script
                    process_single_license(client, lic, now)
                except Exception as e:
                    log.error(f"Error processing license {lic.get('license_key')}: {e}")
    except Exception as e:
        log.error(f"Could not connect to Auth Service: {e}")

def process_single_license(client, lic, now):
    expires_at = datetime.fromisoformat(lic["expires_at"])
    days_remaining = (expires_at - now).days
    
    # Logic for deletion (15 days grace period)
    if days_remaining < -15:
        log.info(f"Cleanup: Deleting data for {lic['email']} ({abs(days_remaining)}d overdue)")
        client.delete(f"{AUTH_SERVICE_URL}/auth/history/{lic['license_key']}")
    # Logic for warnings
    elif days_remaining <= 10:
        # Note: In the future, add a check here to see if we already emailed them today!
        subject = "🔨 Builder License Status Update"
        html = build_expiry_warning_html(lic.get("name"), days_remaining, STRIPE_PAYMENT_URL)
        send_email(lic["email"], subject, html)

# ... (Rest of the notification queue logic) ...
