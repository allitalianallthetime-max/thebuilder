"""
ai_worker.py — The Background AI Processor
===========================================
Enterprise-Grade Asynchronous Task Worker.
Features:
- Official xAI (grok-3) Integration
- Per-Model Local Retries (Prevents double-billing if one API fails)
- Redis Output Caching (100% Margin on duplicate requests)
- Automated API Cost Tracking
"""

import os
import asyncio
import logging
import json
import hashlib
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

# ── 1. Redis & Celery Setup ──────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://builder-redis:6379/0")
celery_app = Celery("ai_tasks", broker=REDIS_URL, backend=REDIS_URL)

try:
    import redis
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    log.error(f"Redis cache connection failed: {e}")
    redis_client = None

# ── 2. Configuration & API Clients ───────────────────────────────────────────
DATABASE_URL      = os.getenv("DATABASE_URL")
XAI_API_KEY       = os.getenv("XAI_API_KEY")       # Elon Musk's xAI
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") # Claude
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY")    # Google

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
if ANTHROPIC_API_KEY:
    anthropic_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

DETAIL_PROMPTS = {
    "Full Blueprint (All 3 Tiers)": "Include Novice, Journeyman, and Master tiers with deep technical precision.",
    "Quick Concept (Novice Only)":  "Only provide the NOVICE TIER. Focus on basic hand tools and absolute safety.",
    "Master Build (Expert Only)":   "Only provide the MASTER TIER. Assume a full CNC shop and advanced coding skills.",
}

# ── 3. Resilient AI Callers (Local Retries = Money Saved) ────────────────────

async def get_grok_response(junk_desc: str, project_type: str, max_retries=3) -> dict:
    """The Shop Foreman: Uses xAI's most advanced grok-3 model."""
    if not XAI_API_KEY:
        return {"text": "[SHOP FOREMAN OFFLINE] XAI_API_KEY not configured.", "tokens": 0}

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {XAI_API_KEY}", 
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "grok-3", # Musk's latest cutting-edge reasoning model
                        "messages": [
                            {"role": "system", "content": "You are a Master Marine Diesel Mechanic. Think in raw components, torque specs, weld joints, and hydraulic pressures. Be direct, technical, and brutally practical. No fluff."},
                            {"role": "user", "content": f"Break down how to build a {project_type} using these parts: {junk_desc}."}
                        ],
                        "max_tokens": 1500,
                        "temperature": 0.2 
                    }
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "text": data["choices"][0]["message"]["content"],
                    "tokens": data.get("usage", {}).get("total_tokens", 0)
                }
        except Exception as e:
            log.warning(f"Grok attempt {attempt+1} failed: {e}")
            if attempt == max_retries - 1:
                return {"text": "[SHOP FOREMAN OFFLINE] Grok unavailable — proceeding with standard specs.", "tokens": 0}
            await asyncio.sleep(2 ** attempt)

async def get_claude_response(junk_desc: str, project_type: str, max_retries=3) -> dict:
    """The Precision Engineer: Claude 3.7 Sonnet for code and schematics."""
    if not ANTHROPIC_API_KEY:
        return {"text": "[PRECISION ENGINEER OFFLINE] ANTHROPIC_API_KEY not configured.", "tokens": 0}

    for attempt in range(max_retries):
        try:
            message = await anthropic_client.messages.create(
                model="claude-3-7-sonnet-20250219", 
                max_tokens=1500,
                temperature=0.2,
                messages=[
                    {"role": "user", "content": f"You are a Precision Engineer specializing in embedded systems, Python automation, and electrical engineering. TASK: Design the control system for a {project_type} built from: {junk_desc}"}
                ]
            )
            return {
                "text": message.content[0].text,
                "tokens": message.usage.input_tokens + message.usage.output_tokens
            }
        except Exception as e:
            log.warning(f"Claude attempt {attempt+1} failed: {e}")
            if attempt == max_retries - 1:
                return {"text": "[PRECISION ENGINEER OFFLINE] Claude unavailable.", "tokens": 0}
            await asyncio.sleep(2 ** attempt)

