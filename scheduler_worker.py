"""
scheduler_worker.py — Enterprise Morning Inspection
===================================================
High-Concurrency Async Batch Processor.
- Expiry warnings (Retention)
- Win-back campaigns for churned users
- Welcome emails
- Admin Daily Digest (MRR & API Health)
"""

import os
import asyncio
import logging
import httpx
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SCHEDULER] %(message)s")
log = logging.getLogger("scheduler")

# ── Configuration ─────────────────────────────────────────────────────────────
def normalize_url(raw: str, default: str) -> str:
    if not raw: return default
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return f"http://{raw}:10000"

AUTH_SERVICE_URL   = normalize_url(os.environ.get("AUTH_SERVICE_URL", ""), "http://builder-auth:10000")
ADMIN_SERVICE_URL  = normalize_url(os.environ.get("ADMIN_SERVICE_URL", ""), "http://builder-admin:10000")
INTERNAL_API_KEY   = os.environ.get("INTERNAL_API_KEY")
MASTER_KEY         = os.environ.get("MASTER_KEY")
RESEND_API_KEY     = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL         = os.environ.get("FROM_EMAIL", "The Builder <noreply@thebuilder.app>")
ADMIN_EMAIL        = os.environ.get("ADMIN_EMAIL", "") # Optional: Add to Render environment to get daily reports!
STRIPE_PAYMENT_URL = os.environ.get("STRIPE_PAYMENT_URL", "")
APP_URL            = os.environ.get("APP_URL", "")

HEADERS = {"X-Internal-Key": INTERNAL_API_KEY}

# Limit concurrent emails to avoid Resend API rate limits
email_semaphore = asyncio.Semaphore(10)

# ── 1. Email Templates (Retention Optimized) ──────────────────────────────────
async def send_email(client: httpx.AsyncClient, to_email: str, subject: str, html: str) -> bool:
    if not RESEND_API_KEY:
        log.warning(f"Simulated Email to {to_email}: {subject}")
        return False
    
    async with email_semaphore:
        try:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": FROM_EMAIL, "to": [to_email], "subject": subject, "html": html}
            )
            if resp.status_code == 200:
                log.info(f"✅ Sent: {to_email} ({subject})")
                return True
            else:
                log.error(f"❌ Failed: {to_email} - {resp.text}")
                return False
        except Exception as e:
            log.error(f"❌ Network Error sending to {to_email}: {e}")
            return False

