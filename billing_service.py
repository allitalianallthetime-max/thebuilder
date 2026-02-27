"""
billing_service.py — The Cash Register
=========================================
Handles all Stripe payments and license provisioning.
Merged with stripe_webhook.py for clean architecture.

Endpoints:
- POST /webhook          — Stripe webhook receiver
- GET  /plans            — Available pricing plans
- POST /create-checkout  — Create Stripe checkout session
- GET  /health
"""

import os
import secrets
import stripe
import httpx
import logging
from fastapi import FastAPI, Request, HTTPException, Header
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BILLING] %(levelname)s %(message)s")
log = logging.getLogger("billing")

app = FastAPI()

# ── Configuration ─────────────────────────────────────────────────────────────
STRIPE_SECRET_KEY  = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SEC = os.getenv("STRIPE_WEBHOOK_SEC")
INTERNAL_API_KEY   = os.getenv("INTERNAL_API_KEY")
APP_URL            = os.getenv("APP_URL", "https://builder-ui.onrender.com")

def normalize_url(raw: str, default: str) -> str:
    if not raw:
        return default
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return f"http://{raw}:10000"

AUTH_SERVICE_URL   = normalize_url(os.getenv("AUTH_SERVICE_URL", ""), "http://builder-auth:10000")

stripe.api_key = STRIPE_SECRET_KEY

HEADERS = {"X-Internal-Key": INTERNAL_API_KEY}

# ── Pricing Plans ─────────────────────────────────────────────────────────────
PLANS = {
    "starter": {
        "name":        "Starter",
        "price":       2900,   # cents
        "days":        30,
        "tier":        "starter",
        "builds":      25,
        "description": "25 builds/month · Basic Round Table access"
    },
    "pro": {
        "name":        "Pro Builder",
        "price":       4900,
        "days":        30,
        "tier":        "pro",
        "builds":      100,
        "description": "100 builds/month · Full Round Table · Priority processing"
    },
    "master": {
        "name":        "Master Forge",
        "price":       9900,
        "days":        30,
        "tier":        "master",
        "builds":      999,
        "description": "Unlimited builds · All AI models · API access · White label"
    }
}

# ── Provision License After Payment ──────────────────────────────────────────
async def provision_license(session: dict):
    """Called after successful Stripe payment — creates license and queues welcome email."""
    session_id        = session.get("id")
    customer_email    = session.get("customer_details", {}).get("email") or session.get("customer_email")
    customer_name     = session.get("customer_details", {}).get("name", "Builder")
    stripe_customer   = session.get("customer", "")
    plan_key          = session.get("metadata", {}).get("plan", "pro")
    plan              = PLANS.get(plan_key, PLANS["pro"])

    if not customer_email:
        log.error(f"Payment received but no email found. Session: {session_id}")
        return

    log.info(f"Provisioning {plan['tier']} license for: {customer_email}")

    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        try:
            # ── 1.9: Idempotency check — prevent duplicate licenses from webhook replays ──
            check_resp = await client.get(
                f"{AUTH_SERVICE_URL}/auth/check-session/{session_id}"
            )
            if check_resp.status_code == 200 and check_resp.json().get("provisioned"):
                existing = check_resp.json()
                log.warning(f"⚠️ License already provisioned for session {session_id}: "
                           f"{existing['license_key']} → {existing['email']}. Skipping.")
                return

            # 1. Create the license
            auth_resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/create",
                json={
                    "email":              customer_email,
                    "name":               customer_name,
                    "stripe_customer_id": stripe_customer,
                    "days":               plan["days"],
                    "tier":               plan["tier"],
                    "notes":              f"Stripe Session: {session_id} | Plan: {plan_key}"
                }
            )
            auth_resp.raise_for_status()
            license_data = auth_resp.json()
            license_key  = license_data["key"]

            # 2. Queue welcome email
            await client.post(
                f"{AUTH_SERVICE_URL}/notify/queue",
                json={
                    "type":    "welcome",
                    "to":      customer_email,
                    "name":    customer_name,
                    "payload": {
                        "license_key": license_key,
                        "tier":        plan["tier"],
                        "builds":      plan["builds"],
                        "app_url":     APP_URL
                    }
                }
            )

            log.info(f"✅ Provisioning complete — Key: {license_key} → {customer_email}")

        except httpx.HTTPStatusError as e:
            log.error(f"Service error during provisioning: {e.response.status_code} — {e.response.text}")
        except Exception as e:
            log.error(f"Provisioning failed: {e}")

async def handle_subscription_cancelled(subscription: dict):
    """Deactivate license when subscription is cancelled."""
    customer_id = subscription.get("customer")
    log.info(f"Subscription cancelled for customer: {customer_id}")

    if not customer_id:
        log.error("Subscription cancelled event has no customer ID")
        return

    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        try:
            resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/deactivate-by-customer",
                json={
                    "stripe_customer_id": customer_id,
                    "reason": f"Stripe subscription cancelled: {subscription.get('id', 'unknown')}"
                }
            )
            resp.raise_for_status()
            result = resp.json()
            deactivated = result.get("deactivated", 0)

            if deactivated > 0:
                log.info(f"✅ Deactivated {deactivated} license(s) for customer {customer_id}")
                # Queue cancellation emails
                for lic in result.get("licenses", []):
                    try:
                        await client.post(
                            f"{AUTH_SERVICE_URL}/notify/queue",
                            json={
                                "type": "subscription_cancelled",
                                "to":   lic["email"],
                                "name": "Builder",
                                "payload": {"app_url": APP_URL}
                            }
                        )
                    except Exception:
                        pass
            else:
                log.warning(f"No active licenses found for customer {customer_id}")

        except Exception as e:
            log.error(f"Failed to deactivate licenses for customer {customer_id}: {e}")

async def handle_payment_failed(invoice: dict):
    """Queue payment failed notification."""
    customer_email = invoice.get("customer_email")
    if customer_email:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
            try:
                await client.post(
                    f"{AUTH_SERVICE_URL}/notify/queue",
                    json={
                        "type":    "payment_failed",
                        "to":      customer_email,
                        "name":    "Builder",
                        "payload": {"app_url": APP_URL}
                    }
                )
            except Exception as e:
                log.error(f"Failed to queue payment failed email: {e}")

# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "stripe": "connected"}

@app.get("/plans")
async def get_plans():
    """Public endpoint — returns available pricing plans."""
    return {"plans": PLANS}

@app.post("/create-checkout")
async def create_checkout(
    plan_key: str,
    x_internal_key: str = Header(None)
):
    """Create a Stripe checkout session for the given plan."""
    if not x_internal_key or not INTERNAL_API_KEY or \
       not secrets.compare_digest(x_internal_key, INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Unauthorized")

    plan = PLANS.get(plan_key)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan_key}")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency":     "usd",
                    "unit_amount":  plan["price"],
                    "product_data": {
                        "name":        f"The Builder — {plan['name']}",
                        "description": plan["description"]
                    }
                },
                "quantity": 1
            }],
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
    """Stripe webhook — receives and processes all payment events."""
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SEC
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    event_type = event["type"]
    log.info(f"Stripe event received: {event_type}")

    if event_type == "checkout.session.completed":
        await provision_license(event["data"]["object"])

    elif event_type == "customer.subscription.deleted":
        await handle_subscription_cancelled(event["data"]["object"])

    elif event_type == "invoice.payment_failed":
        await handle_payment_failed(event["data"]["object"])

    return {"status": "received", "type": event_type}
