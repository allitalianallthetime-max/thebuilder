"""
billing_service.py — The Builder Billing Service
=================================================
FastAPI service that handles Stripe webhooks and auto-provisions license keys.

Deploy on Render as a separate Web Service.
Set env vars: STRIPE_WEBHOOK_SEC, STRIPE_SECRET_KEY, AUTH_SERVICE_URL,
              NOTIFY_SERVICE_URL (optional), INTERNAL_API_KEY
"""

import os
import logging
import httpx
import stripe

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [BILLING] %(levelname)s %(message)s")
log = logging.getLogger("billing")

# ── Config ────────────────────────────────────────────────────────────────────
STRIPE_WEBHOOK_SEC  = os.environ["STRIPE_WEBHOOK_SEC"]       # from Stripe dashboard
STRIPE_SECRET_KEY   = os.environ["STRIPE_SECRET_KEY"]        # sk_live_...
AUTH_SERVICE_URL    = os.environ["AUTH_SERVICE_URL"]          # e.g. https://builder-auth.onrender.com
INTERNAL_API_KEY    = os.environ["INTERNAL_API_KEY"]          # shared secret between services
APP_URL             = os.environ.get("APP_URL", "")           # Streamlit app URL for redirect

stripe.api_key = STRIPE_SECRET_KEY

app = FastAPI(title="Builder Billing Service", docs_url=None, redoc_url=None)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """Render health check endpoint."""
    return {"status": "ok", "service": "billing"}


# ── Stripe Webhook ────────────────────────────────────────────────────────────
@app.post("/stripe-webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """
    Receive and verify Stripe webhook events.
    Handles: checkout.session.completed, customer.subscription.deleted
    """
    payload = await request.body()

    # Verify Stripe signature — reject anything unsigned
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, STRIPE_WEBHOOK_SEC)
    except stripe.error.SignatureVerificationError:
        log.warning("Invalid Stripe signature — request rejected")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        log.error(f"Webhook parse error: {e}")
        raise HTTPException(status_code=400, detail="Bad payload")

    log.info(f"Stripe event received: {event['type']} — id: {event['id']}")

    # ── Handle events ─────────────────────────────────────────────────────────
    if event["type"] == "checkout.session.completed":
        await handle_checkout_completed(event["data"]["object"])

    elif event["type"] == "customer.subscription.deleted":
        await handle_subscription_cancelled(event["data"]["object"])

    elif event["type"] == "invoice.payment_failed":
        await handle_payment_failed(event["data"]["object"])

    # Always return 200 to Stripe — retries happen on non-200
    return JSONResponse({"received": True})


async def handle_checkout_completed(session: dict):
    """
    New subscriber paid. Create a license key and queue a welcome email.
    Stripe sends: customer_email, customer_details, metadata (if set in payment link).
    """
    customer_email = (
        session.get("customer_details", {}).get("email")
        or session.get("customer_email")
        or ""
    )
    customer_name = session.get("customer_details", {}).get("name", "")
    stripe_customer_id = session.get("customer", "")

    if not customer_email:
        log.error(f"checkout.session.completed has no email — session id: {session.get('id')}")
        return

    log.info(f"New subscriber: {customer_email} ({customer_name})")

    # Call Auth Service to create the license
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/create",
                json={
                    "email":              customer_email,
                    "name":               customer_name,
                    "stripe_customer_id": stripe_customer_id,
                    "days":               30,
                    "notes":              f"Auto-provisioned via Stripe checkout {session.get('id')}",
                },
                headers={"X-Internal-Key": INTERNAL_API_KEY},
            )
            resp.raise_for_status()
            data = resp.json()
            license_key = data["key"]
            log.info(f"License created: {license_key} for {customer_email}")

        except httpx.HTTPStatusError as e:
            log.error(f"Auth Service returned {e.response.status_code}: {e.response.text}")
            return
        except Exception as e:
            log.error(f"Failed to call Auth Service: {e}")
            return

    # Queue welcome email via Auth Service notification endpoint
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(
                f"{AUTH_SERVICE_URL}/notify/queue",
                json={
                    "type":    "welcome",
                    "to":      customer_email,
                    "name":    customer_name,
                    "payload": {
                        "license_key": license_key,
                        "app_url":     APP_URL,
                    },
                },
                headers={"X-Internal-Key": INTERNAL_API_KEY},
            )
            log.info(f"Welcome email queued for {customer_email}")
        except Exception as e:
            # Non-fatal — key was created, email just didn't queue
            log.warning(f"Could not queue welcome email: {e}")


async def handle_subscription_cancelled(subscription: dict):
    """Customer cancelled. Revoke their license key."""
    stripe_customer_id = subscription.get("customer", "")
    if not stripe_customer_id:
        return

    log.info(f"Subscription cancelled for Stripe customer: {stripe_customer_id}")

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(
                f"{AUTH_SERVICE_URL}/auth/revoke-by-stripe-id",
                json={"stripe_customer_id": stripe_customer_id, "reason": "subscription_cancelled"},
                headers={"X-Internal-Key": INTERNAL_API_KEY},
            )
        except Exception as e:
            log.error(f"Failed to revoke license for {stripe_customer_id}: {e}")


async def handle_payment_failed(invoice: dict):
    """Payment failed — warn user, don't revoke yet (Stripe retries)."""
    customer_email = invoice.get("customer_email", "")
    log.info(f"Payment failed for {customer_email} — Stripe will retry")
    # Stripe handles retries. After max retries it fires subscription.deleted.
    # No action needed here unless you want to send a custom warning email.
