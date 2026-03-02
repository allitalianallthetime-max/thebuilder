import os, asyncio, json, hashlib, psycopg2, httpx, anthropic
import google.generativeai as genai
from datetime import datetime
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("bob_tasks", broker=REDIS_URL, backend=REDIS_URL)

try: import redis; redis_client = redis.from_url(REDIS_URL, decode_responses=True)
except: redis_client = None

DATABASE_URL = os.getenv("DATABASE_URL")
XAI_API_KEY = os.getenv("XAI_API_KEY") 
if os.getenv("GEMINI_API_KEY"): genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
if os.getenv("ANTHROPIC_API_KEY"): anthropic_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def get_grok(desc, proj):
    """Mechanical Engineering Analysis (Grok-3)"""
    if not XAI_API_KEY: return {"text": "[MECHANICAL ENGINEERING OFFLINE]", "tokens": 0}
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(
            "https://api.x.ai/v1/chat/completions", 
            headers={"Authorization": f"Bearer {XAI_API_KEY}"}, 
            json={"model": "grok-3", "temperature": 0.1, "messages": [
                {"role": "system", "content": "You are a professional mechanical engineer. Provide highly technical structural analysis, torque calculations, and physical integration steps. Do not hallucinate capabilities beyond the provided inventory."}, 
                {"role": "user", "content": f"Project: {proj}\nAvailable Components: {desc}"}
            ]}
        )
        return {"text": r.json()["choices"][0]["message"]["content"], "tokens": r.json().get("usage", {}).get("total_tokens", 0)}

async def get_claude(desc, proj):
    """Embedded Systems & Software (Claude 3.7 Sonnet Latest)"""
    if not os.getenv("ANTHROPIC_API_KEY"): return {"text": "[SYSTEMS ENGINEERING OFFLINE]", "tokens": 0}
    # THIS IS THE LATEST ANTHROPIC SDK STANDARD (Uses system parameter)
    msg = await anthropic_client.messages.create(
        model="claude-3-7-sonnet-latest", 
        max_tokens=2048, 
        temperature=0.1,
        system="You are an expert Robotics Software and Embedded Systems Engineer. Provide pure technical documentation, wiring schematics, and micro-controller logic. Do not include conversational filler. Base your design strictly on the provided components.",
        messages=[{"role": "user", "content": f"Project: {proj}\nComponents: {desc}"}]
    )
    return {"text": msg.content[0].text, "tokens": msg.usage.input_tokens + msg.usage.output_tokens}

async def get_gemini(desc, proj, g_n, c_n):
    """Central Systems Architect (Gemini 2.5 Flash)"""
    if not os.getenv("GEMINI_API_KEY"): return {"text": "[SYNTHESIS OFFLINE]", "tokens": 0}
    model = genai.GenerativeModel("gemini-2.5-flash")
    resp = await model.generate_content_async(
        f"You are BOB (Base Operations Builder), a professional robotics engineering AI. Synthesize a pristine, technical engineering blueprint for {proj} using strictly these components: {desc}. "
        f"Integrate Mechanical constraints: {g_n}. Integrate Systems logic: {c_n}. Format cleanly in Markdown with a Bill of Materials, Assembly Steps, and Safety Warnings."
    )
    return {"text": resp.text, "tokens": len(resp.text)//4}

async def run_pipeline(desc, proj, email, detail, task):
    cache_key = "bob_bld_" + hashlib.md5(f"{desc}|{proj}|{detail}".encode()).hexdigest()
    if redis_client and redis_client.get(cache_key):
        task.update_state(state='PROGRESS', meta={'message': 'Retrieving cached architectural plans...'})
        c = json.loads(redis_client.get(cache_key))
        return await save_db(email, desc, proj, c["blueprint"], c["grok"], c["claude"], 0, task)

    task.update_state(state='PROGRESS', meta={'message': 'Calculating mechanical & electrical parameters...'})
    grok, claude = await asyncio.gather(get_grok(desc, proj), get_claude(desc, proj))
    
    task.update_state(state='PROGRESS', meta={'message': 'Synthesizing master engineering blueprint...'})
    gemini = await get_gemini(desc, proj, grok["text"], claude["text"])

    if redis_client: redis_client.setex(cache_key, 604800, json.dumps({"blueprint": gemini["text"], "grok": grok["text"], "claude": claude["text"]}))
    return await save_db(email, desc, proj, gemini["text"], grok["text"], claude["text"], grok["tokens"]+claude["tokens"]+gemini["tokens"], task)

async def save_db(email, desc, proj, bp, g_notes, c_notes, tokens, task):
    task.update_state(state='PROGRESS', meta={'message': 'Securing blueprint to database...'})
    def _save():
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS builds (id SERIAL PRIMARY KEY, user_email TEXT, junk_desc TEXT, project_type TEXT, blueprint TEXT, grok_notes TEXT, claude_notes TEXT, tokens_used INTEGER, created_at TIMESTAMP DEFAULT NOW())")
            cur.execute("INSERT INTO builds (user_email, junk_desc, project_type, blueprint, grok_notes, claude_notes, tokens_used) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id", (email, desc, proj, bp, g_notes, c_notes, tokens))
            conn.commit(); return cur.fetchone()[0]
    return {"content": bp, "build_id": await asyncio.to_thread(_save)}

@celery_app.task(bind=True, name="ai_worker.forge_blueprint_task") 
def forge_blueprint_task(self, desc, proj, email, detail):
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    return loop.run_until_complete(run_pipeline(desc, proj, email, detail, self))

@celery_app.task(bind=True, name="ai_worker.simulate_battle_task")
def simulate_battle_task(self, na, sa, nb, sb):
    self.update_state(state='PROGRESS', meta={'message': 'Running kinematic stress simulation...'})
    prompt = f"Act as a strict physics simulation engine. Evaluate a kinetic collision between Subject A [{na}: {sa}] and Subject B [{nb}: {sb}]. Detail structural failures and energy transfer strictly based on the provided materials. Conclude with 'SIMULATION WINNER: [Subject]'."
    with httpx.Client(timeout=45.0) as client:
        resp = client.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_API_KEY}"}, json={"model": "grok-3", "messages": [{"role": "user", "content": prompt}], "temperature": 0.2})
        return {"combat_log": resp.json()["choices"][0]["message"]["content"]}
