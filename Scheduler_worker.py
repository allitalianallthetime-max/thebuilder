"""
scheduler_worker.py — The Builder Scheduler Worker
===================================================
Standalone script run as a Render Cron Job (daily).
Handles: license expiry warnings, data deletion, and email notification processing.

Deploy on Render as a Cron Job: `python scheduler_worker.py`
Schedule: 0 9 * * * (9am UTC daily)

Set env vars: AUTH_SERVICE_URL, INTERNAL_API_KEY, RESEND_API_KEY,
              FROM_EMAIL, APP_URL, STRIPE_PAYMENT_URL
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
AUTH_SERVICE_URL  = os.environ["AUTH_SERVICE_URL"]
INTERNAL_API_KEY  = os.environ["INTERNAL_API_KEY"]
RESEND_API_KEY    = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL        = os.environ.get("FROM_EMAIL", "The Builder <noreply@yourdomain.com>")
APP_URL           = os.environ.get("APP_URL", "")
STRIPE_PAYMENT_URL = os.environ.get("STRIPE_PAYMENT_URL", "")

HEADERS = {"X-Internal-Key": INTERNAL_API_KEY}


# ── Email sending ─────────────────────────────────────────────────────────────
def send_email(to: str, subject: str, html: str) -> bool:
    if not RESEND_API_KEY:
        log.warning("RESEND_API_KEY not set — skipping email")
        return False
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={"from": FROM_EMAIL, "to": [to], "subject": subject, "html": html},
            timeout=15,
        )
        if resp.status_code in (200, 201):
            log.info(f"Email sent to {to}: {subject}")
            return True
        else:
            log.error(f"Resend returned {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        log.error(f"Email error to {to}: {e}")
        return False


def build_expiry_warning_html(name: str, days_left: int, payment_url: str) -> str:
    color = "#FF6B00" if days_left > 0 else "#FF4B4B"
    msg   = f"expires in <strong>{days_left} day(s)</strong>" if days_left > 0 else f"expired <strong>{abs(days_left)} day(s) ago</strong>"
    return f"""
<div style="font-family:monospace;background:#0D1117;color:#C8D4E8;
            padding:32px;border-radius:8px;max-width:560px;margin:auto;">
    <h2 style="color:{color};letter-spacing:3px;margin-top:0;">
        ⚠️ THE BUILDER — LICENSE {('WARNING' if days_left > 0 else 'EXPIRED')}
    </h2>
    <p>Hey {name or 'Boss'},</p>
    <p>Your Builder subscription {msg}.</p>
    <p>Renew now to keep your build history and forge access.</p>
    <a href="{payment_url}" style="display:block;background:linear-gradient(135deg,#B84400,#FF6B00);
       color:#fff;text-align:center;padding:14px;border-radius:4px;
       font-size:1rem;letter-spacing:3px;text-decoration:none;margin:24px 0;">
       🔨 RENEW — $29.99/MO
    </a>
    <p style="color:#7A8BA0;font-size:0.85rem;">Anthony, what's next boss?</p>
</div>
"""


def build_welcome_html(name: str, license_key: str, app_url: str) -> str:
    return f"""
<div style="font-family:monospace;background:#0D1117;color:#C8D4E8;
            padding:32px;border-radius:8px;max-width:560px;margin:auto;">
    <h2 style="color:#FF6B00;letter-spacing:3px;margin-top:0;">
        🔨 THE BUILDER — LICENSE KEY
    </h2>
    <p>Hey {name or 'Boss'},</p>
    <p>Your license key is ready. Paste it into the sidebar to unlock The Builder.</p>
    <div style="background:#1C2333;border:1px solid #FF6B00;border-radius:4px;
                padding:18px;font-size:1.3rem;letter-spacing:4px;color:#FF8C00;
                text-align:center;margin:24px 0;">
        {license_key}
    </div>
    <p style="color:#7A8BA0;font-size:0.85rem;line-height:1.7;">
        Subscription renews monthly at $29.99.<br/>
        Reply to this email with any questions.
    </p>
    <p style="color:#FF6B00;margin-bottom:0;">Anthony, what's next boss?</p>
