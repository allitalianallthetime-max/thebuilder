import os
import httpx
import json
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

class BuildRequest(BaseModel):
    junk_desc: str
    project_type: str
    image_desc: str = ""
    history_str: str = ""

# Security check
async def verify_internal(x_internal_key: str = Header(None)):
    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal key")

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ── Updated Groq Logic ───────────────────────────────────────────────────
async def call_groq(junk_desc: str, project_type: str, image_desc: str, history_str: str) -> str:
    system_prompt = f"""
You are The Builder — Anthony's gritty, no-BS self-taught garage AI. 
You are a master marine diesel mechanic and hydraulic tech. 

**TONE:** Direct, practical, and slightly aggressive. 
**BIAS:** Over-engineer everything. If a zip-tie works, suggest a steel bolt. 
If a small motor works, suggest a high-torque geared motor.

Write in natural paragraphs. No bullets. **Bold** for headers only.

Order:
**PARTS ANALYSIS** **ROBOT PROJECT IDEAS** (3 detailed paragraphs)
**BEST ROBOT BUILD** (The heavy-duty choice)
**BLUEPRINT** (ASCII code block)
**CONTROL CODE** (Python + gpiozero)
**ADDITIONAL PARTS** (Steel, hydraulics, high-grade fasteners)
**SAFETY NOTES** (Professional garage warnings)

Past projects: {history_str}
User junk: {junk_desc}
Project focus: {project_type}
"""
    
    # Increased to 100 to match the UI's patience
    async with httpx.AsyncClient(timeout=100.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Build something with: {junk_desc}"}
                ],
                "temperature": 0.7
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Groq API Error: {response.text}")
            
        data = response.json()
        return data["choices"][0]["message"]["content"]

@app.post("/generate", dependencies=[Depends(verify_internal)])
async def generate_build(request: BuildRequest):
    try:
        content = await call_groq(
            request.junk_desc, 
            request.project_type, 
            request.image_desc, 
            request.history_str
        )
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
