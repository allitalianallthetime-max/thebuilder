"""
ai_service.py — The Round Table
================================
THE FORGE AI ENGINE
- Grok      → The Shop Foreman    (mechanical logic)
- Claude    → The Precision Engineer (code & schematics)
- Gemini    → The General Contractor (final synthesis)

All three AIs collaborate on every build.
Every build is saved to PostgreSQL.
"""

import os
import asyncio
import secrets
import psycopg2
import psycopg2.pool
import httpx
import anthropic
import google.generativeai as genai
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# ── Configuration ─────────────────────────────────────────────────────────────
INTERNAL_API_KEY  = os.getenv("INTERNAL_API_KEY")
DATABASE_URL      = os.getenv("DATABASE_URL")
XAI_API_KEY       = os.getenv("XAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY")

# ── Security (timing-safe comparison) ────────────────────────────────────────
def verify_key(provided: str) -> bool:
    """Constant-time comparison to prevent timing attacks on API key."""
    if not provided or not INTERNAL_API_KEY:
        return False
    return secrets.compare_digest(provided, INTERNAL_API_KEY)

# Configure AI clients — use ASYNC clients so we don't block the event loop
genai.configure(api_key=GEMINI_API_KEY)
anthropic_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# ── Database (connection pool) ────────────────────────────────────────────────
db_pool = None

def get_pool():
    global db_pool
    if db_pool is None:
        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2, maxconn=10, dsn=DATABASE_URL
        )
    return db_pool

def get_conn():
    return get_pool().getconn()

def put_conn(conn):
    get_pool().putconn(conn)

def init_db():
    """Create builds table if it doesn't exist."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS builds (
                    id           SERIAL PRIMARY KEY,
                    user_email   TEXT DEFAULT 'anonymous',
                    junk_desc    TEXT NOT NULL,
                    project_type TEXT NOT NULL,
                    blueprint    TEXT,
                    grok_notes   TEXT,
                    claude_notes TEXT,
                    tokens_used  INTEGER DEFAULT 0,
                    created_at   TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
    finally:
        put_conn(conn)

try:
    init_db()
except Exception as e:
    print(f"DB Init Warning: {e}")

# ── Request Model ─────────────────────────────────────────────────────────────
class BuildRequest(BaseModel):
    junk_desc:    str
    project_type: str
    detail_level: str = "Full Blueprint (All 3 Tiers)"
    user_email:   str = "anonymous"

# ── Detail level → prompt modifier ────────────────────────────────────────────
DETAIL_PROMPTS = {
    "Full Blueprint (All 3 Tiers)": "Include Novice, Journeyman, and Master tiers with full detail.",
    "Quick Concept (Novice Only)":  "Only provide the NOVICE TIER — basic build, minimum tools, beginner-friendly.",
    "Master Build (Expert Only)":   "Only provide the MASTER TIER — full integration, advanced techniques, Python control.",
}

# ── Tier Build Limits (per 30-day rolling window) ────────────────────────────
# Must match billing_service.py PLANS
TIER_LIMITS = {
    "starter": 25,
    "pro":     100,
    "master":  999,
}

# ── Build Limit Enforcement ──────────────────────────────────────────────────
def check_build_limits(user_email: str) -> dict:
    """Check if a user has builds remaining in their current billing cycle.

    Returns dict with: allowed, tier, used, limit, remaining, (reason if denied)
    Queries the licenses table directly — can't be spoofed from the UI.
    """
    # Admin/master key users bypass limits
    if user_email in ("admin", "anonymous"):
        return {"allowed": True, "tier": "master", "used": 0, "limit": 999, "remaining": 999}

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Look up the user's active license tier
            cur.execute("""
                SELECT tier, status, expires_at FROM licenses
                WHERE email = %s AND status = 'active'
                ORDER BY created_at DESC LIMIT 1
            """, (user_email,))
            lic = cur.fetchone()

            if not lic:
                return {"allowed": False, "tier": "none", "used": 0, "limit": 0, "remaining": 0,
                        "reason": "No active license found for this account."}

            tier, status, expires_at = lic

            if expires_at < datetime.utcnow():
                return {"allowed": False, "tier": tier, "used": 0, "limit": 0, "remaining": 0,
                        "reason": "License expired. Renew to continue forging."}

            # Count builds in the last 30 days
            cur.execute("""
                SELECT COUNT(*) FROM builds
                WHERE user_email = %s AND created_at > NOW() - INTERVAL '30 days'
            """, (user_email,))
            used = cur.fetchone()[0]

            limit = TIER_LIMITS.get(tier, 25)
            remaining = max(0, limit - used)

            if used >= limit:
                return {"allowed": False, "tier": tier, "used": used, "limit": limit, "remaining": 0,
                        "reason": f"{tier.upper()} tier limit reached ({used}/{limit} builds). Upgrade to unlock more."}

            return {"allowed": True, "tier": tier, "used": used, "limit": limit, "remaining": remaining}
    finally:
        put_conn(conn)

# ── THE SHOP FOREMAN (Grok) ───────────────────────────────────────────────────
async def get_grok_response(junk_desc: str, project_type: str) -> str:
    """Grok: Raw mechanical logic, grease-under-the-fingernails engineering."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {XAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "grok-3",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a Master Marine Diesel Mechanic and combat engineer with 30 years experience. "
                                "You think in raw components, torque specs, weld joints, and hydraulic pressures. "
                                "Be direct, technical, and practical. No fluff."
                            )
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Break down how to build a {project_type} using these parts: {junk_desc}. "
                                f"Cover: structural integrity, component reuse, mechanical feasibility, "
                                f"drive systems, and what tools are needed."
                            )
                        }
                    ],
                    "max_tokens": 1024
                }
            )
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[SHOP FOREMAN OFFLINE] Grok unavailable — proceeding with standard specs. Error: {str(e)}"

