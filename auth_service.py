import os
import psycopg2
import jwt
import datetime
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from pydantic import BaseModel
from contextlib import contextmanager  # The missing tool
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

# ── Database Connection Manager ──────────────────────────────────────────────
@contextmanager
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()

# ── Security Check ───────────────────────────────────────────────────────────
async def verify_internal(x_internal_key: str = Header(None)):
    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal key")

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ── Verify License Logic ─────────────────────────────────────────────────────
@app.post("/verify-license")
async def verify_license(data: dict, x_internal_key: str = Header(None)):
    await verify_internal(x_internal_key)
    
    license_key = data.get("license_key")
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, expires_at, tier FROM licenses WHERE license_key = %s",
                (license_key,)
            )
            result = cur.fetchone()
            
    if not result:
        raise HTTPException(status_code=404, detail="License not found")
        
    status, expires_at, tier = result
    
    if status != 'active':
        raise HTTPException(status_code=403, detail="License is inactive")
        
    if expires_at < datetime.datetime.now():
        raise HTTPException(status_code=403, detail="License expired")
        
    # Generate the "Badge" (JWT)
    token = jwt.encode({
        "sub": license_key,
        "tier": tier,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, JWT_SECRET, algorithm="HS256")
    
    return {"token": token, "tier": tier}
