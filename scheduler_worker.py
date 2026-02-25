"""
scheduler_worker.py — The Morning Inspection
=============================================
Runs daily automated tasks:
- License lifecycle management
- Expiry warnings
- Welcome emails
- Data cleanup

Run via Render Cron Job:
  Command: python scheduler_worker.py
  Schedule: 0 8 * * *  (8am daily)
"""

import os
import json
import logging
import httpx
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCHEDULER] %(levelname)s %(message)s"
)
log = logging.getLogger("scheduler")

# ── Configuration ─────────────────────────────────────────────────────────────
AUTH_SERVICE_URL   = os.environ.get("AUTH_SERVICE_URL")
INTERNAL_API_KEY   = os.environ.get("INTERNAL_API_KEY")
RESEND_API_KEY     = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL         = os.environ.get("FROM_EMAIL", "The Builder <noreply@thebuilder.app>")
STRIPE_PAYMENT_URL = os.environ.get("STRIPE_PAYMENT_URL", "")
APP_URL            = os.environ.get("APP_URL", "")

if not all([AUTH_SERVICE_URL, INTERNAL_API_KEY]):
    log.critical("Missing AUTH_SERVICE_URL or INTERNAL_API_KEY. Exiting.")
    exit(1)

HEADERS = {"X-Internal-Key": INTERNAL_API_KEY}

