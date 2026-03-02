import os, psycopg2.pool
from fastapi import FastAPI, Header, Depends

app = FastAPI()
db_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, os.getenv("DATABASE_URL"))

def verify(x_master_key: str = Header(None)):
    import secrets
    if not secrets.compare_digest(x_master_key or "", os.getenv("MASTER_KEY")): raise Exception("Denied")

@app.get("/dashboard", dependencies=[Depends(verify)])
def dashboard():
    with db_pool.getconn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM licenses WHERE status = 'active'")
            users = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM builds")
            builds = cur.fetchone()[0]
        db_pool.putconn(conn)
    return {"financials": {"estimated_mrr": f"${users * 49}", "gross_margin": f"${(users * 49) - (builds * 0.05):.2f}"}, "licenses": {"active": users}}
