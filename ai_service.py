import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
from openai import OpenAI  # <--- NEW SEAT AT THE TABLE
import httpx

app = FastAPI()

# --- CONFIGURATION ---
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class BuildRequest(BaseModel):
    junk_desc: str
    project_type: str

@app.post("/generate")
async def generate_blueprint(req: BuildRequest, x_internal_key: str = Header(None)):
    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid Security Badge")

    # 1. THE FOREMAN (Grok/X-AI) - Mechanical Logic
    # (Assuming xAI integration logic here)
    
    # 2. THE SPECIALIST (ChatGPT/OpenAI) - Creative Problem Solving
    gpt_response = openai_client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": f"You are a Specialist Engineer. Design a {req.project_type} using: {req.junk_desc}"}]
    )
    gpt_blueprint = gpt_response.choices[0].message.content

    # 3. THE GENERAL CONTRACTOR (Gemini Ultra) - Master Oversight & Argument
    model = genai.GenerativeModel('gemini-1.5-pro') # Upgrade to Ultra/Pro
    prompt = f"""
    You are the General Contractor. Review the Specialist's blueprint: {gpt_blueprint}.
    Challenge any flaws in the mechanical logic for a {req.project_type}.
    Finalize the blueprint with Novice, Journeyman, and Master tiers.
    """
    gemini_response = model.generate_content(prompt)
    
    return {"content": gemini_response.text}
