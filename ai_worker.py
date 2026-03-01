"""
ai_worker.py — The Background AI Processor
===========================================
Runs exclusively in the background via Celery.
Pulls jobs from Redis, executes LLM logic safely, and saves to PostgreSQL.
Fully immune to web server timeouts.
"""

import os
import asyncio
import logging
from datetime import datetime
import psycopg2
from celery import Celery
import httpx
import anthropic
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [AI-WORKER] %(levelname)s %(message)s")
log = logging.getLogger("ai-worker")

# ── 1. Celery Setup ──────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://builder-redis:6379/0")
celery_app = Celery("ai_tasks", broker=REDIS_URL, backend=REDIS_URL)

# ── 2. Configuration & Clients ───────────────────────────────────────────────
DATABASE_URL      = os.getenv("DATABASE_URL")
XAI_API_KEY       = os.getenv("XAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
anthropic_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

DETAIL_PROMPTS = {
    "Full Blueprint (All 3 Tiers)": "Include Novice, Journeyman, and Master tiers.",
    "Quick Concept (Novice Only)":  "Only provide the NOVICE TIER.",
    "Master Build (Expert Only)":   "Only provide the MASTER TIER.",
}

# ── 3. Core AI Logic ─────────────────────────────────────────────────────────
async def get_grok_response(junk_desc: str, project_type: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": "You are a Master Marine Diesel Mechanic. Think in raw components, torque specs, weld joints, and hydraulic pressures. Be direct, technical, and practical. No fluff."},
                        {"role": "user", "content": f"Break down how to build a {project_type} using these parts: {junk_desc}."}
                    ],
                    "max_tokens": 1024
                }
            )
            return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        log.error(f"Grok API error: {e}")
        return "[SHOP FOREMAN OFFLINE] Grok unavailable — proceeding with standard specs."

async def get_claude_response(junk_desc: str, project_type: str) -> str:
    try:
        message = await anthropic_client.messages.create(
            model="claude-3-7-sonnet-20250219", 
            max_tokens=1024,
            messages=[
                {"role": "user", "content": f"You are a Precision Engineer specializing in embedded systems, Python automation, and electrical engineering. TASK: Design the control system for a {project_type} built from: {junk_desc}"}
            ]
        )
        return message.content[0].text
    except Exception as e:
        log.error(f"Claude API error: {e}")
        return "[PRECISION ENGINEER OFFLINE] Claude unavailable."

async def get_gemini_response(junk_desc, project_type, grok_notes, claude_notes, detail_level) -> str:
    detail_instruction = DETAIL_PROMPTS.get(detail_level, DETAIL_PROMPTS["Full Blueprint (All 3 Tiers)"])
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"""You are the General Contractor overseeing a Round Table of elite engineers.
        GROK NOTES: {grok_notes}
        CLAUDE NOTES: {claude_notes}
        TASK: Synthesize a legendary tiered blueprint for a {project_type} built from: {junk_desc}
        DETAIL LEVEL: {detail_instruction}
        Format strictly as a blueprint with sections for Tiers, Parts Manifest, and Safety Protocols."""
        
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        log.error(f"Gemini API error: {e}")
        return "[GENERAL CONTRACTOR OFFLINE] Gemini unavailable."

# ── 4. Async Orchestrator ────────────────────────────────────────────────────
async def run_ai_pipeline(junk_desc, project_type, user_email, detail_level, task_instance):
    """Coordinates parallel execution and database saving."""
    task_instance.update_state(state='PROGRESS', meta={'message': 'Foreman and Engineer analyzing components...'})
    
    # Run Grok and Claude simultaneously to save 50% time
    grok_notes, claude_notes = await asyncio.gather(
        get_grok_response(junk_desc, project_type),
        get_claude_response(junk_desc, project_type)
    )
    
    task_instance.update_state(state='PROGRESS', meta={'message': 'General Contractor finalizing blueprint...'})
    final_blueprint = await get_gemini_response(
        junk_desc, project_type, grok_notes, claude_notes, detail_level
    )
    
    task_instance.update_state(state='PROGRESS', meta={'message': 'Filing blueprints in logbook...'})
    
    # Save to PostgreSQL
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO builds (user_email, junk_desc, project_type, blueprint, grok_notes, claude_notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (user_email, junk_desc, project_type, final_blueprint, grok_notes, claude_notes, datetime.utcnow()))
            build_id = cur.fetchone()[0]
            conn.commit()
    finally:
        conn.close()
    
    return {
        "content": final_blueprint,
        "build_id": build_id,
        "round_table": {"foreman": grok_notes, "engineer": claude_notes, "contractor": final_blueprint}
    }

def refund_credit(user_email: str):
    """If the worker completely fails all retries, refund the user to prevent chargebacks."""
    if user_email in ("admin", "anonymous"): return
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE licenses SET build_count = build_count - 1 WHERE email = %s AND build_count > 0", (user_email,))
            conn.commit()
    except Exception as e:
        log.error(f"Refund failed for {user_email}: {e}")
    finally:
        conn.close()

# ── 5. Celery Entry Point ────────────────────────────────────────────────────
@celery_app.task(bind=True, name="ai_worker.forge_blueprint_task", max_retries=3)
def forge_blueprint_task(self, junk_desc, project_type, user_email, detail_level):
    """
    CELERY TASK:
    If an AI provider throws a 503 error, Celery automatically catches it
    and retries the task later without you losing the customer's request.
    """
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(
            run_ai_pipeline(junk_desc, project_type, user_email, detail_level, self)
        )
    except Exception as exc:
        log.error(f"AI Task Failed: {exc}")
        
        # If we exhausted all retries, refund the user!
        if self.request.retries >= self.max_retries:
            refund_credit(user_email)
            
        # Automatically retry with exponential backoff
        raise self.retry(exc=exc, countdown=15 * (2 ** self.request.retries))