# ── THE PRECISION ENGINEER (Claude) ──────────────────────────────────────────
async def get_claude_response(junk_desc: str, project_type: str, grok_notes: str) -> str:
    """Claude: Control systems, Python code, electrical schematics. Now fully async."""
    try:
        message = await anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"You are a Precision Engineer specializing in embedded systems, Python automation, "
                        f"and electrical engineering.\n\n"
                        f"SHOP FOREMAN'S MECHANICAL NOTES:\n{grok_notes}\n\n"
                        f"TASK: Design the control system for a {project_type} built from: {junk_desc}\n\n"
                        f"Provide:\n"
                        f"1. ASCII wiring diagram\n"
                        f"2. Sensor integration plan\n"
                        f"3. Python control code skeleton\n"
                        f"4. Safety interlock system\n"
                        f"5. Power requirements"
                    )
                }
            ]
        )
        return message.content[0].text
    except Exception as e:
        return f"[PRECISION ENGINEER OFFLINE] Claude unavailable. Error: {str(e)}"

# ── THE GENERAL CONTRACTOR (Gemini) ──────────────────────────────────────────
async def get_gemini_response(
    junk_desc: str,
    project_type: str,
    grok_notes: str,
    claude_notes: str,
    detail_level: str = "Full Blueprint (All 3 Tiers)"
) -> str:
    """Gemini: Synthesizes all inputs into the final tiered blueprint. Now fully async."""
    detail_instruction = DETAIL_PROMPTS.get(detail_level, DETAIL_PROMPTS["Full Blueprint (All 3 Tiers)"])

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"""You are the General Contractor overseeing a Round Table of elite engineers.

SHOP FOREMAN (Grok) — MECHANICAL ANALYSIS:
{grok_notes}

PRECISION ENGINEER (Claude) — ELECTRICAL & CODE:
{claude_notes}

YOUR TASK: Synthesize a legendary tiered blueprint for a {project_type} built from: {junk_desc}

DETAIL LEVEL: {detail_instruction}

Format your response EXACTLY as follows:

## 🏗️ LEGENDARY BLUEPRINT: {project_type.upper()}

---

### ⚙️ NOVICE TIER — The Basic Build
*(Minimum tools, maximum safety, proven methods)*
[Detailed steps for beginners]

---

### 🔧 JOURNEYMAN TIER — Enhanced Build
*(Intermediate capabilities, improved performance)*
[Detailed steps for experienced builders]

---

### ⚡ MASTER TIER — Full Integration
*(All systems, maximum performance, full Python control)*
[Detailed steps for master builders]

---

### 📋 PARTS MANIFEST
*(Every component and its new purpose)*
[Itemized list]

---

### ⚠️ SAFETY PROTOCOLS
*(Non-negotiable safety requirements)*
[Critical safety items]

---

**Always wear PPE. No weapons. Build for the future.**
"""
        # Use async generation to avoid blocking the event loop
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        return f"[GENERAL CONTRACTOR OFFLINE] Gemini unavailable. Error: {str(e)}"

