import os, psycopg2.pool, jwt, secrets, datetime, json
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from contextlib import contextmanager

app = FastAPI()
pool = psycopg2.pool.ThreadedConnectionPool(2, 15, os.getenv("DATABASE_URL"))

@contextmanager
def get_db():
    conn = pool.getconn(); try: yield conn; finally: pool.putconn(conn)

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS licenses (id SERIAL PRIMARY KEY, license_key TEXT UNIQUE, email TEXT, name TEXT, stripe_customer_id TEXT, status TEXT DEFAULT 'active', tier TEXT, expires_at TIMESTAMP, build_count INTEGER DEFAULT 0, notes TEXT, created_at TIMESTAMP DEFAULT NOW())")
            cur.execute("CREATE TABLE IF NOT EXISTS notification_queue (id SERIAL PRIMARY KEY, type TEXT, to_email TEXT, name TEXT, payload JSONB, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT NOW())")
            conn.commit()
init_db()

def verify_int(x_internal_key: str = Header(None)):
    if not secrets.compare_digest(x_internal_key or "", os.getenv("INTERNAL_API_KEY")): raise HTTPException(403)

class VerifyReq(BaseModel): license_key: str
class CreateReq(BaseModel): email: str; stripe_customer_id: str=""; days: int=30; tier: str="pro"; notes: str=""

@app.post("/verify-license")
def verify_lic(req: VerifyReq, _=Depends(verify_int)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, expires_at, tier, email, name FROM licenses WHERE license_key = %s", (req.license_key,))
            res = cur.fetchone()
    if not res or res[0] != "active" or res[1] < datetime.datetime.utcnow(): raise HTTPException(403)
    tkn = jwt.encode({"sub": req.license_key, "email": res[3], "name": res[4], "tier": res[2], "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)}, os.getenv("JWT_SECRET"), "HS256")
    return {"token": tkn, "tier": res[2], "name": res[4], "email": res[3]}

@app.post("/auth/create", dependencies=[Depends(verify_int)])
def create_lic(req: CreateReq):
    key = f"BOB-{secrets.token_hex(4).upper()}"
    exp = datetime.datetime.utcnow() + datetime.timedelta(days=req.days)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO licenses (license_key, email, stripe_customer_id, tier, expires_at, notes) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id", (key, req.email, req.stripe_customer_id, req.tier, exp, req.notes))
            conn.commit()
    return {"key": key, "email": req.email, "tier": req.tier}
