"""
workshop_service.py — The Shop Floor
======================================
Turns blueprints into tracked build projects.
AI-powered parts teardown, phase-gated workflow,
task management, inventory tracking, and safety gates.

This is where blueprints become REAL BUILDS.

Endpoints:
── PROJECTS ──
  POST /projects/create            — Create project from a blueprint
  GET  /projects                   — List all projects
  GET  /projects/{id}              — Full project detail
  PATCH /projects/{id}/phase       — Advance to next phase
  DELETE /projects/{id}            — Archive a project

── TASKS ──
  GET  /projects/{id}/tasks        — All tasks for a project
  PATCH /projects/{id}/tasks/{tid} — Toggle task completion
  POST /projects/{id}/tasks        — Add a custom task
  POST /projects/{id}/notes        — Add a build note/log entry

── PARTS INTELLIGENCE ──
  POST /parts/analyze              — AI teardown: junk description → structured parts list
  GET  /projects/{id}/parts        — Parts checklist for a project
  PATCH /projects/{id}/parts/{pid} — Update part status (sourced/installed/missing)

── STATS ──
  GET  /workshop/stats             — Workshop-wide statistics
  GET  /health
"""

import os
import json
import secrets
import asyncio
import logging
import psycopg2
import psycopg2.pool
import google.generativeai as genai
from fastapi import FastAPI, Header, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from typing import Optional, List
from contextlib import contextmanager
from datetime import datetime
from dotenv import load_dotenv
import base64
import re

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [WORKSHOP] %(levelname)s %(message)s")
log = logging.getLogger("workshop")

app = FastAPI()

# ── Configuration ─────────────────────────────────────────────────────────────
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
DATABASE_URL     = os.getenv("DATABASE_URL")
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

# ── Database ──────────────────────────────────────────────────────────────────
db_pool = None

def init_pool():
    global db_pool
    try:
        db_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, DATABASE_URL)
        log.info("Connection pool initialized.")
    except Exception as e:
        log.warning(f"Pool init: {e}")

@contextmanager
def get_db():
    conn = None
    try:
        conn = db_pool.getconn() if db_pool else psycopg2.connect(DATABASE_URL)
        yield conn
    finally:
        if conn:
            if db_pool:
                db_pool.putconn(conn)
            else:
                conn.close()

# ── Phase Definitions ─────────────────────────────────────────────────────────
# These are the build phases every project goes through.
# Each phase has a safety gate — you can't advance without confirming safety.
PHASES = [
    {
        "key":   "planning",
        "name":  "PLANNING & TEARDOWN",
        "icon":  "📐",
        "desc":  "Strip donor equipment, inventory parts, plan the build.",
        "gate":  "Confirm: All parts inventoried, workspace cleared, PPE staged."
    },
    {
        "key":   "fabrication",
        "name":  "FABRICATION",
        "icon":  "🔥",
        "desc":  "Cut, weld, machine, and prepare all structural components.",
        "gate":  "Confirm: All welds inspected, measurements verified, no cracks."
    },
    {
        "key":   "assembly",
        "name":  "ASSEMBLY",
        "icon":  "🔩",
        "desc":  "Assemble mechanical systems, mount components, route wiring.",
        "gate":  "Confirm: All fasteners torqued to spec, wiring secured, no shorts."
    },
    {
        "key":   "electrical",
        "name":  "ELECTRICAL & CODE",
        "icon":  "⚡",
        "desc":  "Wire control systems, upload firmware, configure sensors.",
        "gate":  "Confirm: All circuits tested, grounds verified, code uploaded."
    },
    {
        "key":   "testing",
        "name":  "TESTING & VALIDATION",
        "icon":  "🧪",
        "desc":  "Power up, run diagnostics, stress test, validate safety systems.",
        "gate":  "Confirm: All systems nominal, safety interlocks functional, documented."
    },
    {
        "key":   "complete",
        "name":  "BUILD COMPLETE",
        "icon":  "🏆",
        "desc":  "Project finished. Document lessons learned.",
        "gate":  None
    }
]

PHASE_KEYS = [p["key"] for p in PHASES]

