from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import stripe
import os
from key_manager import create_license, send_welcome_email

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
    except:
        raise HTTPException(status_code=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email")
        if customer_email:
            new_key = create_license(email=customer_email, name="", stripe_session=session["id"])
            send_welcome_email(customer_email, "", new_key)
            print(f"✅ New license created & emailed to {customer_email}")

    return JSONResponse({"status": "success"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
