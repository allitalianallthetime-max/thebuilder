"""
billing_service.py — The Cash Register
=========================================
Enterprise Billing with Redis Distributed Locks.
Prevents Stripe Webhook Race Conditions to protect revenue.
"""

import os
import secrets
import stripe
import httpx
import logging
import redis
from fastapi import FastAPI, Request, HTTPException, Header, Depends
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BILLING] %(levelname)s %(message)s")
log = logging.getLogger("billing")

app = FastAPI(title="The Builder - Billing Service")

STRIPE_SECRET_KEY  = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SEC = os.getenv("STRIPE_WEBHOOK_SEC")
INTERNAL_API_KEY   = os.getenv("INTERNAL_API_KEY")
APP_URL            = os.getenv("APP_URL", "https://builder-ui.onrender.com")

def normalize_url(raw: str, default: str) -> str:
    if not raw: return default
    raw = raw.strip()
    return raw if raw.startswith("http") else f"http://{raw}:10000"

AUTH_SERVICE_URL = normalize_url(os.getenv("AUTH_SERVICE_URL", ""), "http://builder-auth:10000")
REDIS_URL        = os.getenv("REDIS_URL", "redis://builder-redis:6379/0")

stripe.api_key = STRIPE_SECRET_KEY
HEADERS = {"X-Internal-Key": INTERNAL_API_KEY}

# ── 1. Redis for Distributed Webhook Locks ───────────────────────────────────
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    log.error(f"Redis connection failed: {e}")
    redis_client = None

PLANS = {
    "starter": {"name": "Starter", "price": 2900, "days": 30, "tier": "starter", "builds": 25, "description": "25 builds/month · Basic Round Table access"},
    "pro": {"name": "Pro Builder", "price": 4900, "days": 30, "tier": "pro", "builds": 100, "description": "100 builds/month · Full Round Table · Priority processing"},
    "master": {"name": "Master Forge", "price": 9900, "days": 30, "tier": "master", "builds": 999, "description": "Unlimited builds · All AI models · API access · White label"}
}

def verify_internal(x_internal_key: str = Header(None)):
    if not x_internal_key or not secrets.compare_digest(x_internal_key, INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Unauthorized")

async def provision_license(session: dict):
    session_id = session.get("id")
    customer_email = session.get("customer_details", {}).get("email") or session.get("customer_email")
    customer_name = session.get("customer_details", {}).get("name", "Builder")
    stripe_customer = session.get("customer", "")
    plan_key = session.get("metadata", {}).get("plan", "pro")
    plan = PLANS.get(plan_key, PLANS["pro"])

    if not customer_email: return

    # ── ENTERPRISE UPGRADE: REDIS DISTRIBUTED LOCK ──
    # Prevents Stripe from double-provisioning if they send the webhook twice
    if redis_client:
        lock_key = f"lock:stripe:provision:{session_id}"
        if not redis_client.set(lock_key, "locked", nx=True, ex=3600):
            log.warning(f"Webhook race condition prevented! Session {session_id} is already processing.")
            return

    log.info(f"Provisioning {plan['tier']} license for: {customer_email}")

    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        try:
            # 1. Create License
            auth_resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/create",
                json={"email": customer_email, "name": customer_name, "stripe_customer_id": stripe_customer, "days": plan["days"], "tier": plan["tier"], "notes": f"Stripe: {session_id}"}
            )
            auth_resp.raise_for_status()
            license_key = auth_resp.json()["key"]

            # 2. Queue Welcome Email
            await client.post(
                f"{AUTH_SERVICE_URL}/notify/queue",
                json={"type": "welcome", "to": customer_email, "name": customer_name, "payload": {"license_key": license_key, "tier": plan["tier"], "app_url": APP_URL}}
            )
            log.info(f"✅ Provisioning complete: {customer_email}")
        except Exception as e:
            log.error(f"Provisioning failed: {e}")
            if redis_client: redis_client.delete(f"lock:stripe:provision:{session_id}") # Unlock on failure

@app.get("/health")
def health(): return {"status": "healthy", "redis_lock": "active" if redis_client else "offline"}

@app.get("/plans")
def get_plans(): return {"plans": PLANS}

@app.post("/create-checkout", dependencies=[Depends(verify_internal)])
def create_checkout(plan_key: str):
    plan = PLANS.get(plan_key)
    if not plan: raise HTTPException(status_code=400, detail="Unknown plan")
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price_data": {"currency": "usd", "unit_amount": plan["price"], "product_data": {"name": f"The Builder — {plan['name']}", "description": plan["description"]}}, "quantity": 1}],
            mode="payment",
            success_url=f"{APP_URL}?payment=success",
            cancel_url=f"{APP_URL}?payment=cancelled",
            metadata={"plan": plan_key}
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, STRIPE_WEBHOOK_SEC)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    event_type = event["type"]
    if event_type == "checkout.session.completed":
        await provision_license(event["data"]["object"])
    # Add other webhook handlers here...

    return {"status": "received"}
