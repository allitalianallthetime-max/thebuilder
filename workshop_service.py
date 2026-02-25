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
import asyncio
import logging
import psycopg2
import psycopg2.pool
import google.generativeai as genai
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from contextlib import contextmanager
from datetime import datetime
from dotenv import load_dotenv

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
            conn.commit()
    log.info("Workshop tables initialized.")

try:
    init_pool()
    init_db()
except Exception as e:
    log.warning(f"DB Init: {e}")

# ── Security ──────────────────────────────────────────────────────────────────
async def verify(x_internal_key: str = Header(None)):
    if x_internal_key != INTERNAL_API_KEY:
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
