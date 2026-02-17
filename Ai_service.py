"""
ai_service.py — The Builder AI Service
=======================================
FastAPI service wrapping Groq. Handles prompt construction, rate limiting,
usage tracking, and structured error responses.

Deploy on Render as a separate Web Service.
Set env vars: GROQ_API_KEY, INTERNAL_API_KEY, DATABASE_URL
"""

import os
import logging
import sqlite3
from datetime import date, datetime
from contextlib import contextmanager

import httpx
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [AI] %(levelname)s %(message)s")
log = logging.getLogger("ai_service")

# ── Config ────────────────────────────────────────────────────────────────────
GROQ_API_KEY     = os.environ["GROQ_API_KEY"]
INTERNAL_API_KEY = os.environ["INTERNAL_API_KEY"]   # shared secret between services
DATABASE_URL     = os.environ.get("DATABASE_URL", "builder.db")
GROQ_MODEL       = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
DAILY_LIMIT      = int(os.environ.get("DAILY_BUILD_LIMIT", "20"))  # per license key

app = FastAPI(title="Builder AI Service", docs_url=None, redoc_url=None)


# ── DB setup ──────────────────────────────────────────────────────────────────
@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_usage_table():
    """Create usage tracking table if it doesn't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_tracking (
                license_key TEXT NOT NULL,
                usage_date  TEXT NOT NULL,
                build_count INTEGER DEFAULT 0,
                PRIMARY KEY (license_key, usage_date)
            )
        """)
    log.info("Usage tracking table ready")


init_usage_table()


# ── Auth dependency ───────────────────────────────────────────────────────────
def require_internal_key(x_internal_key: str = Header(None)):
    """Reject requests not from trusted internal services."""
    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return x_internal_key


# ── Rate limiting ─────────────────────────────────────────────────────────────
def check_and_increment_usage(license_key: str) -> dict:
    """
    Check if the key has hit daily limit. Increment if not.
    Returns {"allowed": bool, "used": int, "limit": int}
    """
    today = str(date.today())
    with get_db() as conn:
        row = conn.execute(
            "SELECT build_count FROM usage_tracking WHERE license_key=? AND usage_date=?",
            (license_key, today)
        ).fetchone()

        current = row["build_count"] if row else 0

        if current >= DAILY_LIMIT:
            return {"allowed": False, "used": current, "limit": DAILY_LIMIT}

        if row:
            conn.execute(
                "UPDATE usage_tracking SET build_count=build_count+1 WHERE license_key=? AND usage_date=?",
                (license_key, today)
            )
        else:
            conn.execute(
                "INSERT INTO usage_tracking (license_key, usage_date, build_count) VALUES (?,?,1)",
                (license_key, today)
            )

        return {"allowed": True, "used": current + 1, "limit": DAILY_LIMIT}


# ── Groq call ─────────────────────────────────────────────────────────────────
async def call_groq(junk_desc: str, project_type: str, image_desc: str, history_str: str) -> str:
    system_prompt = f"""
You are The Builder — Anthony's gritty, no-BS self-taught garage AI that turns junk into real functional battlefield robots.

Write everything in natural, complete flowing paragraphs. Never use bullet points or short lines. Use **bold** for section headers only.

Always include these sections in order:
**PARTS ANALYSIS** — full paragraph.
**ROBOT PROJECT IDEAS** — three detailed ideas in full paragraphs.
**BEST ROBOT BUILD** — the strongest idea in flowing paragraphs.
**BLUEPRINT** — clean ASCII diagram in a markdown code block.
**CONTROL CODE** — professional class-based Python using gpiozero with detailed comments.
**ADDITIONAL PARTS NEEDED** — paragraph listing cheap Home Depot parts.
**SAFETY NOTES** — practical garage safety warnings.

Past projects: {history_str}
User junk: {junk_desc}
Project focus: {project_type}
Image: {image_desc}

End every response with: "Anthony, what's next boss?"
"""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model":       GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": junk_desc},
                ],
                "temperature": 0.72,
                "max_tokens":  1800,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            log.error(f"Groq error response: {data['error']}")
            raise RuntimeError(f"Groq API error: {data['error'].get('message', 'Unknown')}")

        return data["choices"][0]["message"]["content"]


# ── Models ────────────────────────────────────────────────────────────────────
class ForgeRequest(BaseModel):
    license_key:  str
    junk_desc:    str
    project_type: str
    image_desc:   str = ""
    history:      list[str] = []


class UsageResponse(BaseModel):
    license_key: str
    date:        str
    used:        int
    limit:       int
    remaining:   int


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai", "model": GROQ_MODEL}


@app.post("/ai/forge")
async def forge(req: ForgeRequest, _=Depends(require_internal_key)):
    """
    Main forge endpoint. Checks rate limit, calls Groq, returns result.
    Called by the Streamlit UI service.
    """
    # 1. Rate limit check
    usage = check_and_increment_usage(req.license_key)
    if not usage["allowed"]:
        log.warning(f"Rate limit hit for {req.license_key} — {usage['used']}/{usage['limit']} today")
        raise HTTPException(
            status_code=429,
            detail={
                "message":   f"Daily build limit reached ({usage['limit']}/day). Resets at midnight.",
                "used":      usage["used"],
                "limit":     usage["limit"],
            }
        )

    log.info(f"Forge request — key: ...{req.license_key[-6:]}, type: {req.project_type}, usage: {usage['used']}/{usage['limit']}")

    # 2. Call Groq
    history_str = "\n".join(req.history[-10:]) if req.history else "No previous builds yet."
    try:
        result = await call_groq(req.junk_desc, req.project_type, req.image_desc, history_str)
    except httpx.HTTPStatusError as e:
        log.error(f"Groq HTTP error {e.response.status_code}: {e.response.text[:200]}")
        raise HTTPException(status_code=502, detail="AI service temporarily unavailable. Try again in a moment.")
    except httpx.TimeoutException:
        log.error("Groq request timed out")
        raise HTTPException(status_code=504, detail="AI service timed out. Try again.")
    except Exception as e:
        log.error(f"Unexpected Groq error: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong in the forge. Try again.")

    return {
        "result":  result,
        "usage":   usage,
    }


@app.get("/ai/usage/{license_key}")
async def get_usage(license_key: str, _=Depends(require_internal_key)) -> UsageResponse:
    """Return today's usage for a given license key."""
    today = str(date.today())
    with get_db() as conn:
        row = conn.execute(
            "SELECT build_count FROM usage_tracking WHERE license_key=? AND usage_date=?",
            (license_key, today)
        ).fetchone()
    used = row["build_count"] if row else 0
    return UsageResponse(
        license_key=license_key,
        date=today,
        used=used,
        limit=DAILY_LIMIT,
        remaining=max(0, DAILY_LIMIT - used),
    )


@app.get("/ai/usage-admin")
async def get_all_usage(
    target_date: str = str(date.today()),
    _=Depends(require_internal_key)
):
    """Admin: return all usage for a given date."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT license_key, build_count FROM usage_tracking WHERE usage_date=? ORDER BY build_count DESC",
            (target_date,)
        ).fetchall()
    return {
        "date":  target_date,
        "limit": DAILY_LIMIT,
        "usage": [{"key": r["license_key"][-6:] + "...", "builds": r["build_count"]} for r in rows],
        "total_builds": sum(r["build_count"] for r in rows),
    }