# ── Email Templates ───────────────────────────────────────────────────────────
def build_welcome_html(name: str, license_key: str, tier: str, app_url: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<body style="background:#0a0a0a;color:#e8d5b0;font-family:Arial,sans-serif;padding:40px;">
  <div style="max-width:600px;margin:0 auto;border:1px solid #ff6600;padding:40px;">
    <h1 style="color:#ff6600;letter-spacing:4px;font-size:32px;">THE BUILDER</h1>
    <p style="color:#888;font-size:12px;letter-spacing:3px;">AoC3P0 SYSTEMS · FORGE ACCESS GRANTED</p>
    <hr style="border-color:#2a1500;"/>
    <h2 style="color:#e8d5b0;">Welcome to the Forge, {name}! 🔥</h2>
    <p>Your <strong style="color:#ff6600;">{tier.upper()} LICENSE</strong> is now active.</p>
    <div style="background:#1a1a1a;border:1px solid #ff6600;padding:20px;margin:20px 0;text-align:center;">
      <p style="color:#888;font-size:11px;letter-spacing:3px;">YOUR LICENSE KEY</p>
      <p style="color:#ff6600;font-size:24px;font-family:monospace;letter-spacing:4px;">{license_key}</p>
    </div>
    <p>Enter this key at <a href="{app_url}" style="color:#ff6600;">{app_url}</a> to access The Forge.</p>
    <p style="color:#888;font-size:11px;">The Round Table (Gemini, Grok & Claude) is standing by.<br/>
    Junk in. Robots out. Let's build. ⚙</p>
  </div>
</body>
</html>
"""

def build_expiry_warning_html(name: str, days_remaining: int, payment_url: str) -> str:
    urgency = "🔴 CRITICAL" if days_remaining <= 3 else "⚠️ WARNING"
    return f"""
<!DOCTYPE html>
<html>
<body style="background:#0a0a0a;color:#e8d5b0;font-family:Arial,sans-serif;padding:40px;">
  <div style="max-width:600px;margin:0 auto;border:1px solid #ff4400;padding:40px;">
    <h1 style="color:#ff6600;letter-spacing:4px;">THE BUILDER</h1>
    <hr style="border-color:#ff4400;"/>
    <h2 style="color:#ff4400;">{urgency}: License Expiring</h2>
    <p>Hey {name}, your Builder license expires in <strong style="color:#ff4400;">{days_remaining} day(s)</strong>.</p>
    <p>Renew now to keep the forge running:</p>
    <a href="{payment_url}"
       style="display:inline-block;background:#ff6600;color:#000;padding:14px 32px;
              text-decoration:none;font-weight:bold;letter-spacing:3px;margin:20px 0;">
      RENEW LICENSE →
    </a>
    <p style="color:#888;font-size:11px;">The Round Table will be waiting. ⚙</p>
  </div>
</body>
</html>
"""

# ── Email Sender ──────────────────────────────────────────────────────────────
def send_email(to_email: str, subject: str, html: str) -> bool:
    """Send email via Resend API."""
    if not RESEND_API_KEY:
        log.warning(f"No RESEND_API_KEY — email skipped for {to_email}")
        return False

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from":    FROM_EMAIL,
                    "to":      [to_email],
                    "subject": subject,
                    "html":    html
                }
            )
            if resp.status_code == 200:
                log.info(f"✅ Email sent → {to_email}")
                return True
            else:
                log.error(f"Email failed: {resp.status_code} — {resp.text}")
                return False
    except Exception as e:
        log.error(f"Email error: {e}")
        return False

# ── Phase 1: License Lifecycle ────────────────────────────────────────────────
def process_single_license(client: httpx.Client, lic: dict, now: datetime):
    expires_at     = datetime.fromisoformat(lic["expires_at"].replace("Z", ""))
    days_remaining = (expires_at - now).days

    if days_remaining < -15:
        # Past grace period — cleanup
        log.info(f"Scrapping expired data for {lic['email']} ({abs(days_remaining)}d overdue)")
        try:
            client.delete(f"{AUTH_SERVICE_URL}/auth/history/{lic['license_key']}")
        except Exception as e:
            log.error(f"Cleanup failed for {lic['license_key']}: {e}")

    elif days_remaining in [10, 5, 3, 1]:
        # Send expiry warning
        log.info(f"Sending expiry warning to {lic['email']} ({days_remaining}d left)")
        subject = f"⚠️ Builder License: {days_remaining} day(s) remaining"
        html    = build_expiry_warning_html(
            lic.get("name", "Builder"), days_remaining, STRIPE_PAYMENT_URL
        )
        send_email(lic["email"], subject, html)

def run_license_lifecycle():
    log.info("── Phase 1: License Lifecycle ────────────────────────────────")
    try:
        with httpx.Client(headers=HEADERS, timeout=20) as client:
            resp = client.get(f"{AUTH_SERVICE_URL}/admin/licenses")
            resp.raise_for_status()
            licenses = resp.json()
            now      = datetime.utcnow()

            log.info(f"Processing {len(licenses)} licenses...")
            for lic in licenses:
                try:
                    process_single_license(client, lic, now)
                except Exception as e:
                    log.error(f"Error processing {lic.get('license_key')}: {e}")

    except Exception as e:
        log.error(f"Could not connect to Auth Service: {e}")

# ── Phase 2: Notification Queue ───────────────────────────────────────────────
def run_notification_queue():
    log.info("── Phase 2: Notification Queue ───────────────────────────────")
    try:
        with httpx.Client(headers=HEADERS, timeout=20) as client:
            resp = client.get(f"{AUTH_SERVICE_URL}/notify/pending")
            resp.raise_for_status()
            notifications = resp.json()

            log.info(f"Processing {len(notifications)} pending notifications...")
            for notif in notifications:
                try:
                    payload = notif.get("payload", {})
                    sent    = False

                    if notif["type"] == "welcome":
                        html = build_welcome_html(
                            notif.get("name", "Builder"),
                            payload.get("license_key", ""),
                            payload.get("tier", "pro"),
                            payload.get("app_url", APP_URL)
                        )
                        sent = send_email(
                            notif["to"],
                            "🔥 Welcome to The Builder — Your License Key Inside",
                            html
                        )

                    elif notif["type"] == "payment_failed":
                        html = f"""
<h2>Payment Failed</h2>
<p>Hey {notif.get('name', 'Builder')}, your Builder payment failed.</p>
<p>Please update your payment method to keep the forge running.</p>
<a href="{STRIPE_PAYMENT_URL}">Update Payment →</a>
"""
                        sent = send_email(
                            notif["to"],
                            "⛔ Builder Payment Failed — Action Required",
                            html
                        )

                    if sent:
                        client.post(f"{AUTH_SERVICE_URL}/notify/mark-sent/{notif['id']}")

                except Exception as e:
                    log.error(f"Notification error for {notif.get('id')}: {e}")

    except Exception as e:
        log.error(f"Could not process notification queue: {e}")

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("══════════════════════════════════════════════════════")
    log.info("  THE BUILDER — MORNING INSPECTION STARTING")
    log.info(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log.info("══════════════════════════════════════════════════════")

    run_license_lifecycle()
    run_notification_queue()

    log.info("══════════════════════════════════════════════════════")
    log.info("  INSPECTION COMPLETE")
    log.info("══════════════════════════════════════════════════════")
