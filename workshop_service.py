import os, secrets, re, psycopg2.pool, redis, json
from fastapi import FastAPI, Header, Depends, HTTPException
from pydantic import BaseModel
from celery.result import AsyncResult
from celery import Celery

app = FastAPI()
celery_app = Celery("ws_tasks", broker=os.getenv("REDIS_URL"), backend=os.getenv("REDIS_URL"))
try: rc = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
except: rc = None
db_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, os.getenv("DATABASE_URL"))

def verify(x_internal_key: str = Header(None)):
    if not secrets.compare_digest(x_internal_key or "", os.getenv("INTERNAL_API_KEY")): raise HTTPException(403)

class ScanImg(BaseModel): image_base64: str; user_email: str; context: str

# 👇 FIXED: Changed Header(verify) to Depends(verify)
@app.post("/scan/base64", dependencies=[Depends(verify)])
def scan_img(req: ScanImg):
    mime = "image/jpeg"; b64 = req.image_base64
    if b64.startswith("data:"): 
        match = re.match(r"data:(image/\w+);base64,(.+)", b64, re.DOTALL)
        mime = match.group(1); b64 = match.group(2)
    pkey = f"scan:{secrets.token_hex(8)}"
    if rc: rc.setex(pkey, 600, b64)
    task = celery_app.send_task("workshop_worker.vision_scan_task", args=[pkey, mime, req.context, req.user_email])
    return {"status": "processing", "task_id": task.id}

@app.get("/task/status/{tid}", dependencies=[Depends(verify)])
def check_task(tid: str):
    res = AsyncResult(tid, app=celery_app)
    if res.state == 'SUCCESS': return {"status": "complete", "result": res.result}
    if res.state == 'FAILURE': return {"status": "failed"}
    return {"status": "processing", "message": res.info.get("message", "Processing data...") if isinstance(res.info, dict) else ""}
