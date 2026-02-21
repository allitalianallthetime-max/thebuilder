import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import httpx

app = FastAPI()

# ── Security Handshake ──────────────────────────────────────────────────────
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

class BuildRequest(BaseModel):
    junk_desc: str
    project_type: str

# ── The Round Table Logic ──────────────────────────────────────────────────
@app.post("/generate")
async def generate_blueprint(request: BuildRequest, x_internal_key: str = Header(None)):
    # 1. Verify Identity
    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # 2. Safety Filter (The Weapon Ban)
    ban_keywords = ["weapon", "gun", "explosive", "bomb", "attack", "lethal"]
    if any(word in request.junk_desc.lower() for word in ban_keywords):
        return {"content": "### ⚠️ Safety Violation\nThis request involves restricted content. The Forge only builds tools, robots, and mechanical solutions. No weapons."}

    # 3. Assemble the Round Table
    # Note: In a real deploy, we call the APIs for Grok, Claude, and Gemini here.
    # For now, we are structuring the GC (General Contractor) report.
    
    blueprint_template = f"""
# 📜 LEGENDARY BLUEPRINT: {request.project_type.upper()}

---

## 🛠️ THE MECHANICAL FOREMAN'S VIEW (Grok)
**Focus: Raw Durability & Torque**
* **Parts Evaluation**: Assessing {request.junk_desc} for structural integrity.
* **The Build**: Heavy-duty welding required for the frame. Use Grade 8 bolts for all high-stress joints.
* **Foreman's Tip**: If those hydraulic seals look worn, don't trust them. Replace before first fire.

## 📐 THE ENGINEER'S SCHEMATIC (Claude)
**Focus: Logic & Precision**
* **Control Systems**: Logic for the actuators should follow a 3-stage safety loop.
* **Power Distribution**: Ensure your amperage doesn't peak past the battery's discharge rating.
* **Code Implementation**: Use the provided Python script to calibrate the sensors.

## 🏗️ THE GENERAL CONTRACTOR'S PLAN (Gemini)
**Focus: Tiered Assembly & Safety**

### 🟢 NOVICE TIER (Hand Tools Only)
* Basic frame assembly and cleaning the scrap parts.

### 🟡 JOURNEYMAN TIER (Welding & Basic Wiring)
* Fabricating the mounting brackets and wiring the main power relay.

### 🔴 MASTER MECHANIC TIER (Complex Systems)
* Final hydraulic pressure testing and programming the AI controller.

---
**⚠️ WARNING: Do not exceed 500psi on initial tests. Wear eye protection.**
    """
    
    return {"content": blueprint_template}
