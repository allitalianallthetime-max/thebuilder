"""
workshop_worker.py — Background Data Processor
===============================================
Pulls heavy Vision and Teardown tasks off the main web thread.
Forces native JSON. Safely cleans up Redis memory bloat.
"""

import os
import json
import logging
import psycopg2
import base64
import hashlib
from celery import Celery
import redis
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("ws-worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://builder-redis:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

celery_app = Celery("workshop_tasks", broker=REDIS_URL, backend=REDIS_URL)
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
genai.configure(api_key=GEMINI_API_KEY)

PHASE_KEYS = ["planning", "fabrication", "assembly", "electrical", "testing", "complete"]
PHASES = [
    {"key": "planning", "name": "PLANNING & TEARDOWN", "gate": "Confirm: All parts inventoried, workspace cleared, PPE staged."},
    {"key": "fabrication", "name": "FABRICATION", "gate": "Confirm: All welds inspected, measurements verified, no cracks."},
    {"key": "assembly", "name": "ASSEMBLY", "gate": "Confirm: All fasteners torqued to spec, wiring secured, no shorts."},
    {"key": "electrical", "name": "ELECTRICAL & CODE", "gate": "Confirm: All circuits tested, grounds verified, code uploaded."},
    {"key": "testing", "name": "TESTING & VALIDATION", "gate": "Confirm: All systems nominal, safety interlocks functional, documented."}
]

# ── TASK 1: Project Teardown Analysis ─────────────────────────────────────────
@celery_app.task(bind=True, name="workshop_worker.build_project_data_task", max_retries=2)
def build_project_data_task(self, project_id: int, junk_desc: str, project_type: str):
    self.update_state(state='PROGRESS', meta={'message': 'AI tearing down components...'})
    
    analysis = {"parts": [], "tasks": {}}
    if junk_desc:
        try:
            # Native JSON Mode ensures 100% crash-proof parsing
            model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
            prompt = f"""You are an expert salvage engineer. EQUIPMENT: {junk_desc}. TARGET: {project_type}.
            Return ONLY a JSON object with keys: "parts" (list of objects with name, category, quantity, source, est_value, notes), "difficulty" (1-10), "est_hours", "est_cost", "safety_warnings", "tools_required", and "tasks" (dict of arrays for planning, fabrication, assembly, electrical, testing)."""
            
            response = model.generate_content(prompt)
            analysis = json.loads(response.text)
        except Exception as exc:
            log.error(f"Project AI setup failed: {exc}")
            raise self.retry(exc=exc, countdown=10)
        
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            # 1. Update Project Status
            cur.execute("UPDATE workshop_projects SET difficulty=%s, est_hours=%s, est_cost=%s, status='active' WHERE id=%s",
                        (analysis.get("difficulty", 5), analysis.get("est_hours", 0), analysis.get("est_cost", 0), project_id))
            
            # 2. Insert Tasks & Safety Gates
            sort = 0
            for phase in PHASES:
                pkey = phase["key"]
                for t in analysis.get("tasks", {}).get(pkey, []):
                    sort += 1
                    cur.execute("INSERT INTO workshop_tasks (project_id, phase, title, sort_order) VALUES (%s, %s, %s, %s)", (project_id, pkey, t, sort))
                
                if phase["gate"]:
                    sort += 1
                    cur.execute("INSERT INTO workshop_tasks (project_id, phase, title, description, is_safety, sort_order) VALUES (%s, %s, %s, %s, TRUE, %s)", 
                                (project_id, pkey, f"⛑ SAFETY GATE: {phase['name']}", phase["gate"], sort))

            # 3. Insert Parts & Warnings
            for p in analysis.get("parts", []):
                cur.execute("INSERT INTO workshop_parts (project_id, name, category, source, quantity, est_value, notes) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (project_id, p.get("name", "Unknown"), p.get("category", "general"), p.get("source", "salvage"), p.get("quantity", 1), p.get("est_value", 0), p.get("notes", "")))
            
            for warning in analysis.get("safety_warnings", []):
                cur.execute("INSERT INTO workshop_notes (project_id, phase, content, note_type) VALUES (%s, 'planning', %s, 'safety')", (project_id, f"⚠️ {warning}"))

            conn.commit()
            return {"project_id": project_id, "parts_count": len(analysis.get("parts", []))}
    finally:
        conn.close()

# ── TASK 2: X-Ray Vision Scanner ──────────────────────────────────────────────
@celery_app.task(bind=True, name="workshop_worker.vision_scan_task", max_retries=2)
def vision_scan_task(self, payload_key: str, mime_type: str, context: str, user_email: str):
    self.update_state(state='PROGRESS', meta={'message': 'X-Raying image layers...'})
    
    b64_image = redis_client.get(payload_key)
    if not b64_image:
        raise ValueError("Image payload expired in Redis queue.")
        
    try:
        image_bytes = base64.b64decode(b64_image)
        model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
        prompt = f"""You are an elite forensic industrial analyst. CONTEXT: {context}.
        Return ONLY valid JSON with keys: identification (equipment_name, manufacturer, model, year_range, category), schematics, specifications, components (list of dicts with name, category, quantity, salvage_value), hazards (level), salvage_assessment (total_estimated_value)."""
        
        image_part = {"inline_data": {"mime_type": mime_type, "data": b64_image}}
        response = model.generate_content([prompt, image_part])
        
        result = json.loads(response.text)
        
        image_hash = hashlib.md5(image_bytes).hexdigest()
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                ident = result.get("identification", {})
                cur.execute("""
                    INSERT INTO equipment_scans (user_email, image_hash, equipment_name, manufacturer, model, year_range, category, scan_result, parts_found, est_salvage, hazard_level, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'complete') RETURNING id
                """, (user_email, image_hash, ident.get("equipment_name", "Unknown"), ident.get("manufacturer", ""), ident.get("model", ""), ident.get("year_range", ""), ident.get("category", "other"), json.dumps(result), len(result.get("components", [])), result.get("salvage_assessment", {}).get("total_estimated_value", 0), result.get("hazards", {}).get("level", "unknown")))
                scan_id = cur.fetchone()[0]
                conn.commit()
                
                # Success! Now safe to free memory
                redis_client.delete(payload_key)
                
                return {"scan_id": scan_id, "equipment_name": ident.get("equipment_name", "Unknown"), "scan_result": result}
        finally:
            conn.close()
    except Exception as exc:
        log.error(f"Vision task failed: {exc}")
        raise self.retry(exc=exc, countdown=15)