def html_wrapper(title: str, content: str, urgency_color: str = "#ff6600") -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <body style="background:#0a0a0a;color:#e8d5b0;font-family:Arial,sans-serif;padding:40px;">
      <div style="max-width:600px;margin:0 auto;border:1px solid {urgency_color};padding:40px;">
        <h1 style="color:{urgency_color};letter-spacing:4px;">THE BUILDER</h1>
        <hr style="border-color:{urgency_color};"/>
        {content}
      </div>
    </body>
    </html>
    """

# ── 2. The Massively Parallel Retention Engine ────────────────────────────────
async def process_single_license(client: httpx.AsyncClient, lic: dict, now: datetime):
    try:
        expires_at = datetime.fromisoformat(lic["expires_at"].replace("Z", ""))
        days_remaining = (expires_at - now).days

        # SCENARIO 1: The Win-Back Campaign (15 Days Expired)
        if days_remaining == -15:
            log.info(f"Triggering Win-Back Campaign for {lic['email']}")
            content = f"""
            <h2 style="color:#e8d5b0;">Your Garage is Locked.</h2>
            <p>Hey {lic.get('name', 'Builder')}, your license expired 15 days ago.</p>
            <p><strong>Don't worry — we didn't delete your blueprints.</strong> Your custom builds, AI parts lists, and schematics are safely locked in the database.</p>
            <p>Whenever you're ready to get back to the shop floor, just renew your license and pick up exactly where you left off.</p>
            <a href="{STRIPE_PAYMENT_URL}" style="display:inline-block;background:#ff6600;color:#000;padding:14px 32px;text-decoration:none;font-weight:bold;margin:20px 0;">RE-OPEN THE GARAGE →</a>
            """
            await send_email(client, lic["email"], "Your blueprints are safely locked away.", html_wrapper("Garage Locked", content, "#555"))

        # SCENARIO 2: Expiry Warnings
        elif days_remaining in [10, 5, 3, 1]:
            log.info(f"Sending expiry warning to {lic['email']} ({days_remaining}d left)")
            color = "#ff0000" if days_remaining == 1 else "#ffaa00"
            content = f"""
            <h2 style="color:{color};">License Expiring in {days_remaining} Days</h2>
            <p>Hey {lic.get('name', 'Builder')}, your access to the AI Round Table is about to close.</p>
            <p>Renew now so you don't lose access to the Forge:</p>
            <a href="{STRIPE_PAYMENT_URL}" style="display:inline-block;background:{color};color:#000;padding:14px 32px;text-decoration:none;font-weight:bold;margin:20px 0;">RENEW LICENSE →</a>
            """
            await send_email(client, lic["email"], f"Action Required: License expires in {days_remaining} days", html_wrapper("Expiry Warning", content, color))
    except Exception as e:
        log.error(f"Error processing license for {lic.get('email')}: {e}")

async def process_single_notification(client: httpx.AsyncClient, notif: dict):
    try:
        payload = notif.get("payload", {})
        sent = False

        if notif["type"] == "welcome":
            content = f"""
            <h2 style="color:#e8d5b0;">Welcome to the Forge, {notif.get('name', 'Builder')}! 🔥</h2>
            <p>Your <strong style="color:#ff6600;">{payload.get('tier', 'pro').upper()} LICENSE</strong> is now active.</p>
            <div style="background:#1a1a1a;border:1px solid #ff6600;padding:20px;margin:20px 0;text-align:center;">
              <p style="color:#888;font-size:11px;letter-spacing:3px;">YOUR LICENSE KEY</p>
              <p style="color:#ff6600;font-size:24px;font-family:monospace;letter-spacing:4px;">{payload.get('license_key', '')}</p>
            </div>
            <p>Enter this key at <a href="{APP_URL}" style="color:#ff6600;">{APP_URL}</a> to access The Forge.</p>
            <p style="color:#888;font-size:11px;">The Round Table (Gemini, Grok & Claude) is standing by.<br/>
            Junk in. Robots out. Let's build. ⚙</p>
            """
            sent = await send_email(client, notif["to"], "🔥 Welcome to The Builder — Your License Key Inside", html_wrapper("Welcome", content, "#ff6600"))

        elif notif["type"] == "payment_failed":
            content = f"""
            <h2 style="color:#ff4400;">Payment Failed</h2>
            <p>Hey {notif.get('name', 'Builder')}, your Builder payment failed.</p>
            <p>Please update your payment method to keep the forge running.</p>
            <a href="{STRIPE_PAYMENT_URL}" style="display:inline-block;background:#ff4400;color:#000;padding:14px 32px;text-decoration:none;font-weight:bold;margin:20px 0;">Update Payment →</a>
            """
            sent = await send_email(client, notif["to"], "⛔ Builder Payment Failed — Action Required", html_wrapper("Payment Failed", content, "#ff4400"))

        if sent:
            await client.post(f"{AUTH_SERVICE_URL}/notify/mark-sent/{notif['id']}", headers=HEADERS)

    except Exception as e:
        log.error(f"Notification error for {notif.get('id')}: {e}")

async def run_inspection():
    log.info("======================================================")
    log.info(f" THE BUILDER — ENTERPRISE INSPECTION STARTING ({datetime.utcnow()})")
    log.info("======================================================")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Phase 1: License Lifecycle & Churn Prevention
        log.info("── Analyzing Customer Retention ──────────────────────────────")
        try:
            resp = await client.get(f"{AUTH_SERVICE_URL}/admin/licenses", headers=HEADERS)
            resp.raise_for_status()
            licenses = resp.json()
            now = datetime.utcnow()

            # Execute safely in parallel
            tasks = [process_single_license(client, lic, now) for lic in licenses]
            await asyncio.gather(*tasks)
        except Exception as e:
            log.error(f"Failed to fetch licenses: {e}")

        # Phase 2: Notification Queue
        log.info("── Executing Notification Queue ──────────────────────────────")
        try:
            resp = await client.get(f"{AUTH_SERVICE_URL}/notify/pending", headers=HEADERS)
            resp.raise_for_status()
            notifications = resp.json()

            # Execute safely in parallel
            tasks = [process_single_notification(client, notif) for notif in notifications]
            await asyncio.gather(*tasks)
        except Exception as e:
            log.error(f"Failed to process notifications: {e}")
            
        # Phase 3: Founder Digest
        if ADMIN_EMAIL and MASTER_KEY:
            log.info("── Generating Admin Digest ───────────────────────────────────")
            try:
                resp = await client.get(f"{ADMIN_SERVICE_URL}/dashboard", headers={"x-master-key": MASTER_KEY})
                if resp.status_code == 200:
                    dash = resp.json()
                    fin = dash.get("financials", {})
                    builds = dash.get("builds", {})
                    
                    content = f"""
                    <h2 style="color:#00cc66;">Morning Inspection Complete</h2>
                    <p><strong>MRR:</strong> {fin.get('estimated_mrr')}</p>
                    <p><strong>Est. API Cost:</strong> {fin.get('est_api_costs_monthly')}</p>
                    <p><strong>Gross Margin:</strong> <span style="color:#00cc66;">{fin.get('gross_margin')}</span></p>
                    <br>
                    <p><strong>Builds Yesterday:</strong> {builds.get('today')}</p>
                    <p><strong>Total Builds:</strong> {builds.get('total')}</p>
                    <p><strong>Active Licenses:</strong> {dash.get('licenses', {}).get('active')}</p>
                    """
                    await send_email(client, ADMIN_EMAIL, f"Daily Forge Report: {fin.get('estimated_mrr')} MRR", html_wrapper("Admin Digest", content, "#00cc66"))
            except Exception as e:
                log.error(f"Failed to generate admin digest: {e}")

    log.info("======================================================")
    log.info(" INSPECTION COMPLETE. FORGE IS SECURE.")
    log.info("======================================================")

if __name__ == "__main__":
    asyncio.run(run_inspection())