# ── Schema Init ───────────────────────────────────────────────────────────────
def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS workshop_projects (
                    id              SERIAL PRIMARY KEY,
                    build_id        INTEGER REFERENCES builds(id),
                    user_email      TEXT DEFAULT 'anonymous',
                    title           TEXT NOT NULL,
                    project_type    TEXT NOT NULL,
                    junk_desc       TEXT,
                    current_phase   TEXT DEFAULT 'planning',
                    difficulty      INTEGER DEFAULT 5,
                    est_hours       REAL DEFAULT 0,
                    est_cost        REAL DEFAULT 0,
                    status          TEXT DEFAULT 'active',
                    created_at      TIMESTAMP DEFAULT NOW(),
                    updated_at      TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS workshop_tasks (
                    id           SERIAL PRIMARY KEY,
                    project_id   INTEGER REFERENCES workshop_projects(id) ON DELETE CASCADE,
                    phase        TEXT NOT NULL,
                    title        TEXT NOT NULL,
                    description  TEXT,
                    is_complete  BOOLEAN DEFAULT FALSE,
                    is_safety    BOOLEAN DEFAULT FALSE,
                    sort_order   INTEGER DEFAULT 0,
                    completed_at TIMESTAMP,
                    created_at   TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS workshop_parts (
                    id           SERIAL PRIMARY KEY,
                    project_id   INTEGER REFERENCES workshop_projects(id) ON DELETE CASCADE,
                    name         TEXT NOT NULL,
                    category     TEXT DEFAULT 'general',
                    source       TEXT DEFAULT 'salvage',
                    quantity     INTEGER DEFAULT 1,
                    status       TEXT DEFAULT 'needed',
                    est_value    REAL DEFAULT 0,
                    notes        TEXT,
                    created_at   TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS workshop_notes (
                    id           SERIAL PRIMARY KEY,
                    project_id   INTEGER REFERENCES workshop_projects(id) ON DELETE CASCADE,
                    phase        TEXT,
                    content      TEXT NOT NULL,
                    note_type    TEXT DEFAULT 'log',
                    created_at   TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS equipment_scans (
                    id              SERIAL PRIMARY KEY,
                    user_email      TEXT DEFAULT 'anonymous',
                    image_hash      TEXT,
                    equipment_name  TEXT,
                    manufacturer    TEXT,
                    model           TEXT,
                    year_range      TEXT,
                    category        TEXT,
                    scan_result     JSONB,
                    parts_found     INTEGER DEFAULT 0,
                    est_salvage     REAL DEFAULT 0,
                    hazard_level    TEXT DEFAULT 'low',
                    status          TEXT DEFAULT 'scanned',
                    created_at      TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
    log.info("Workshop tables initialized.")

try:
    init_pool()
    init_db()
except Exception as e:
    log.warning(f"DB Init: {e}")

# ── Security ──────────────────────────────────────────────────────────────────
async def verify(x_internal_key: str = Header(None)):
    if not x_internal_key or not INTERNAL_API_KEY or \
       not secrets.compare_digest(x_internal_key, INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Unauthorized")

# ── Request Models ────────────────────────────────────────────────────────────
class CreateProjectRequest(BaseModel):
    build_id:     Optional[int] = None
    user_email:   str = "anonymous"
    title:        str
    project_type: str
    junk_desc:    str = ""
    blueprint:    str = ""

class AdvancePhaseRequest(BaseModel):
    safety_confirmed: bool = False

class UpdateTaskRequest(BaseModel):
    is_complete: bool

class AddTaskRequest(BaseModel):
    phase:       str
    title:       str
    description: str = ""
    is_safety:   bool = False

class AddNoteRequest(BaseModel):
    phase:     str = ""
    content:   str
    note_type: str = "log"

class UpdatePartRequest(BaseModel):
    status: str

class AnalyzePartsRequest(BaseModel):
    junk_desc:    str
    project_type: str = ""

class ScanImageRequest(BaseModel):
    image_base64: str
    user_email:   str = "anonymous"
    context:      str = ""

# ══════════════════════════════════════════════════════════════════════════════
#   AI PARTS INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════
async def ai_analyze_parts(junk_desc: str, project_type: str) -> dict:
    """Use Gemini to tear down a junk description into structured parts data."""
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"""You are an expert salvage engineer and mechanical teardown specialist.

EQUIPMENT TO TEAR DOWN:
{junk_desc}

TARGET BUILD: {project_type or 'General purpose'}

Analyze this equipment and return a JSON object with EXACTLY this structure (no markdown, no backticks, just raw JSON):

{{
    "parts": [
        {{
            "name": "Component name",
            "category": "one of: structural, electrical, mechanical, hydraulic, pneumatic, sensor, motor, pump, valve, wiring, fastener, electronic, raw_material, other",
            "quantity": 1,
            "source": "one of: salvage, purchase, fabricate",
            "est_value": 0.00,
            "notes": "Brief note on condition/reuse potential"
        }}
    ],
    "difficulty": 7,
    "est_hours": 40,
    "est_cost": 250.00,
    "safety_warnings": ["Warning 1", "Warning 2"],
    "tools_required": ["Tool 1", "Tool 2"],
    "tasks": {{
        "planning": ["Task 1", "Task 2"],
        "fabrication": ["Task 1", "Task 2"],
        "assembly": ["Task 1", "Task 2"],
        "electrical": ["Task 1", "Task 2"],
        "testing": ["Task 1", "Task 2"]
    }}
}}

Be thorough. Extract EVERY salvageable component. Estimate realistic values and hours.
Difficulty is 1-10 (1=beginner, 10=master fabricator).
Return ONLY valid JSON. No explanation text."""

        response = await model.generate_content_async(prompt)
        text = response.text.strip()

        # Clean markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

        return json.loads(text)

    except json.JSONDecodeError as e:
        log.error(f"AI returned invalid JSON: {e}")
        return {"parts": [], "difficulty": 5, "est_hours": 0, "est_cost": 0,
                "safety_warnings": [], "tools_required": [],
                "tasks": {"planning": [], "fabrication": [], "assembly": [], "electrical": [], "testing": []},
                "error": "AI response was not valid JSON"}
    except Exception as e:
        log.error(f"Parts analysis failed: {e}")
        return {"parts": [], "difficulty": 5, "est_hours": 0, "est_cost": 0,
                "safety_warnings": [], "tools_required": [],
                "tasks": {"planning": [], "fabrication": [], "assembly": [], "electrical": [], "testing": []},
                "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
#   ENDPOINTS — PROJECTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "workshop", "phases": len(PHASES)}


@app.post("/projects/create")
async def create_project(req: CreateProjectRequest, x_internal_key: str = Header(None)):
    """Create a new workshop project, optionally from an existing blueprint.
    Runs AI parts analysis to populate tasks and parts automatically."""
    await verify(x_internal_key)

    log.info(f"Creating project: {req.title} for {req.user_email}")

    # Run AI analysis on the junk description
    analysis = {}
    if req.junk_desc:
        analysis = await ai_analyze_parts(req.junk_desc, req.project_type)

    difficulty = analysis.get("difficulty", 5)
    est_hours  = analysis.get("est_hours", 0)
    est_cost   = analysis.get("est_cost", 0)

    with get_db() as conn:
        with conn.cursor() as cur:
            # Create the project
            cur.execute("""
                INSERT INTO workshop_projects
                    (build_id, user_email, title, project_type, junk_desc,
                     difficulty, est_hours, est_cost)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (req.build_id, req.user_email, req.title, req.project_type,
                  req.junk_desc, difficulty, est_hours, est_cost))
            project_id = cur.fetchone()[0]

            # Insert AI-generated tasks per phase
            tasks_data = analysis.get("tasks", {})
            sort = 0
            for phase_key in PHASE_KEYS[:-1]:  # skip 'complete'
                phase_tasks = tasks_data.get(phase_key, [])
                for task_title in phase_tasks:
                    if isinstance(task_title, str) and task_title.strip():
                        sort += 1
                        cur.execute("""
                            INSERT INTO workshop_tasks
                                (project_id, phase, title, sort_order)
                            VALUES (%s, %s, %s, %s)
                        """, (project_id, phase_key, task_title.strip(), sort))

            # Insert safety gate tasks for each phase
            for phase in PHASES:
                if phase["gate"]:
                    sort += 1
                    cur.execute("""
                        INSERT INTO workshop_tasks
                            (project_id, phase, title, description, is_safety, sort_order)
                        VALUES (%s, %s, %s, %s, TRUE, %s)
                    """, (project_id, phase["key"],
                          f"⛑ SAFETY GATE: {phase['name']}",
                          phase["gate"], sort))

            # Insert AI-identified parts
            for part in analysis.get("parts", []):
                if isinstance(part, dict) and part.get("name"):
                    cur.execute("""
                        INSERT INTO workshop_parts
                            (project_id, name, category, source, quantity, est_value, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (project_id, part["name"],
                          part.get("category", "general"),
                          part.get("source", "salvage"),
                          part.get("quantity", 1),
                          part.get("est_value", 0),
                          part.get("notes", "")))

            # Insert safety warnings as notes
            for warning in analysis.get("safety_warnings", []):
                cur.execute("""
                    INSERT INTO workshop_notes
                        (project_id, phase, content, note_type)
                    VALUES (%s, 'planning', %s, 'safety')
                """, (project_id, f"⚠️ {warning}"))

            # Insert tools required as a planning note
            tools = analysis.get("tools_required", [])
            if tools:
                tools_text = "TOOLS REQUIRED:\n" + "\n".join(f"  • {t}" for t in tools)
                cur.execute("""
                    INSERT INTO workshop_notes
                        (project_id, phase, content, note_type)
                    VALUES (%s, 'planning', %s, 'tools')
                """, (project_id, tools_text))

            conn.commit()

    log.info(f"Project #{project_id} created with {len(analysis.get('parts', []))} parts, "
             f"{sum(len(v) for v in tasks_data.values() if isinstance(v, list))} tasks")

    return {
        "project_id":  project_id,
        "title":       req.title,
        "difficulty":  difficulty,
        "est_hours":   est_hours,
        "est_cost":    est_cost,
        "parts_count": len(analysis.get("parts", [])),
        "tasks_count": sum(len(v) for v in tasks_data.values() if isinstance(v, list)),
        "analysis":    analysis
    }


@app.get("/projects")
async def list_projects(x_internal_key: str = Header(None),
                        user_email: str = None, status: str = "active"):
    """List all projects, optionally filtered by user and status."""
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT p.id, p.build_id, p.user_email, p.title, p.project_type,
                       p.current_phase, p.difficulty, p.est_hours, p.est_cost,
                       p.status, p.created_at, p.updated_at,
                       COUNT(DISTINCT t.id) as total_tasks,
                       COUNT(DISTINCT t.id) FILTER (WHERE t.is_complete) as done_tasks,
                       COUNT(DISTINCT pt.id) as total_parts,
                       COUNT(DISTINCT pt.id) FILTER (WHERE pt.status = 'installed') as installed_parts
                FROM workshop_projects p
                LEFT JOIN workshop_tasks t ON t.project_id = p.id
                LEFT JOIN workshop_parts pt ON pt.project_id = p.id
                WHERE p.status = %s
            """
            params = [status]

            if user_email:
                query += " AND p.user_email = %s"
                params.append(user_email)

            query += " GROUP BY p.id ORDER BY p.updated_at DESC"
            cur.execute(query, params)
            rows = cur.fetchall()

    return [
        {
            "id": r[0], "build_id": r[1], "user_email": r[2],
            "title": r[3], "project_type": r[4], "current_phase": r[5],
            "difficulty": r[6], "est_hours": r[7], "est_cost": r[8],
            "status": r[9], "created_at": str(r[10]), "updated_at": str(r[11]),
            "progress": {
                "total_tasks": r[12], "done_tasks": r[13],
                "total_parts": r[14], "installed_parts": r[15],
                "percent": round((r[13] / r[12] * 100) if r[12] > 0 else 0)
            }
        }
        for r in rows
    ]


@app.get("/projects/{project_id}")
async def get_project(project_id: int, x_internal_key: str = Header(None)):
    """Full project detail including all tasks, parts, and notes."""
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            # Project
            cur.execute("""
                SELECT id, build_id, user_email, title, project_type, junk_desc,
                       current_phase, difficulty, est_hours, est_cost,
                       status, created_at, updated_at
                FROM workshop_projects WHERE id = %s
            """, (project_id,))
            proj = cur.fetchone()

            if not proj:
                raise HTTPException(status_code=404, detail="Project not found")

            # Tasks grouped by phase
            cur.execute("""
                SELECT id, phase, title, description, is_complete, is_safety,
                       sort_order, completed_at
                FROM workshop_tasks WHERE project_id = %s
                ORDER BY sort_order, id
            """, (project_id,))
            tasks = cur.fetchall()

            # Parts
            cur.execute("""
                SELECT id, name, category, source, quantity, status,
                       est_value, notes
                FROM workshop_parts WHERE project_id = %s
                ORDER BY category, name
            """, (project_id,))
            parts = cur.fetchall()

            # Notes
            cur.execute("""
                SELECT id, phase, content, note_type, created_at
                FROM workshop_notes WHERE project_id = %s
                ORDER BY created_at DESC
            """, (project_id,))
            notes = cur.fetchall()

    # Build phase map with tasks
    phases_out = []
    for phase_def in PHASES:
        phase_tasks = [
            {
                "id": t[0], "title": t[2], "description": t[3],
                "is_complete": t[4], "is_safety": t[5],
                "completed_at": str(t[7]) if t[7] else None
            }
            for t in tasks if t[1] == phase_def["key"]
        ]
        done = sum(1 for t in phase_tasks if t["is_complete"])
        phases_out.append({
            **phase_def,
            "tasks": phase_tasks,
            "done":  done,
            "total": len(phase_tasks),
            "is_current": phase_def["key"] == proj[6]
        })

    total_tasks = len(tasks)
    done_tasks  = sum(1 for t in tasks if t[4])

    return {
        "id": proj[0], "build_id": proj[1], "user_email": proj[2],
        "title": proj[3], "project_type": proj[4], "junk_desc": proj[5],
        "current_phase": proj[6], "difficulty": proj[7],
        "est_hours": proj[8], "est_cost": proj[9],
        "status": proj[10], "created_at": str(proj[11]),
        "updated_at": str(proj[12]),
        "progress_percent": round((done_tasks / total_tasks * 100) if total_tasks > 0 else 0),
        "phases": phases_out,
        "parts": [
            {
                "id": p[0], "name": p[1], "category": p[2], "source": p[3],
                "quantity": p[4], "status": p[5], "est_value": p[6], "notes": p[7]
            }
            for p in parts
        ],
        "notes": [
            {
                "id": n[0], "phase": n[1], "content": n[2],
                "note_type": n[3], "created_at": str(n[4])
            }
            for n in notes
        ],
        "parts_summary": {
            "total":     len(parts),
            "needed":    sum(1 for p in parts if p[5] == "needed"),
            "sourced":   sum(1 for p in parts if p[5] == "sourced"),
            "installed": sum(1 for p in parts if p[5] == "installed"),
            "total_value": round(sum(p[6] for p in parts), 2)
        }
    }


@app.patch("/projects/{project_id}/phase")
async def advance_phase(project_id: int, req: AdvancePhaseRequest,
                        x_internal_key: str = Header(None)):
    """Advance project to next phase. Requires safety gate confirmation."""
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_phase FROM workshop_projects WHERE id = %s", (project_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Project not found")

            current = row[0]
            idx = PHASE_KEYS.index(current) if current in PHASE_KEYS else 0

            if idx >= len(PHASE_KEYS) - 1:
                raise HTTPException(status_code=400, detail="Project already complete")

            # Check safety gate
            if not req.safety_confirmed:
                gate = PHASES[idx]["gate"]
                raise HTTPException(status_code=400,
                    detail=f"Safety gate not confirmed: {gate}")

            # Check all safety tasks in current phase are complete
            cur.execute("""
                SELECT COUNT(*) FROM workshop_tasks
                WHERE project_id = %s AND phase = %s AND is_safety = TRUE AND is_complete = FALSE
            """, (project_id, current))
            unchecked = cur.fetchone()[0]
            if unchecked > 0:
                raise HTTPException(status_code=400,
                    detail=f"{unchecked} safety task(s) still incomplete in {current} phase")

            next_phase = PHASE_KEYS[idx + 1]
            cur.execute("""
                UPDATE workshop_projects
                SET current_phase = %s, updated_at = NOW()
                WHERE id = %s
            """, (next_phase, project_id))

            # Log the phase transition
            cur.execute("""
                INSERT INTO workshop_notes (project_id, phase, content, note_type)
                VALUES (%s, %s, %s, 'phase_change')
            """, (project_id, next_phase,
                  f"Phase advanced: {current} → {next_phase}"))

            conn.commit()

    log.info(f"Project #{project_id}: {current} → {next_phase}")
    return {"project_id": project_id, "previous_phase": current,
            "current_phase": next_phase, "phase_info": PHASES[idx + 1]}


# ══════════════════════════════════════════════════════════════════════════════
#   ENDPOINTS — TASKS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/projects/{project_id}/tasks")
async def get_tasks(project_id: int, phase: str = None,
                    x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT id, phase, title, description, is_complete, is_safety,
                       sort_order, completed_at
                FROM workshop_tasks WHERE project_id = %s
            """
            params = [project_id]
            if phase:
                query += " AND phase = %s"
                params.append(phase)
            query += " ORDER BY sort_order, id"
            cur.execute(query, params)
            rows = cur.fetchall()

    return [
        {
            "id": r[0], "phase": r[1], "title": r[2], "description": r[3],
            "is_complete": r[4], "is_safety": r[5], "sort_order": r[6],
            "completed_at": str(r[7]) if r[7] else None
        }
        for r in rows
    ]


@app.patch("/projects/{project_id}/tasks/{task_id}")
async def toggle_task(project_id: int, task_id: int, req: UpdateTaskRequest,
                      x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            completed_at = datetime.utcnow() if req.is_complete else None
            cur.execute("""
                UPDATE workshop_tasks
                SET is_complete = %s, completed_at = %s
                WHERE id = %s AND project_id = %s
                RETURNING phase, title
            """, (req.is_complete, completed_at, task_id, project_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Task not found")

            # Update project timestamp
            cur.execute("UPDATE workshop_projects SET updated_at = NOW() WHERE id = %s",
                        (project_id,))
            conn.commit()

    return {"task_id": task_id, "is_complete": req.is_complete,
            "phase": row[0], "title": row[1]}


@app.post("/projects/{project_id}/tasks")
async def add_task(project_id: int, req: AddTaskRequest,
                   x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO workshop_tasks
                    (project_id, phase, title, description, is_safety, sort_order)
                VALUES (%s, %s, %s, %s, %s,
                    (SELECT COALESCE(MAX(sort_order), 0) + 1
                     FROM workshop_tasks WHERE project_id = %s))
                RETURNING id
            """, (project_id, req.phase, req.title, req.description,
                  req.is_safety, project_id))
            task_id = cur.fetchone()[0]
            conn.commit()

    return {"task_id": task_id, "phase": req.phase, "title": req.title}


@app.post("/projects/{project_id}/notes")
async def add_note(project_id: int, req: AddNoteRequest,
                   x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO workshop_notes (project_id, phase, content, note_type)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (project_id, req.phase, req.content, req.note_type))
            note_id = cur.fetchone()[0]
            cur.execute("UPDATE workshop_projects SET updated_at = NOW() WHERE id = %s",
                        (project_id,))
            conn.commit()

    return {"note_id": note_id}


# ══════════════════════════════════════════════════════════════════════════════
#   ENDPOINTS — PARTS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/parts/analyze")
async def analyze_parts(req: AnalyzePartsRequest, x_internal_key: str = Header(None)):
    """Standalone parts intelligence — analyze junk without creating a project."""
    await verify(x_internal_key)

    analysis = await ai_analyze_parts(req.junk_desc, req.project_type)
    return {"analysis": analysis}


@app.get("/projects/{project_id}/parts")
async def get_parts(project_id: int, x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, category, source, quantity, status, est_value, notes
                FROM workshop_parts WHERE project_id = %s
                ORDER BY category, name
            """, (project_id,))
            rows = cur.fetchall()

    parts = [
        {
            "id": r[0], "name": r[1], "category": r[2], "source": r[3],
            "quantity": r[4], "status": r[5], "est_value": r[6], "notes": r[7]
        }
        for r in rows
    ]

    return {
        "parts": parts,
        "summary": {
            "total":     len(parts),
            "needed":    sum(1 for p in parts if p["status"] == "needed"),
            "sourced":   sum(1 for p in parts if p["status"] == "sourced"),
            "installed": sum(1 for p in parts if p["status"] == "installed"),
            "total_value": round(sum(p["est_value"] for p in parts), 2)
        }
    }


@app.patch("/projects/{project_id}/parts/{part_id}")
async def update_part_status(project_id: int, part_id: int,
                             req: UpdatePartRequest,
                             x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    valid = ["needed", "sourced", "installed", "missing"]
    if req.status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid}")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE workshop_parts SET status = %s
                WHERE id = %s AND project_id = %s RETURNING name
            """, (req.status, part_id, project_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Part not found")
            cur.execute("UPDATE workshop_projects SET updated_at = NOW() WHERE id = %s",
                        (project_id,))
            conn.commit()

    return {"part_id": part_id, "name": row[0], "status": req.status}


@app.delete("/projects/{project_id}")
async def archive_project(project_id: int, x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE workshop_projects SET status = 'archived', updated_at = NOW()
                WHERE id = %s RETURNING title
            """, (project_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Project not found")
            conn.commit()

    return {"status": "archived", "title": row[0]}


# ══════════════════════════════════════════════════════════════════════════════
#   ENDPOINTS — STATS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/workshop/stats")
async def workshop_stats(x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM workshop_projects WHERE status = 'active'")
            active = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM workshop_projects WHERE current_phase = 'complete'")
            completed = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM workshop_tasks WHERE is_complete = TRUE")
            tasks_done = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM workshop_tasks")
            tasks_total = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM workshop_parts")
            parts_total = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM workshop_parts WHERE status = 'installed'")
            parts_installed = cur.fetchone()[0]

            cur.execute("""
                SELECT current_phase, COUNT(*) FROM workshop_projects
                WHERE status = 'active' GROUP BY current_phase
            """)
            by_phase = {r[0]: r[1] for r in cur.fetchall()}

            cur.execute("SELECT COALESCE(SUM(est_cost), 0) FROM workshop_projects WHERE status = 'active'")
            total_est_cost = round(cur.fetchone()[0], 2)

            cur.execute("SELECT COALESCE(AVG(difficulty), 0) FROM workshop_projects WHERE status = 'active'")
            avg_difficulty = round(cur.fetchone()[0], 1)

    return {
        "active_projects":  active,
        "completed":        completed,
        "tasks_done":       tasks_done,
        "tasks_total":      tasks_total,
        "parts_total":      parts_total,
        "parts_installed":  parts_installed,
        "by_phase":         by_phase,
        "total_est_cost":   total_est_cost,
        "avg_difficulty":   avg_difficulty
    }


# ══════════════════════════════════════════════════════════════════════════════
#   X-RAY SCANNER — AI Vision Equipment Analysis
# ══════════════════════════════════════════════════════════════════════════════

async def ai_vision_scan(image_bytes: bytes, mime_type: str, context: str = "") -> dict:
    """Use Gemini Vision to identify equipment from a photo and perform
    a complete engineering teardown — specs, schematics, parts, hazards."""
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")

        context_line = f"\nADDITIONAL CONTEXT FROM USER: {context}" if context else ""

        prompt = f"""You are an elite industrial equipment forensic analyst, master mechanic,
and salvage engineer. You have 30 years of experience tearing down every kind of
industrial, medical, military, automotive, and commercial equipment.

A photo of equipment has been uploaded. Analyze it with extreme detail.
{context_line}

YOUR MISSION — Perform a COMPLETE X-RAY SCAN:

1. IDENTIFY the equipment: manufacturer, model, year/era, original purpose
2. FIND THE SCHEMATICS: Describe the internal schematic layout — what's inside,
   how the systems connect, power flow, fluid paths, signal chains
3. COMPONENT TEARDOWN: List EVERY salvageable component visible or reasonably
   expected to be inside this equipment
4. SPECIFICATIONS: Voltages, pressures, flow rates, dimensions, weight, power ratings
5. HAZARD ASSESSMENT: Any dangerous materials (asbestos, lead, mercury, refrigerants,
   capacitors, radiation sources, pressurized vessels, biohazards)
6. SALVAGE VALUE: Estimate the value of key components on the used market

Return ONLY a valid JSON object with this EXACT structure (no markdown, no backticks):

{{
    "identification": {{
        "equipment_name": "Full name of the equipment",
        "manufacturer": "Manufacturer/brand name",
        "model": "Model number or series",
        "year_range": "Approximate year or range (e.g. 2005-2012)",
        "category": "one of: medical, industrial, automotive, military, commercial, electrical, hvac, marine, agricultural, computing, telecom, laboratory, other",
        "original_purpose": "What this equipment was designed to do",
        "common_names": ["Other names this equipment goes by"]
    }},
    "schematics": {{
        "system_overview": "High-level description of how this machine works internally",
        "power_system": "How power enters and distributes through the machine",
        "control_system": "How the machine is controlled — PCBs, microcontrollers, relays, pneumatics",
        "fluid_systems": "Any hydraulic, pneumatic, coolant, gas, or liquid systems",
        "mechanical_systems": "Drive trains, gears, bearings, actuators, linkages",
        "electrical_diagram": "ASCII representation of the main electrical flow path",
        "signal_chain": "How sensors, controllers, and actuators communicate"
    }},
    "specifications": {{
        "power_input": "e.g. 120V AC 60Hz 15A",
        "power_consumption": "e.g. 1800W",
        "dimensions": "L x W x H approximate",
        "weight": "Approximate weight",
        "operating_pressure": "If applicable",
        "flow_rates": "If applicable",
        "other_specs": ["Any other notable specifications"]
    }},
    "components": [
        {{
            "name": "Component name",
            "category": "structural/electrical/mechanical/hydraulic/pneumatic/sensor/motor/pump/valve/wiring/electronic/raw_material/optical/thermal/other",
            "quantity": 1,
            "location": "Where in the machine this component is found",
            "condition_notes": "Expected condition based on equipment type and age",
            "salvage_value": 0.00,
            "reuse_potential": "high/medium/low",
            "specifications": "Key specs of this specific component"
        }}
    ],
    "hazards": {{
        "level": "none/low/medium/high/critical",
        "warnings": ["Specific hazard warning 1", "Specific hazard warning 2"],
        "required_ppe": ["PPE item 1", "PPE item 2"],
        "disposal_notes": "Special disposal requirements for hazardous components",
        "lockout_tagout": "Lockout/tagout requirements before teardown"
    }},
    "salvage_assessment": {{
        "total_estimated_value": 0.00,
        "high_value_components": ["Component 1 ($XX)", "Component 2 ($XX)"],
        "scrap_metal_value": 0.00,
        "teardown_difficulty": 7,
        "teardown_hours": 8.0,
        "required_tools": ["Tool 1", "Tool 2", "Tool 3"],
        "recommended_approach": "Step-by-step teardown strategy"
    }},
    "build_potential": [
        "What this equipment could be repurposed into — idea 1",
        "What this equipment could be repurposed into — idea 2",
        "What this equipment could be repurposed into — idea 3"
    ]
}}

Be thorough and precise. If you can't identify the exact model, give your best assessment
based on visual cues. Extract EVERY component you can identify or reasonably infer.
Return ONLY valid JSON."""

        # Build the multimodal request
        image_part = {
            "inline_data": {
                "mime_type": mime_type,
                "data": base64.b64encode(image_bytes).decode("utf-8")
            }
        }

        response = await model.generate_content_async([prompt, image_part])
        text = response.text.strip()

        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

        result = json.loads(text)
        log.info(f"Vision scan complete: {result.get('identification', {}).get('equipment_name', 'Unknown')}")
        return result

    except json.JSONDecodeError as e:
        log.error(f"Vision AI returned invalid JSON: {e}")
        return {
            "identification": {"equipment_name": "Analysis Error", "manufacturer": "Unknown",
                               "model": "Unknown", "year_range": "", "category": "other",
                               "original_purpose": "Could not parse AI response", "common_names": []},
            "schematics": {}, "specifications": {}, "components": [],
            "hazards": {"level": "unknown", "warnings": ["Scan failed — inspect manually"], "required_ppe": [], "disposal_notes": "", "lockout_tagout": ""},
            "salvage_assessment": {"total_estimated_value": 0, "high_value_components": [],
                                   "scrap_metal_value": 0, "teardown_difficulty": 5,
                                   "teardown_hours": 0, "required_tools": [], "recommended_approach": ""},
            "build_potential": [],
            "error": f"JSON parse error: {str(e)}"
        }
    except Exception as e:
        log.error(f"Vision scan failed: {e}")
        return {
            "identification": {"equipment_name": "Scan Failed", "manufacturer": "Unknown",
                               "model": "Unknown", "year_range": "", "category": "other",
                               "original_purpose": str(e), "common_names": []},
            "schematics": {}, "specifications": {}, "components": [],
            "hazards": {"level": "unknown", "warnings": [], "required_ppe": [], "disposal_notes": "", "lockout_tagout": ""},
            "salvage_assessment": {"total_estimated_value": 0, "high_value_components": [],
                                   "scrap_metal_value": 0, "teardown_difficulty": 5,
                                   "teardown_hours": 0, "required_tools": [], "recommended_approach": ""},
            "build_potential": [],
            "error": str(e)
        }


def save_scan(user_email: str, image_hash: str, result: dict) -> int:
    """Save a scan result to the database."""
    ident = result.get("identification", {})
    hazards = result.get("hazards", {})
    salvage = result.get("salvage_assessment", {})

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO equipment_scans
                        (user_email, image_hash, equipment_name, manufacturer, model,
                         year_range, category, scan_result, parts_found,
                         est_salvage, hazard_level)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    user_email,
                    image_hash,
                    ident.get("equipment_name", "Unknown"),
                    ident.get("manufacturer", "Unknown"),
                    ident.get("model", "Unknown"),
                    ident.get("year_range", ""),
                    ident.get("category", "other"),
                    json.dumps(result),
                    len(result.get("components", [])),
                    salvage.get("total_estimated_value", 0),
                    hazards.get("level", "unknown")
                ))
                scan_id = cur.fetchone()[0]
                conn.commit()
                return scan_id
    except Exception as e:
        log.error(f"Failed to save scan: {e}")
        return None


# ── SCANNER ENDPOINTS ─────────────────────────────────────────────────────────

@app.post("/scan/upload")
async def scan_uploaded_image(
    file: UploadFile = File(...),
    user_email: str = Form("anonymous"),
    context: str = Form(""),
    x_internal_key: str = Header(None)
):
    """Upload an image file for X-Ray scanning.
    Accepts JPEG, PNG, WebP. Max ~20MB (Gemini limit)."""
    await verify(x_internal_key)

    allowed = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
    content_type = file.content_type or "image/jpeg"
    if content_type not in allowed:
        raise HTTPException(status_code=400,
            detail=f"Unsupported image type: {content_type}. Use JPEG, PNG, or WebP.")

    image_bytes = await file.read()
    if len(image_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large. Max 20MB.")
    if len(image_bytes) < 1000:
        raise HTTPException(status_code=400, detail="Image too small or corrupt.")

    log.info(f"Scanning image: {file.filename} ({len(image_bytes)} bytes) for {user_email}")

    # Hash for dedup
    import hashlib
    image_hash = hashlib.md5(image_bytes).hexdigest()

    # Run AI vision analysis
    result = await ai_vision_scan(image_bytes, content_type, context)

    # Save to database
    scan_id = await asyncio.to_thread(save_scan, user_email, image_hash, result)

    ident = result.get("identification", {})
    components = result.get("components", [])
    salvage = result.get("salvage_assessment", {})

    return {
        "scan_id":        scan_id,
        "equipment_name": ident.get("equipment_name", "Unknown"),
        "manufacturer":   ident.get("manufacturer", "Unknown"),
        "model":          ident.get("model", "Unknown"),
        "year_range":     ident.get("year_range", ""),
        "category":       ident.get("category", "other"),
        "parts_found":    len(components),
        "est_salvage":    salvage.get("total_estimated_value", 0),
        "hazard_level":   result.get("hazards", {}).get("level", "unknown"),
        "scan_result":    result
    }


@app.post("/scan/base64")
async def scan_base64_image(req: ScanImageRequest, x_internal_key: str = Header(None)):
    """Scan an image provided as base64 string (for Streamlit integration)."""
    await verify(x_internal_key)

    # Strip data URI prefix if present
    b64 = req.image_base64
    mime_type = "image/jpeg"

    if b64.startswith("data:"):
        match = re.match(r"data:(image/\w+);base64,(.+)", b64, re.DOTALL)
        if match:
            mime_type = match.group(1)
            b64 = match.group(2)

    try:
        image_bytes = base64.b64decode(b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    if len(image_bytes) < 1000:
        raise HTTPException(status_code=400, detail="Image too small or corrupt.")

    log.info(f"Scanning base64 image ({len(image_bytes)} bytes) for {req.user_email}")

    import hashlib
    image_hash = hashlib.md5(image_bytes).hexdigest()

    result = await ai_vision_scan(image_bytes, mime_type, req.context)
    scan_id = await asyncio.to_thread(save_scan, req.user_email, image_hash, result)

    ident = result.get("identification", {})
    return {
        "scan_id":        scan_id,
        "equipment_name": ident.get("equipment_name", "Unknown"),
        "manufacturer":   ident.get("manufacturer", "Unknown"),
        "model":          ident.get("model", "Unknown"),
        "parts_found":    len(result.get("components", [])),
        "est_salvage":    result.get("salvage_assessment", {}).get("total_estimated_value", 0),
        "hazard_level":   result.get("hazards", {}).get("level", "unknown"),
        "scan_result":    result
    }


@app.get("/scans")
async def list_scans(x_internal_key: str = Header(None),
                     user_email: str = None, limit: int = 50):
    """List all equipment scans."""
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT id, user_email, equipment_name, manufacturer, model,
                       year_range, category, parts_found, est_salvage,
                       hazard_level, status, created_at
                FROM equipment_scans
            """
            params = []
            if user_email:
                query += " WHERE user_email = %s"
                params.append(user_email)
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()

    return [
        {
            "id": r[0], "user_email": r[1], "equipment_name": r[2],
            "manufacturer": r[3], "model": r[4], "year_range": r[5],
            "category": r[6], "parts_found": r[7], "est_salvage": r[8],
            "hazard_level": r[9], "status": r[10], "created_at": str(r[11])
        }
        for r in rows
    ]


@app.get("/scans/{scan_id}")
async def get_scan(scan_id: int, x_internal_key: str = Header(None)):
    """Get full scan detail including the complete AI analysis."""
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_email, equipment_name, manufacturer, model,
                       year_range, category, scan_result, parts_found,
                       est_salvage, hazard_level, status, created_at
                FROM equipment_scans WHERE id = %s
            """, (scan_id,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    return {
        "id": row[0], "user_email": row[1], "equipment_name": row[2],
        "manufacturer": row[3], "model": row[4], "year_range": row[5],
        "category": row[6], "scan_result": row[7], "parts_found": row[8],
        "est_salvage": row[9], "hazard_level": row[10], "status": row[11],
        "created_at": str(row[12])
    }


@app.post("/scans/{scan_id}/to-workbench")
async def scan_to_workbench(scan_id: int, x_internal_key: str = Header(None)):
    """Convert a scan into a workbench-ready junk description string
    that can be pasted directly into the New Build form."""
    await verify(x_internal_key)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT equipment_name, manufacturer, model, year_range, scan_result
                FROM equipment_scans WHERE id = %s
            """, (scan_id,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    name, mfr, model, year, result = row
    components = result.get("components", []) if isinstance(result, dict) else []
    specs = result.get("specifications", {}) if isinstance(result, dict) else {}

    # Build a rich workbench description from the scan
    lines = [f"{mfr} {model} {name}"]
    if year:
        lines[0] += f" ({year})"

    # Add key specs
    for key in ["power_input", "weight", "dimensions"]:
        val = specs.get(key)
        if val:
            lines.append(f"  Spec: {key.replace('_', ' ').title()}: {val}")

    # Add all identified components
    if components:
        lines.append(f"  Components ({len(components)} identified):")
        for comp in components:
            if isinstance(comp, dict):
                cname = comp.get("name", "Unknown")
                cat   = comp.get("category", "")
                qty   = comp.get("quantity", 1)
                spec  = comp.get("specifications", "")
                entry = f"    - {cname}"
                if qty > 1:
                    entry += f" (x{qty})"
                if cat:
                    entry += f" [{cat}]"
                if spec:
                    entry += f" — {spec}"
                lines.append(entry)

    workbench_text = "\n".join(lines)

    return {
        "scan_id":       scan_id,
        "workbench_text": workbench_text,
        "equipment_name": name,
        "parts_count":    len(components)
    }
