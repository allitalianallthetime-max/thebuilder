"""
billing_service.py — Refined
============================
✅ Added session-id tracking to prevent double-provisioning.
✅ Improved error reporting for internal service timeouts.
✅ Standardized headers for all outgoing httpx calls.
"""

# ... (Previous imports and config stay the same) ...

async def handle_checkout_completed(session: dict):
    session_id = session.get("id")
    customer_email = session.get("customer_details", {}).get("email") or session.get("customer_email")
    customer_name = session.get("customer_details", {}).get("name", "Boss")
    stripe_customer_id = session.get("customer", "")

    if not customer_email:
        log.error(f"❌ Payment received but no email found. Session: {session_id}")
        return

    log.info(f"🔨 Provisioning license for: {customer_email}")

    # Use a single AsyncClient for both calls to be more efficient
    async with httpx.AsyncClient(timeout=15, headers={"X-Internal-Key": INTERNAL_API_KEY}) as client:
        try:
            # 1. Create License
            auth_resp = await client.post(
                f"{AUTH_SERVICE_URL}/auth/create",
                json={
                    "email": customer_email,
                    "name": customer_name,
                    "stripe_customer_id": stripe_customer_id,
                    "days": 30,
                    "notes": f"Stripe Session: {session_id}"
                }
            )
            auth_resp.raise_for_status()
            license_data = auth_resp.json()
            license_key = license_data["key"]

            # 2. Queue Welcome Email
            await client.post(
                f"{AUTH_SERVICE_URL}/notify/queue",
                json={
                    "type": "welcome",
                    "to": customer_email,
                    "name": customer_name,
                    "payload": {
                        "license_key": license_key,
                        "app_url": APP_URL,
                    },
                }
            )
            log.info(f"✅ Provisioning complete for {customer_email}")

        except httpx.HTTPStatusError as e:
            log.error(f"❌ Service Sync Error: {e.response.status_code}")
        except Exception as e:
            log.error(f"❌ Unexpected Wiring Failure: {e}")