</div>
"""


# ── Phase 1: License lifecycle ─────────────────────────────────────────────────
def run_license_lifecycle():
    """Check all licenses and send warning emails or delete expired data."""
    log.info("── Phase 1: License lifecycle check ─────────────────")

    try:
        resp = httpx.get(f"{AUTH_SERVICE_URL}/admin/licenses", headers=HEADERS, timeout=15)
        resp.raise_for_status()
        licenses = resp.json()
    except Exception as e:
        log.error(f"Could not fetch licenses: {e}")
        return

    now = datetime.utcnow()
    warned = expired_deleted = active = 0

    for lic in licenses:
        if lic["status"] == "revoked":
            continue

        expires_at    = datetime.fromisoformat(lic["expires_at"])
        days_remaining = (expires_at - now).days
        email          = lic["email"]
        name           = lic.get("name", "")
        key            = lic["license_key"]

        if days_remaining <= 10 and days_remaining >= 0:
            # Expiry warning
            log.info(f"Expiry warning: {email} ({days_remaining}d left)")
            subject = f"⚠️ Builder license expires in {days_remaining} day(s)"
            html    = build_expiry_warning_html(name, days_remaining, STRIPE_PAYMENT_URL)
            send_email(email, subject, html)
            warned += 1

        elif days_remaining < 0 and days_remaining >= -15:
            # Post-expiry warning
            days_over = abs(days_remaining)
            days_to_deletion = 15 - days_over
            log.info(f"Post-expiry warning: {email} ({days_over}d over, {days_to_deletion}d to deletion)")
            subject = f"🚨 Builder license expired — data deleted in {days_to_deletion} day(s)"
            html    = build_expiry_warning_html(name, days_remaining, STRIPE_PAYMENT_URL)
            send_email(email, subject, html)
            warned += 1

        elif days_remaining < -15:
            # Delete user data
            log.info(f"Deleting expired user data: {email} ({abs(days_remaining)}d over)")
            try:
                del_resp = httpx.delete(
                    f"{AUTH_SERVICE_URL}/auth/history/{key}",
                    headers=HEADERS,
                    timeout=10
                )
                del_resp.raise_for_status()
                expired_deleted += 1
            except Exception as e:
                log.error(f"Failed to delete data for {key}: {e}")

        else:
            active += 1

    log.info(f"Lifecycle done — active: {active}, warned: {warned}, deleted: {expired_deleted}")


# ── Phase 2: Process notification queue ──────────────────────────────────────
def process_notification_queue():
    """Drain the notification queue — send pending emails with retry tracking."""
    log.info("── Phase 2: Processing notification queue ────────────")

    try:
        resp = httpx.get(f"{AUTH_SERVICE_URL}/notify/pending", headers=HEADERS, timeout=10)
        resp.raise_for_status()
        jobs = resp.json()
    except Exception as e:
        log.error(f"Could not fetch notification queue: {e}")
        return

    if not jobs:
        log.info("No pending notifications")
        return

    log.info(f"Processing {len(jobs)} notification job(s)")
    sent = failed = 0

    for job in jobs:
        job_id   = job["id"]
        job_type = job["type"]
        to       = job["to_email"]
        name     = job.get("name", "")

        try:
            payload = json.loads(job.get("payload", "{}"))
        except json.JSONDecodeError:
            payload = {}

        # Build the right email
        if job_type == "welcome":
            subject = "🔨 Your Builder License Key"
            html    = build_welcome_html(name, payload.get("license_key", ""), APP_URL)
        elif job_type == "expiry_warning":
            days_left = payload.get("days_remaining", 0)
            subject   = f"⚠️ Builder license expires in {days_left} day(s)"
            html      = build_expiry_warning_html(name, days_left, STRIPE_PAYMENT_URL)
        elif job_type == "final_warning":
            days_over = payload.get("days_over", 0)
            subject   = f"🚨 Builder license expired — action required"
            html      = build_expiry_warning_html(name, -days_over, STRIPE_PAYMENT_URL)
        else:
            log.warning(f"Unknown notification type: {job_type} — skipping job {job_id}")
            continue

        ok = send_email(to, subject, html)

        # Report result back to Auth Service
        try:
            if ok:
                httpx.post(f"{AUTH_SERVICE_URL}/notify/mark-sent/{job_id}", headers=HEADERS, timeout=5)
                sent += 1
            else:
                httpx.post(f"{AUTH_SERVICE_URL}/notify/mark-failed/{job_id}", headers=HEADERS, timeout=5)
                failed += 1
        except Exception as e:
            log.error(f"Could not update job {job_id} status: {e}")

    log.info(f"Notifications done — sent: {sent}, failed: {failed}")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("═══════════════════════════════════════════════")
    log.info("  THE BUILDER — SCHEDULER WORKER STARTING")
    log.info(f"  {datetime.utcnow().isoformat()[:19]} UTC")
    log.info("═══════════════════════════════════════════════")

    run_license_lifecycle()
    process_notification_queue()

    log.info("═══════════════════════════════════════════════")
    log.info("  SCHEDULER WORKER COMPLETE")
    log.info("═══════════════════════════════════════════════")