# ── Database Save ─────────────────────────────────────────────────────────────
def save_build(
    junk_desc: str,
    project_type: str,
    user_email: str,
    blueprint: str,
    grok_notes: str,
    claude_notes: str
) -> Optional[int]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO builds
                    (user_email, junk_desc, project_type, blueprint, grok_notes, claude_notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (user_email, junk_desc, project_type, blueprint, grok_notes, claude_notes, datetime.utcnow()))
            build_id = cur.fetchone()[0]

            # ── Bug Fix 3.1: Increment build_count on the user's license ──
            if user_email not in ("admin", "anonymous"):
                cur.execute("""
                    UPDATE licenses SET build_count = build_count + 1
                    WHERE email = %s AND status = 'active'
                """, (user_email,))

            conn.commit()
            return build_id
    except Exception as e:
        conn.rollback()
        print(f"DB Save Error: {e}")
        return None
    finally:
        put_conn(conn)

# ── ENDPOINTS ─────────────────────────────────────────────────────────────────
@app.post("/generate")
async def generate_blueprint(
    req: BuildRequest,
    x_internal_key: str = Header(None)
):
    if not verify_key(x_internal_key):
        raise HTTPException(status_code=403, detail="Invalid Security Badge")

    # ── 2.3: INPUT VALIDATION ──
    if len(req.junk_desc) > 5000:
        raise HTTPException(status_code=400, detail="Parts description too long (max 5,000 characters).")
    if len(req.project_type) > 200:
        raise HTTPException(status_code=400, detail="Project type too long (max 200 characters).")
    if not req.junk_desc.strip():
        raise HTTPException(status_code=400, detail="Parts description cannot be empty.")

    # ── BUILD LIMIT CHECK ──
    # Queries the licenses table directly (can't be spoofed from UI)
    # Runs in thread since it uses synchronous psycopg2
    limits = await asyncio.to_thread(check_build_limits, req.user_email)
    if not limits["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=limits.get("reason", "Build limit reached. Upgrade your plan.")
        )

    # ── THE ROUND TABLE ──
    # Step 1: Shop Foreman analyzes the parts
    grok_notes = await get_grok_response(req.junk_desc, req.project_type)

    # Step 2: Precision Engineer designs the control system
    claude_notes = await get_claude_response(req.junk_desc, req.project_type, grok_notes)

    # Step 3: General Contractor synthesizes the final blueprint
    final_blueprint = await get_gemini_response(
        req.junk_desc, req.project_type, grok_notes, claude_notes, req.detail_level
    )

    # Save everything to the database (runs in thread to avoid blocking)
    build_id = await asyncio.to_thread(
        save_build,
        req.junk_desc, req.project_type, req.user_email,
        final_blueprint, grok_notes, claude_notes
    )

    return {
        "content": final_blueprint,
        "build_id": build_id,
        "round_table": {
            "foreman": grok_notes,
            "engineer": claude_notes,
            "contractor": final_blueprint
        },
        "usage": {
            "tier":       limits["tier"],
            "used":       limits["used"] + 1,
            "limit":      limits["limit"],
            "remaining":  max(0, limits["remaining"] - 1)
        }
    }

@app.get("/builds")
async def get_all_builds(x_internal_key: str = Header(None), user_email: str = None):
    if not verify_key(x_internal_key):
        raise HTTPException(status_code=403, detail="Unauthorized")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if user_email:
                cur.execute("""
                    SELECT id, user_email, project_type, junk_desc, created_at
                    FROM builds WHERE user_email = %s
                    ORDER BY created_at DESC LIMIT 100
                """, (user_email,))
            else:
                cur.execute("""
                    SELECT id, user_email, project_type, junk_desc, created_at
                    FROM builds ORDER BY created_at DESC LIMIT 100
                """)
            rows = cur.fetchall()
    finally:
        put_conn(conn)

    return [
        {"id": r[0], "email": r[1], "type": r[2], "parts": r[3][:80], "created": str(r[4])}
        for r in rows
    ]

@app.get("/builds/{build_id}")
async def get_build(build_id: int, x_internal_key: str = Header(None)):
    if not verify_key(x_internal_key):
        raise HTTPException(status_code=403, detail="Unauthorized")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_email, junk_desc, project_type,
                       blueprint, grok_notes, claude_notes, tokens_used, created_at
                FROM builds WHERE id = %s
            """, (build_id,))
            row = cur.fetchone()
    finally:
        put_conn(conn)

    if not row:
        raise HTTPException(status_code=404, detail="Build not found")

    return {
        "id": row[0], "email": row[1], "junk_desc": row[2],
        "project_type": row[3], "blueprint": row[4],
        "grok_notes": row[5], "claude_notes": row[6], "created": str(row[8])
    }

@app.get("/health")
async def health():
    return {"status": "online", "engine": "roaring", "round_table": "active"}
