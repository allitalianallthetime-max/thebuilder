import os
import stripe
import psycopg2
from fastapi import FastAPI, Request, HTTPException, Header
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SEC = os.getenv("STRIPE_WEBHOOK_SEC")
DATABASE_URL = os.getenv("DATABASE_URL")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

stripe.api_key = STRIPE_SECRET_KEY

# ── Database Connection Manager ──────────────────────────────────────────────
@contextmanager
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ── Stripe Webhook Endpoint ──────────────────────────────────────────────────
@app.post("/webhook")
async def stripe_webhook(request: Request, sig_header: str = Header(None)):
    payload = await request.body()
    
    try:
        # Verify the signature to ensure it's actually from Stripe
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SEC
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session.get("customer_details", {}).get("email")
        
        # Logic to generate a new license key (Example: AB-1234)
        new_key = f"BUILDER-{os.urandom(4).hex().upper()}"
        
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO licenses (license_key, email, status, tier, expires_at) VALUES (%s, %s, %s, %s, %s)",
                    (new_key, customer_email, 'active', 'pro', '2030-01-01')
                )
                conn.commit()
                
        print(f"✅ Success: Created license {new_key} for {customer_email}")

    return {"status": "success"}
