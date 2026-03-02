import os, json, psycopg2
from celery import Celery
import redis, google.generativeai as genai

celery_app = Celery("ws_tasks", broker=os.getenv("REDIS_URL"), backend=os.getenv("REDIS_URL"))
rc = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
if os.getenv("GEMINI_API_KEY"): genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@celery_app.task(bind=True, name="workshop_worker.vision_scan_task")
def vision_scan_task(self, pkey, mime, ctx, email):
    self.update_state(state='PROGRESS', meta={'message': 'Running Computer Vision Hardware Extraction...'})
    b64 = rc.get(pkey)
    model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
    r = model.generate_content([f"Identify robotics hardware, microcontrollers, motors, and structural components in this image. Context: {ctx}. Return strictly a JSON object with an 'identification' object (containing 'equipment_name') and a 'components' array (containing 'name' and 'quantity'). Do not hallucinate parts not visible.", {"inline_data": {"mime_type": mime, "data": b64}}])
    res = json.loads(r.text)
    
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS equipment_scans (id SERIAL PRIMARY KEY, user_email TEXT, equipment_name TEXT, scan_result JSONB)")
        cur.execute("INSERT INTO equipment_scans (user_email, equipment_name, scan_result) VALUES (%s,%s,%s) RETURNING id", (email, res.get("identification",{}).get("equipment_name", "Unknown"), json.dumps(res)))
        sid = cur.fetchone()[0]; conn.commit()
    conn.close(); rc.delete(pkey)
    return {"scan_id": sid, "scan_result": res}
