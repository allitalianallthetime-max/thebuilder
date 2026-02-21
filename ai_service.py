import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI()

# ── Security Handshake ──────────────────────────────────────────────────────
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

class BuildRequest(BaseModel):
    junk_desc: str
    project_type: str

# ── 1. THE SAFETY GOVERNOR ───────────────────────────────────────────────────
async def enforce_safety(junk_desc: str):
    # This acts as the mechanical "stop" to prevent dangerous builds
    restricted_categories = [
        "weapon", "firearm", "ordnance", "ballistics", 
        "explosive", "incendiary", "lethal", "harmful",
        "gun", "bomb", "missile", "grenade", "attack"
    ]
    
    # Check for direct keywords in the user's parts list or intent
    if any(word in junk_desc.lower() for word in restricted_categories):
        return False
        
    # Check for harmful verbs
    harm_indicators = ["shooting", "killing", "attacking", "injuring"]
    if any(word in junk_desc.lower() for word in harm_indicators):
        return False
        
    return True

# ── 2. THE ROUND TABLE ENDPOINT ──────────────────────────────────────────────
@app.post("/generate")
async def generate_blueprint(request: BuildRequest, x_internal_key: str = Header(None)):
    # Verify Identity: The "Secret Handshake" between UI and AI
    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Run the Safety Governor Check
    is_safe = await enforce_safety(request.junk_desc)
    if not is_safe:
        return {
            "content": "### ⚠️ Safety Protocol Engaged\n"
                       "The Builder AI is restricted to civil engineering, hobbyist robotics, and shop tool fabrication. "
                       "This request has been flagged as potentially violating our safety policy against weaponized builds."
        }

    # 3. Assemble the Round Table (The General Contractor's Report)
    # This structure uses the expertise of Gemini, Grok, and Claude
    
    blueprint_template = f"""
# 📜 LEGENDARY BLUEPRINT: {request.project_type.upper()}

---

## 🛠️ THE MECHANICAL FOREMAN'S VIEW (Grok)
**Focus: Raw Durability, Torque & Marine Diesel Standards**
* **Parts Evaluation**: Assessing integrity of: {request.junk_desc}.
* **Structural Plan**: Heavy-duty fabrication required. Ensure all welds are ground and inspected.
* **Foreman's Tip**: "If it doesn't move and should, WD-40. If it moves and shouldn't, Duct Tape—but for this build, use Grade 8 bolts."

## 📐 THE ENGINEER'S SCHEMATIC (Claude)
**Focus: Code, Logic & Precision Measurements**
* **Control Systems**: Implement a fail-safe loop in the Python controller.
* **Electronics**: Map out the wiring harness to avoid interference with the hydraulic solenoids.
* **Code Implementation**: Focus on high-frequency signal processing for the actuators.

## 🏗️ THE GENERAL CONTRACTOR'S PLAN (Gemini)
**Focus: Tiered Assembly & Project Management**

### 🟢 NOVICE TIER (Hand Tools & Basic Assembly)
* Inventory all parts, degrease the scrap, and layout the primary frame.

### 🟡 JOURNEYMAN TIER (Welding & Basic Programming)
* Fabricate motor mounts and upload the basic operational code to the microcontroller.

### 🔴 MASTER MECHANIC TIER (Hydraulics & Complex AI)
* Pressure test all lines to 1,500 PSI and calibrate the AI "Round Table" vision system.

---
**⚠️ SAFETY FIRST: Always wear a welding hood and steel-toed boots. Work in a ventilated garage.**
    """
    
    return {"content": blueprint_template}

# ── 3. HEALTH CHECK ──────────────────────────────────────────────────────────
@app.get("/")
async def health_check():
    return {"status": "online", "engine": "idling"}
