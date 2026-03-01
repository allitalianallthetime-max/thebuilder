"""
scheduler_worker.py — Enterprise Morning Inspection
===================================================
High-Concurrency Async Batch Processor.
Uses Gmail SMTP for Welcome Emails and Churn Prevention.
"""

import os
import asyncio
import logging
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SCHEDULER] %(message)s")
log = logging.getLogger("scheduler")

# ── Configuration ─────────────────────────────────────────────────────────────
def normalize_url(raw: str, default: str) -> str:
    if not raw: return default
    raw = raw.strip()
    return raw if raw.startswith("http") else f"http://{raw}:10000"

AUTH_SERVICE_URL   = normalize_url(os.getenv("AUTH_SERVICE_URL", ""), "http://builder-auth:10000")
ADMIN_SERVICE_URL  = normalize_url(os.getenv("ADMIN_SERVICE_URL", ""), "http://builder-admin:10000")
INTERNAL_API_KEY   = os.getenv("INTERNAL_API_KEY")
STRIPE_PAYMENT_URL = os.getenv("STRIPE_PAYMENT_URL", "")
APP_URL            = os.getenv("APP_URL", "")

# GMAIL CONFIG
GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PW       = os.getenv("GMAIL_APP_PW")

HEADERS = {"X-Internal-Key": INTERNAL_API_KEY}

# Limit concurrent emails to avoid Google SMTP rate limits (Max ~100 per minute)
email_semaphore = asyncio.Semaphore(5)

# ── 1. NATIVE GMAIL SENDER ────────────────────────────────────────────────────
async def send_email(to_email: str, subject: str, html: str) -> bool:
    if not GMAIL_ADDRESS or not GMAIL_APP_PW:
        log.warning(f"No Gmail credentials. Simulated Email to {to_email}: {subject}")
        return False
    
    async with email_semaphore:
        try:
            # We run the synchronous SMTP blocking code in a thread so it doesn't freeze the async loop
            def _send():
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"The Builder <{GMAIL_ADDRESS}>"
                msg["To"] = to_email
                msg.attach(MIMEText(html, "html"))
                
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                    server.login(GMAIL_ADDRESS, GMAIL_APP_PW)
                    server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())

            await asyncio.to_thread(_send)
            log.info(f"✅ Gmail Sent: {to_email} ({subject})")
            return True
        except Exception as e:
            log.error(f"❌ Gmail SMTP Error sending to {to_email}: {e}")
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

        # Win-Back Campaign
        if days_remaining == -15:
            content = f"""
            <h2 style="color:#e8d5b0;">Your Garage is Locked.</h2>
            <p>Hey {lic.get('name', 'Builder')}, your license expired 15 days ago.</p>
            <p><strong>We didn't delete your blueprints.</strong> Your custom builds are safely locked in the database.</p>
            <a href="{STRIPE_PAYMENT_URL}" style="display:inline-block;background:#ff6600;color:#000;padding:14px 32px;text-decoration:none;font-weight:bold;margin:20px 0;">RE-OPEN THE GARAGE →</a>
            """
            await send_email(lic["email"], "Your blueprints are safely locked away.", html_wrapper("Garage Locked", content, "#555"))

        # Expiry Warnings
        elif days_remaining in [10, 5, 3, 1]:
            color = "#ff0000" if days_remaining == 1 else "#ffaa00"
            content = f"""
            <h2 style="color:{color};">License Expiring in {days_remaining} Days</h2>
            <p>Hey {lic.get('name', 'Builder')}, your access to the AI Round Table is about to close.</p>
            <a href="{STRIPE_PAYMENT_URL}" style="display:inline-block;background:{color};color:#000;padding:14px 32px;text-decoration:none;font-weight:bold;margin:20px 0;">RENEW LICENSE →</a>
            """
            await send_email(lic["email"], f"Action Required: License expires in {days_remaining} days", html_wrapper("Expiry Warning", content, color))
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
            """
            sent = await send_email(notif["to"], "🔥 Welcome to The Builder — Your License Key Inside", html_wrapper("Welcome", content, "#ff6600"))

        if sent:
            await client.post(f"{AUTH_SERVICE_URL}/notify/mark-sent/{notif['id']}", headers=HEADERS)
    except Exception as e:
        log.error(f"Notification error for {notif.get('id')}: {e}")

async def run_inspection():
    log.info("======================================================")
    log.info(" THE BUILDER — ENTERPRISE INSPECTION STARTING")
    log.info("======================================================")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(f"{AUTH_SERVICE_URL}/admin/licenses", headers=HEADERS)
            if resp.status_code == 200:
                licenses = resp.json()
                await asyncio.gather(*[process_single_license(client, lic, datetime.utcnow()) for lic in licenses])
        except Exception as e: log.error(f"Failed to fetch licenses: {e}")

        try:
            resp = await client.get(f"{AUTH_SERVICE_URL}/notify/pending", headers=HEADERS)
            if resp.status_code == 200:
                notifications = resp.json()
                await asyncio.gather(*[process_single_notification(client, notif) for notif in notifications])
        except Exception as e: log.error(f"Failed to process notifications: {e}")
            
    log.info("INSPECTION COMPLETE. FORGE IS SECURE.")

if __name__ == "__main__":
    asyncio.run(run_inspection())
