import os
import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI()

# ── API Keys: These must be set in your Render Environment ──────────────────
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 

class BuildRequest(BaseModel):
    junk_desc: str
    project_type: str

# ── 1. THE SAFETY GOVERNOR ───────────────────────────────────────────────────
async def enforce_safety(junk_desc: str):
    # Prevents the AI from processing any weaponized or harmful requests
    restricted = ["weapon", "firearm", "explosive", "bomb", "lethal", "gun", "attack"]
    if any(word in junk_desc.lower() for word in restricted):
        return False
    return True

# ── 2. THE SPECIALIST CALLS ──────────────────────────────────────────────────
async def get_grok_feedback(junk, p_type):
    # Reaching out to Grok for the mechanical "grit"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {XAI_API_KEY}"},
                json={
                    "model": "grok-beta",
                    "messages": [
                        {"role": "system", "content": "You are a Master Marine Diesel Mechanic. Focus on raw durability and torque."},
                        {"role": "user", "content": f"Practical build steps for a {p_type} using {junk}."}
                    ]
                },
                timeout=30.0
            )
            return response.json()['choices'][0]['message']['content']
        except:
            return "Grok is currently in the shop. Proceeding with standard mechanical specs."

async def get_claude_feedback(junk, p_type):
    # Reaching out to Claude for engineering precision and code
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-3-opus-20240229",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": f"Provide technical Python code and electrical logic for a {p_type} using {junk}."}]
                },
                timeout=30.0
            )
            return response.json()['content'][0]['text']
        except:
            return "Claude is calibrating sensors. Refer to standard logic diagrams."

# ── 3. THE ROUND TABLE (Main Endpoint) ───────────────────────────────────────
@app.post("/generate")
async def generate_blueprint(request: BuildRequest, x_internal_key: str = Header(None)):
    # Verify the "Secret Handshake"
    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Check for weapons/harm
    if not await enforce_safety(request.junk_desc):
        return {"content": "⚠️ **SAFETY VIOLATION**: The Forge does not build weapons. Only tools and robots."}

    # Gather the Round Table Expertise
    grok_notes = await get_grok_feedback(request.junk_desc, request.project_type)
    claude_notes = await get_claude_feedback(request.junk_desc, request.project_type)
    
    # Final Tiered Report
    final_report = f"""
# 📜 LEGENDARY BLUEPRINT: {request.project_type.upper()}

## 🛠️ THE FOREMAN'S VIEW (Grok)
{grok_notes}

## 📐 THE ENGINEER'S SCHEMATIC (Claude)
{claude_notes}

## 🏗️ THE GENERAL CONTRACTOR'S SUMMARY (Gemini)
* **Novice**: Prep and inventory your {request.junk_desc}.
* **Journeyman**: Follow the Foreman's welding and structural specs.
* **Master**: Implement the Engineer's control code and logic loops.

---
**⚠️ Always wear PPE. No weapons. Build for the future.**
    """
    return {"content": final_report}

@app.get("/")
async def health():
    return {"status": "online", "engine": "roaring"}
