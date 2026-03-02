import os, secrets, psycopg2.pool, redis, json
from fastapi import FastAPI, Header, Depends, HTTPException
from pydantic import BaseModel
from celery.result import AsyncResult
from celery import Celery
from datetime import datetime

app = FastAPI()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("ai_tasks", broker=REDIS_URL, backend=REDIS_URL)
try: redis_client = redis.from_url(REDIS_URL, decode_responses=True)
except: redis_client = None

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
db_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, os.getenv("DATABASE_URL"))

def verify_key(x_internal_key: str = Header(None)):
    if not secrets.compare_digest(x_internal_key or "", os.getenv("INTERNAL_API_KEY")): raise HTTPException(403)

class BuildReq(BaseModel): junk_desc: str; project_type: str; detail_level: str="Standard Overview"; user_email: str="anonymous"
class ChatMsg(BaseModel): user_name: str; tier: str; message: str
class BattleReq(BaseModel): robot_a_name: str; robot_a_specs: str; robot_b_name: str; robot_b_specs: str

# 👇 FIXED: Changed Header(verify_key) to Depends(verify_key)
@app.post("/generate", dependencies=[Depends(verify_key)])
def gen_blueprint(req: BuildReq):
    with db_pool.getconn() as conn:
        with conn.cursor() as cur:
            if req.user_email not in ("admin", "anonymous"):
                cur.execute("SELECT build_count, tier FROM licenses WHERE email = %s AND status = 'active'", (req.user_email,))
                lic = cur.fetchone()
                if not lic or lic[0] >= (999 if lic[1]=="master" else 100 if lic[1]=="pro" else 25): raise HTTPException(402)
                cur.execute("UPDATE licenses SET build_count = build_count + 1 WHERE email = %s", (req.user_email,))
                conn.commit()
        db_pool.putconn(conn)
    task = celery_app.send_task("ai_worker.forge_blueprint_task", args=[req.junk_desc, req.project_type, req.user_email, req.detail_level])
    return {"status": "processing", "task_id": task.id}

@app.get("/generate/status/{tid}", dependencies=[Depends(verify_key)])
def chk_task(tid: str):
    res = AsyncResult(tid, app=celery_app)
    if res.state == 'SUCCESS': return {"status": "complete", "result": res.result}
    if res.state == 'FAILURE': return {"status": "failed", "error": str(res.info)}
    return {"status": "processing", "message": res.info.get("message", "Processing...") if isinstance(res.info, dict) else ""}

@app.post("/arena/chat/send", dependencies=[Depends(verify_key)])
def send_chat(msg: ChatMsg):
    if redis_client:
        redis_client.lpush("global_chat", json.dumps({"user": msg.user_name, "tier": msg.tier, "text": msg.message, "time": datetime.utcnow().strftime("%H:%M")}))
        redis_client.ltrim("global_chat", 0, 49) 
    return {"status": "ok"}

@app.get("/arena/chat/recent", dependencies=[Depends(verify_key)])
def get_chat():
    return [json.loads(m) for m in redis_client.lrange("global_chat", 0, 49)][::-1] if redis_client else []

@app.post("/arena/battle", dependencies=[Depends(verify_key)])
def battle(req: BattleReq):
    task = celery_app.send_task("ai_worker.simulate_battle_task", args=[req.robot_a_name, req.robot_a_specs, req.robot_b_name, req.robot_b_specs])
    return {"status": "processing", "task_id": task.id}
    
@app.get("/health")
def health(): return {"status": "ok"}
