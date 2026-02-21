"""
stripe_webhook.py — The Builder Payment Listener
================================================
✅ Handles automated license creation upon payment.
✅ Pulls customer names for a personalized welcome.
✅ Includes robust error logging for troubleshooting.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import stripe
import os
import logging
from key_manager import create_license, send_welcome_email

# ── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [STRIPE] %(levelname)s %(message)s")
log = logging.getLogger("stripe_webhook")

app = FastAPI()

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SEC", "")

@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except Exception as e:
        log.error(f"⚠️ Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the successful payment event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        
        # Get customer details
        customer_email = session.get("customer_details", {}).get("email") or session.get("customer_email")
        customer_name  = session.get("customer_details", {}).get("name", "Boss")

        if customer_email:
            try:
                # 1. Create the license in your DB
                new_key = create_license(
                    email=customer_email, 
                    name=customer_name, 
                    stripe_session=session["id"]
                )
                
                # 2. Fire off the welcome email
                email_sent = send_welcome_email(customer_email, customer_name, new_key)
                
                if email_sent:
                    log.info(f"✅ SUCCESS: License {new_key} sent to {customer_email}")
                else:
                    log.warning(f"⚠️ License created for {customer_email}, but EMAIL FAILED.")
            
            except Exception as e:
                log.error(f"❌ CRITICAL: Failed to process order for {customer_email}: {e}")
                # We return a 500 so Stripe retries the webhook later
                raise HTTPException(status_code=500, detail="Internal processing error")

    return JSONResponse({"status": "success"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
