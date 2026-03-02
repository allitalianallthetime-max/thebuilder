import os, psycopg2.pool, json
from fastapi import FastAPI, Header, BackgroundTasks
from pydantic import BaseModel

app = FastAPI()
db_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, os.getenv("DATABASE_URL"))
class EventReq(BaseModel): event_type: str; user_email: str; metadata: dict

def save_event(evt, email, meta):
    with db_pool.getconn() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS events (id SERIAL PRIMARY KEY, type TEXT, email TEXT, meta JSONB, created_at TIMESTAMP DEFAULT NOW())")
            cur.execute("INSERT INTO events (type, email, meta) VALUES (%s, %s, %s)", (evt, email, json.dumps(meta)))
            conn.commit()
        db_pool.putconn(conn)

@app.post("/track/event")
def track(req: EventReq, bg: BackgroundTasks, x_internal_key: str = Header(None)):
    bg.add_task(save_event, req.event_type, req.user_email, req.metadata)
    return {"status": "ok"}