async def get_gemini_response(junk_desc: str, project_type: str, grok_notes: str, claude_notes: str, detail_level: str, max_retries: int=3) -> dict:
    """The General Contractor: Gemini 2.5 Flash for final blueprint synthesis."""
    if not GEMINI_API_KEY:
        return {"text": "[GENERAL CONTRACTOR OFFLINE] GEMINI_API_KEY not configured.", "tokens": 0}

    detail_instruction = DETAIL_PROMPTS.get(detail_level, DETAIL_PROMPTS["Full Blueprint (All 3 Tiers)"])
    
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            prompt = f"""You are the General Contractor overseeing a Round Table of elite engineers.
            GROK NOTES: {grok_notes}
            CLAUDE NOTES: {claude_notes}
            TASK: Synthesize a legendary tiered blueprint for a {project_type} built from: {junk_desc}
            DETAIL LEVEL: {detail_instruction}
            Format strictly as a blueprint with sections for Tiers, Parts Manifest, and Safety Protocols."""
            
            response = await model.generate_content_async(prompt)
            tokens = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else (len(response.text) // 4)
            
            return {"text": response.text, "tokens": tokens}
        except Exception as e:
            log.warning(f"Gemini attempt {attempt+1} failed: {e}")
            if attempt == max_retries - 1:
                return {"text": "[GENERAL CONTRACTOR OFFLINE] Gemini synthesis failed.", "tokens": 0}
            await asyncio.sleep(2 ** attempt)

# ── 4. Async Orchestrator ────────────────────────────────────────────────────
def generate_cache_key(junk_desc: str, project_type: str, detail_level: str) -> str:
    """Creates a unique hash to check if this exact build has been requested before."""
    raw = f"{junk_desc.strip().lower()}|{project_type.strip().lower()}|{detail_level}"
    return "build_cache:" + hashlib.md5(raw.encode()).hexdigest()

async def run_ai_pipeline(junk_desc: str, project_type: str, user_email: str, detail_level: str, task_instance):
    """Coordinates parallel execution, protects from double-billing, and saves to DB."""
    
    # ── ENTERPRISE COST-SAVER CACHE ──
    cache_key = generate_cache_key(junk_desc, project_type, detail_level)
    total_tokens = 0
    
    if redis_client:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            log.info(f"💰 PROFIT MARGIN BOOST: Cache hit for {user_email}. APIs bypassed.")
            task_instance.update_state(state='PROGRESS', meta={'message': 'Pulling archived schematics from the vault...'})
            await asyncio.sleep(1.5) # Fake a slight delay for user experience
            parsed_cache = json.loads(cached_data)
            
            # Jump straight to saving the record
            return await save_to_db(
                user_email, junk_desc, project_type, 
                parsed_cache["blueprint"], parsed_cache["grok_notes"], parsed_cache["claude_notes"], total_tokens, task_instance
            )

    task_instance.update_state(state='PROGRESS', meta={'message': 'Grok and Claude analyzing components...'})
    
    # 1. Run Grok and Claude simultaneously
    grok_result, claude_result = await asyncio.gather(
        get_grok_response(junk_desc, project_type),
        get_claude_response(junk_desc, project_type)
    )
    
    task_instance.update_state(state='PROGRESS', meta={'message': 'Gemini finalizing master blueprint...'})
    
    # 2. Pass their outputs to Gemini
    gemini_result = await get_gemini_response(
        junk_desc, project_type, grok_result["text"], claude_result["text"], detail_level
    )
    
    # Calculate Total Tokens for Profit/Margin Tracking
    total_tokens = grok_result["tokens"] + claude_result["tokens"] + gemini_result["tokens"]
    
    # SAVE TO CACHE (Store for 7 days to save future API costs)
    if redis_client and "OFFLINE" not in gemini_result["text"]:
        try:
            cache_payload = json.dumps({
                "blueprint": gemini_result["text"], "grok_notes": grok_result["text"], "claude_notes": claude_result["text"]
            })
            redis_client.setex(cache_key, 86400 * 7, cache_payload)
        except Exception as e:
            log.error(f"Failed to cache build: {e}")

    # 3. Save to PostgreSQL safely on a background thread
    return await save_to_db(
        user_email, junk_desc, project_type, 
        gemini_result["text"], grok_result["text"], claude_result["text"], total_tokens, task_instance
    )

async def save_to_db(user_email, junk_desc, project_type, final_blueprint, grok_notes, claude_notes, total_tokens, task_instance):
    task_instance.update_state(state='PROGRESS', meta={'message': 'Filing blueprints in logbook...'})
    def _save():
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO builds (user_email, junk_desc, project_type, blueprint, grok_notes, claude_notes, tokens_used, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (user_email, junk_desc, project_type, final_blueprint, grok_notes, claude_notes, total_tokens, datetime.utcnow()))
                build_id = cur.fetchone()[0]
                conn.commit()
                return build_id
        finally:
            conn.close()

    build_id = await asyncio.to_thread(_save)
    
    return {
        "content": final_blueprint,
        "build_id": build_id,
        "tokens_used": total_tokens,
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
@celery_app.task(bind=True, name="ai_worker.forge_blueprint_task", max_retries=1) 
def forge_blueprint_task(self, junk_desc, project_type, user_email, detail_level):
    """Note: Global Celery retries reduced to 1, because we have Local API retries enabled."""
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
        log.error(f"AI Task Failed Catastrophically: {exc}")
        
        # If we exhausted our 1 Celery retry, refund the user!
        if self.request.retries >= self.max_retries:
            refund_credit(user_email)
            
        raise self.retry(exc=exc, countdown=30)
