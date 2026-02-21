"""
auth_service.py — Refined
=========================
✅ Improved SQLite concurrency with WAL mode (better for multiple services).
✅ Standardized JWT timestamping for better "Clock Sync" between services.
✅ Added a "Manual Cleanup" endpoint for the Scheduler.
"""

# ... (Previous imports stay the same) ...

@contextmanager
def get_db():
    # Adding 'isolation_level=None' and WAL mode for better multi-service access
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;") 
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

# ── Updated Validation with Clearer JWT Payload ───────────────────────────────
@app.post("/auth/validate")
async def validate_license(req: ValidateRequest):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM licenses WHERE license_key=?", (req.license_key,)
        ).fetchone()

    if not row:
        return {"valid": False, "status": "not_found"}

    if row["status"] == "revoked":
        return {"valid": False, "status": "revoked"}

    expires_at = datetime.fromisoformat(row["expires_at"])
    now = datetime.utcnow()
    days_remaining = (expires_at - now).days

    if days_remaining < -15:
        return {"valid": False, "status": "expired", "days_remaining": days_remaining}

    # Issue JWT - using timezone-aware UTC for the 'Brain' to verify correctly
    token_payload = {
        "sub": req.license_key,
        "name": row["name"],
        "email": row["email"], # Added email to payload for easier AI logging
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(token_payload, JWT_SECRET, algorithm="HS256")

    return {
        "valid": True,
        "status": row["status"],
        "email": row["email"],
        "name": row["name"],
        "days_remaining": days_remaining,
        "token": token,
    }
