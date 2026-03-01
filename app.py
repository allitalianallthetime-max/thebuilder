"""
app.py — The Builder UI (Enterprise Edition)
=============================================
AoC3P0 Systems · AI-Powered Engineering Forge
Async Polling, Analytics Tracking, and Pro Monetization.
"""

import streamlit as st
import streamlit.components.v1 as components
import os
import html as html_lib
import secrets
import logging
import httpx
import time
import threading
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("builder-ui")

st.set_page_config(page_title="THE BUILDER | AoC3P0", page_icon="⚙️", layout="wide", initial_sidebar_state="expanded")

# ── Configuration & Environment ───────────────────────────────────────────────
def normalize_url(raw: str, default: str) -> str:
    if not raw: return default
    raw = raw.strip()
    return raw if raw.startswith("http") else f"http://{raw}:10000"

AUTH_SERVICE_URL   = normalize_url(os.getenv("AUTH_SERVICE_URL", ""), "http://builder-auth:10000")
AI_SERVICE_URL     = normalize_url(os.getenv("AI_SERVICE_URL", ""), "http://builder-ai:10000")
BILLING_URL        = normalize_url(os.getenv("BILLING_SERVICE_URL", ""), "http://builder-billing:10000")
ANALYTICS_URL      = normalize_url(os.getenv("ANALYTICS_SERVICE_URL", ""), "http://builder-analytics:10000")
ADMIN_URL          = normalize_url(os.getenv("ADMIN_SERVICE_URL", ""), "http://builder-admin:10000")
EXPORT_URL         = normalize_url(os.getenv("EXPORT_SERVICE_URL", ""), "http://builder-export:10000")
WORKSHOP_URL       = normalize_url(os.getenv("WORKSHOP_SERVICE_URL", ""), "http://builder-workshop:10000")

INTERNAL_API_KEY   = os.getenv("INTERNAL_API_KEY")
MASTER_KEY         = os.getenv("MASTER_KEY")
STRIPE_PAYMENT_URL = os.getenv("STRIPE_PAYMENT_URL", "#")

# ── Safe HTML & Core Helpers ──────────────────────────────────────────────────
_IFRAME_CSS = '<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">'
def safe_html(content: str, height: int = 0):
    if height > 0:
        wrapped = f"<html><head>{_IFRAME_CSS}<style>body{{margin:0;padding:0;background:transparent;overflow:hidden;font-family:'Rajdhani',sans-serif;color:#e8d5b0;}}</style></head><body>{content}</body></html>"
        components.html(wrapped, height=height, scrolling=False)
        return
    if hasattr(st, 'html'):
        try: st.html(content); return
        except: pass
    st.markdown(content, unsafe_allow_html=True)

def esc(text): return html_lib.escape(str(text)) if text else ""
def api_headers():
    headers = {"x-internal-key": INTERNAL_API_KEY}
    if st.session_state.get("user_token"): headers["Authorization"] = f"Bearer {st.session_state['user_token']}"
    return headers

@st.cache_data(ttl=60)
def get_healthz(): return True

# ── Background Analytics Tracking ─────────────────────────────────────────────
def track_event(event_type: str, metadata: dict = None):
    """Silently fires analytics in the background so the UI never slows down."""
    email = st.session_state.get("user_email", "guest")
    def _send():
        try:
            httpx.post(f"{ANALYTICS_URL}/track/event", json={"event_type": event_type, "user_email": email, "metadata": metadata or {}}, headers={"x-internal-key": INTERNAL_API_KEY}, timeout=3.0)
        except: pass 
    threading.Thread(target=_send).start()

# ── Global Cyberpunk / Industrial CSS ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Share+Tech+Mono&family=Rajdhani:wght@500;700&display=swap');
:root { --orange: #ff6600; --dark: #060606; --plate: #0d0d0d; --border: #2a1500; --text: #e8d5b0; --green: #00cc66; --red: #ff4444; }
html, body, .stApp { background-color: var(--dark) !important; color: var(--text) !important; font-family: 'Rajdhani', sans-serif !important; }
#MainMenu, footer, header, .stDeployButton { display: none !important; }
::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: var(--orange); }

.stButton > button { 
    background: linear-gradient(135deg,#cc4400,var(--orange)) !important; 
    color: #000 !important; border: none !important; border-radius: 0 !important; 
    font-family: 'Bebas Neue', sans-serif !important; font-size: 22px !important; letter-spacing: 3px !important; 
    padding: 12px 30px !important; clip-path: polygon(10px 0%,100% 0%,calc(100% - 10px) 100%,0% 100%) !important; 
    transition: all .2s !important; box-shadow: 0 0 15px rgba(255,100,0,.2) !important; width: 100%;
}
.stButton > button:hover { transform: translateY(-2px) !important; box-shadow: 0 0 30px rgba(255,100,0,.6) !important; }
.stTextArea textarea, .stTextInput input, .stSelectbox > div > div { background: #0a0a0a !important; border: 1px solid var(--border) !important; border-radius: 0 !important; color: var(--text) !important; font-family: 'Share Tech Mono', monospace !important; padding: 12px !important;}
.stTextArea textarea:focus, .stTextInput input:focus { border-color: var(--orange) !important; box-shadow: 0 0 10px rgba(255,100,0,.2) !important; }

/* TABS */
.stTabs [data-baseweb="tab-list"] { background: transparent !important; gap: 10px !important; }
.stTabs [data-baseweb="tab"] { font-family: 'Bebas Neue', sans-serif !important; font-size: 24px !important; color: #555 !important; background: transparent; padding: 10px 20px !important; border: none !important; }
.stTabs [aria-selected="true"] { color: var(--orange) !important; border-bottom: 2px solid var(--orange) !important; background: rgba(255,100,0,.05) !important; }

/* Custom Sections */
.sec-head { display:flex; align-items:center; gap:14px; margin-bottom:20px; margin-top:20px;}
.sec-num { font-family:'Bebas Neue',sans-serif; font-size:40px; color:#222; }
.sec-title{ font-family:'Bebas Neue',sans-serif; font-size:26px; color:var(--text); letter-spacing:3px; }
.sec-line { flex:1; height:1px; background:linear-gradient(90deg,var(--border),transparent); }

/* Polling Terminal / Metric Cards */
.terminal-box { background: #050505; border: 1px solid #333; border-left: 4px solid var(--orange); padding: 15px; font-family: 'Share Tech Mono', monospace; color: var(--green); font-size: 14px; box-shadow: inset 0 0 20px rgba(0,0,0,0.8); margin-bottom: 15px;}
.metric-card { background: linear-gradient(135deg,#0f0f0f,#111); border: 1px solid #222; border-top: 3px solid var(--orange); padding: 20px 24px; text-align: center; box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
.metric-val { font-family:'Bebas Neue',sans-serif; font-size:42px; color:var(--orange); line-height:1; }
.metric-label { font-family:'Share Tech Mono',monospace; font-size:10px; color:#666; letter-spacing:2px; margin-top: 6px; }
.admin-row { background:#0d0d0d; border:1px solid #1a1a1a; border-left:2px solid #2a2a2a; padding:12px 18px; margin-bottom:3px; font-family:'Share Tech Mono',monospace; font-size:11px; color:#aaa; }
.stProgress > div > div > div > div { background-color: var(--orange) !important; }
</style>
""", unsafe_allow_html=True)

# ── Session State ─────────────────────────────────────────────────────────────
_DEFAULTS = {"authenticated": False, "user_tier": "guest", "user_name": "", "user_email": "", "user_token": "", "is_admin": False, "last_blueprint": None, "last_build_id": None, "last_project_type": None, "last_junk_input": None, "last_usage": None, "prefill_workbench": ""}
for _key, _val in _DEFAULTS.items():
    if _key not in st.session_state: st.session_state[_key] = _val

def sec_head(num, title): safe_html(f"<div class='sec-head'><div class='sec-num'>{esc(num)}</div><div class='sec-title'>{esc(title)}</div><div class='sec-line'></div></div>")

# ── Upgrade Wall Component ────────────────────────────────────────────────────
def upgrade_wall(feature_name: str):
    """Blocks Free/Starter users and aggressively pushes Stripe Conversions."""
    if st.session_state.user_tier in ["guest", "starter", "none"]:
        safe_html(f"""
        <div style="background:linear-gradient(90deg, #1a0a00, #0a0500); border:1px solid #ff4444; border-left:4px solid #ff4444; padding:20px; margin:20px 0;">
            <h3 style="color:#ff4444; margin-top:0; font-family:'Bebas Neue'; letter-spacing:2px; font-size: 28px;">🔒 {feature_name} RESTRICTED</h3>
            <p style="color:#e8d5b0; font-family:'Share Tech Mono'; font-size:12px;">Your current tier does not have access to this feature. Upgrade to Pro to unlock unlimited power.</p>
            <a href="{STRIPE_PAYMENT_URL}" target="_blank" style="display:inline-block; background:#ff4444; color:#fff; padding:10px 20px; font-family:'Bebas Neue'; font-size:20px; text-decoration:none; letter-spacing:2px; margin-top: 10px;">⚡ UPGRADE TO PRO NOW</a>
        </div>
        """)
        track_event("upgrade_wall_hit", {"feature": feature_name})
        return True
    return False

# ── The Task Poller (The Magic Async UI Engine) ───────────────────────────────
def poll_task(poll_url: str, success_msg: str):
    """Creates a beautiful terminal-like UI that updates in real-time while Celery works."""
    status_box = st.empty()
    progress_bar = st.progress(0)
    
    with st.spinner("Establishing secure uplink..."):
        while True:
            time.sleep(2.0)
            try:
                r = httpx.get(poll_url, headers=api_headers(), timeout=5.0)
                data = r.json()
                state = data.get("status")

                if state in ["processing", "pending"]:
                    msg = data.get("message", "Compiling parameters...")
                    status_box.markdown(f"<div class='terminal-box'>⏳ [IN PROGRESS] {msg}</div>", unsafe_allow_html=True)
                    curr_val = getattr(st.session_state, '_sim_prog', 10)
                    new_val = min(90, curr_val + 10)
                    st.session_state._sim_prog = new_val
                    progress_bar.progress(new_val)
                
                elif state == "complete":
                    progress_bar.progress(100)
                    status_box.markdown(f"<div class='terminal-box' style='border-left-color:#00cc66; color:#00cc66;'>✅ [SUCCESS] {success_msg}</div>", unsafe_allow_html=True)
                    st.session_state._sim_prog = 10
                    time.sleep(1.5)
                    status_box.empty()
                    progress_bar.empty()
                    return data.get("result", True)
                
                elif state == "failed":
                    status_box.error(f"⛔ Task Failed: {data.get('error', 'Unknown anomaly')}")
                    return None
            except Exception as e:
                status_box.warning(f"📡 Waiting for telemetry... {e}")
                time.sleep(2)

# ══════════════════════════════════════════════════════════════════════════════
#   LOGIN / ONBOARDING
# ══════════════════════════════════════════════════════════════════════════════
def login():
    _hero = """
    <div style="min-height:40vh; background: linear-gradient(160deg,#100900 0%,#060606 45%,#080a04 100%); display:flex; flex-direction:column; align-items:center; justify-content:center; position:relative; overflow:hidden;">
        <div style="position:absolute; right:-160px; top:-160px; font-size:540px; opacity:.02; line-height:1; animation:spin 80s linear infinite;">⚙</div>
        <div style="font-family:'Share Tech Mono',monospace; font-size:10px; letter-spacing:8px; color:#663300; margin-bottom:10px;">── AI-POWERED · ROUND TABLE ENGINEERING ──</div>
        <div style="font-family:'Bebas Neue',sans-serif; font-size:clamp(70px, 10vw, 130px); line-height:0.85; letter-spacing:10px; color:#ff6600; text-shadow:0 0 40px rgba(255,100,0,.5);">THE BUILDER</div>
        <div style="margin-top:20px; font-family:'Rajdhani',sans-serif; font-size:24px; color:#c89050; letter-spacing:2px; font-style:italic;">"Where AI logic meets heavy metal."</div>
    </div>
    """
    safe_html(_hero, height=350)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        safe_html("<div style='background:#0d0d0d; border:1px solid #2a1500; border-top:3px solid #ff6600; padding:30px; box-shadow: 0 15px 40px rgba(0,0,0,0.8); margin-top: -30px; position:relative; z-index:10;'>")
        
        key_input = st.text_input("LICENSE KEY", type="password", placeholder="Enter your secure access badge...")
        if st.button("⚡ IGNITE THE FORGE"):
            if MASTER_KEY and secrets.compare_digest(key_input, MASTER_KEY):
                st.session_state.update({"authenticated": True, "is_admin": True, "user_name": "Anthony", "user_tier": "master", "user_email": "admin"})
                track_event("login", {"tier": "master"})
                st.rerun()
            else:
                with st.spinner("Authenticating..."):
                    try:
                        resp = httpx.post(f"{AUTH_SERVICE_URL}/verify-license", json={"license_key": key_input}, headers=api_headers(), timeout=10.0)
                        if resp.status_code == 200:
                            data = resp.json()
                            st.session_state.update({"authenticated": True, "is_admin": False, "user_tier": data.get("tier", "pro"), "user_name": data.get("name", "Builder"), "user_email": data.get("email", ""), "user_token": data.get("token", "")})
                            track_event("login", {"tier": data.get("tier")})
                            st.rerun()
                        else:
                            st.error("⛔ ACCESS DENIED — INVALID KEY")
                    except Exception as e:
                        st.error("Authentication Service Offline.")
        
        safe_html("</div>")
        
        if STRIPE_PAYMENT_URL and STRIPE_PAYMENT_URL != "#":
            st.markdown(f'<div style="text-align:center; margin-top:30px;"><a href="{STRIPE_PAYMENT_URL}" target="_blank" style="color:#ffaa00; font-family:\'Share Tech Mono\'; font-size:14px; text-decoration:none; border-bottom:1px dashed #ffaa00; padding-bottom:2px;">NO LICENSE? SECURE ACCESS HERE ➜</a></div>', unsafe_allow_html=True)

# ── SIDEBAR & HEADER ──────────────────────────────────────────────────────────
def render_header():
    safe_html(f"""
    <div style="background:#0a0a0a; border-bottom:1px solid #1a1a1a; padding:15px 40px; display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px;">
        <div>
            <span style="font-family:'Bebas Neue',sans-serif; font-size:36px; color:#ff6600; letter-spacing:5px;">THE FORGE</span><br>
            <span style="font-family:'Share Tech Mono',monospace; font-size:10px; color:#666; letter-spacing:2px;">AoC3P0 SYSTEMS · SECURE CONNECTION ESTABLISHED</span>
        </div>
        <div style="text-align:right;">
            <span style="font-family:'Share Tech Mono',monospace; font-size:12px; color:#00cc66; border:1px solid #00cc66; padding:5px 12px; background:rgba(0,200,100,.05);">
                {st.session_state.user_tier.upper()} LICENSE
            </span>
            <br><span style="font-family:'Share Tech Mono',monospace; font-size:10px; color:#888; letter-spacing:1px; margin-top:6px; display:inline-block;">OP: {st.session_state.user_name.upper()}</span>
        </div>
    </div>
    """)

# ── TAB 1: NEW BUILD (Async Polling UI) ───────────────────────────────────────
def tab_new_build():
    sec_head("01", "LOAD THE WORKBENCH")
    prefill = st.session_state.pop("prefill_workbench", "")
    if prefill: st.success("✅ Workbench populated from X-Ray Scan!")
    
    junk_input = st.text_area("PARTS INVENTORY", value=prefill, placeholder="Example: 5HP electric motor, titanium plating, arduino uno...", height=150)
    col1, col2 = st.columns(2)
    with col1: project_type = st.selectbox("BUILD DESIGNATION", ["Combat Robot", "Shop Tool", "Hydraulic Lift", "Custom Vehicle Mod", "Defense Rig"])
    with col2: 
        opts = ["Quick Concept (Novice Only)", "Full Blueprint (All 3 Tiers)"]
        if st.session_state.user_tier in ["master", "pro"]: opts.append("Master Build (Expert Only)")
        detail = st.selectbox("ENGINEERING DEPTH", opts)

    st.markdown("<br/>", unsafe_allow_html=True)
    if st.button("🔥 CONSULT THE ROUND TABLE (GENERATE)"):
        if not junk_input.strip():
            st.warning("⚠ Parts list required.")
            return

        track_event("forge_started", {"project_type": project_type})
        
        try:
            # 1. Fire to Gateway (Instantly deducts credit, returns task_id)
            resp = httpx.post(f"{AI_SERVICE_URL}/generate", json={"junk_desc": junk_input, "project_type": project_type, "detail_level": detail, "user_email": st.session_state.user_email}, headers=api_headers(), timeout=10.0)
            
            if resp.status_code == 200:
                task_id = resp.json()["task_id"]
                
                # 2. Async Polling
                result = poll_task(f"{AI_SERVICE_URL}/generate/status/{task_id}", "Blueprint Forged!")
                if result:
                    st.session_state.last_blueprint = result["content"]
                    st.session_state.last_build_id = result["build_id"]
                    st.session_state.last_project_type = project_type
                    st.session_state.last_junk_input = junk_input
                    track_event("forge_success", {"build_id": result["build_id"]})
                    st.rerun()

            elif resp.status_code == 402:
                st.error("⛔ OUT OF CREDITS.")
                st.markdown(f'<a href="{STRIPE_PAYMENT_URL}" target="_blank" style="display:block; background:#ff4444; color:#fff; text-align:center; padding:10px; font-family:\'Bebas Neue\'; font-size:24px; text-decoration:none;">UPGRADE TIER TO UNLOCK MORE BUILDS</a>', unsafe_allow_html=True)
            else:
                st.error(f"Gateway Error: {resp.text}")
        except Exception as e:
            st.error(f"Service offline: {e}")

    # Display Blueprint & Upsells
    if st.session_state.last_blueprint:
        st.markdown("---")
        st.markdown(st.session_state.last_blueprint)
        st.markdown("---")
        
        sec_head("02", "EXECUTE BUILD")
        
        if st.session_state.user_tier in ["guest", "starter"]:
            safe_html("<div style='background:rgba(255,100,0,.1); border:1px solid #ff6600; padding:10px; font-family:Share Tech Mono; font-size:12px; color:#ffaa00; margin-bottom: 10px;'>⚠️ STARTER TIER NOTICE: PDF Exports will be watermarked. Upgrade to Pro for clean prints.</div>")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📄 EXPORT PDF"):
                track_event("export_pdf", {"build_id": st.session_state.last_build_id})
                try:
                    # PASS TIER FOR WATERMARKING
                    r = httpx.post(f"{EXPORT_SERVICE_URL}/export/pdf", json={
                        "blueprint": st.session_state.last_blueprint, 
                        "project_type": st.session_state.last_project_type, 
                        "junk_desc": st.session_state.last_junk_input, 
                        "build_id": st.session_state.last_build_id,
                        "tier": st.session_state.user_tier
                    }, headers=api_headers(), timeout=30.0)
                    if r.status_code == 200:
                        st.download_button("⬇ DOWNLOAD SECURE PDF", data=r.content, file_name=f"blueprint_{st.session_state.last_build_id}.pdf", mime="application/pdf")
                except: st.error("Print shop offline.")
        
        with col2:
            if st.button("🔩 SEND TO WORKSHOP"):
                if not upgrade_wall("Workshop Progress Tracking"):
                    track_event("send_to_workshop")
                    try:
                        r = httpx.post(f"{WORKSHOP_SERVICE_URL}/projects/create", json={"build_id": st.session_state.last_build_id, "user_email": st.session_state.user_email, "title": f"Build #{st.session_state.last_build_id}", "project_type": st.session_state.last_project_type, "junk_desc": st.session_state.last_junk_input}, headers=api_headers(), timeout=10.0)
                        if r.status_code == 200:
                            res = poll_task(f"{WORKSHOP_SERVICE_URL}/task/status/{r.json()['task_id']}", "Project Initialized!")
                            if res: st.success(f"Project #{res['project_id']} active in Workshop tab!")
                    except: st.error("Workshop offline.")

# ── TAB 2: X-RAY SCANNER (Vision Async) ───────────────────────────────────────
def tab_scanner():
    sec_head("01", "X-RAY VISION SCANNER")
    if upgrade_wall("AI Vision Teardown"): return

    st.markdown("<p style='font-family: Share Tech Mono; color: #888;'>Upload an image. Gemini 2.5 Vision will reverse-engineer the components.</p>", unsafe_allow_html=True)
    c1, c2 = st.columns([1.5, 1])
    with c1: uploaded_file = st.file_uploader("DROP EQUIPMENT PHOTO", type=["jpg", "png", "webp"])
    with c2: context = st.text_area("CONTEXT", placeholder="e.g. Found in hospital basement")
    
    if st.button("👁️ INITIATE SCAN"):
        if not uploaded_file: st.warning("Upload a photo.")
        else:
            track_event("vision_scan_started")
            try:
                img_b64 = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
                mime = uploaded_file.type or "image/jpeg"
                
                # Send to Gateway
                r = httpx.post(f"{WORKSHOP_SERVICE_URL}/scan/base64", json={"image_base64": f"data:{mime};base64,{img_b64}", "user_email": st.session_state.user_email, "context": context}, headers=api_headers(), timeout=10.0)
                
                if r.status_code == 200:
                    res = poll_task(f"{WORKSHOP_SERVICE_URL}/task/status/{r.json()['task_id']}", "Analysis Complete.")
                    if res:
                        st.session_state.last_scan = res
                        track_event("vision_scan_success")
                        st.rerun()
                elif r.status_code == 413: st.error("File too large (Max 20MB)")
                elif r.status_code == 429: st.error("Scan limit reached. Upgrade for more bandwidth.")
                else: st.error(f"API Error: {r.text}")
            except Exception as e: st.error(f"Scanner Offline: {e}")

    # Render Result
    scan = st.session_state.get("last_scan")
    if scan and scan.get("scan_result"):
        res = scan["scan_result"]
        ident = res.get("identification", {})
        salvage = res.get("salvage_assessment", {})
        
        st.markdown("---")
        st.markdown(f"<h2 style='color:#00cc66;font-family:Bebas Neue;letter-spacing:2px;'>🎯 IDENTIFIED: {ident.get('equipment_name', 'UNKNOWN')}</h2>", unsafe_allow_html=True)
        
        colA, colB, colC = st.columns(3)
        with colA: safe_html(f"<div class='metric-card'><div class='metric-val'>{len(res.get('components', []))}</div><div class='metric-label'>PARTS EXTRACTED</div></div>")
        with colB: safe_html(f"<div class='metric-card'><div class='metric-val'>${salvage.get('total_estimated_value',0):,.0f}</div><div class='metric-label'>EST. SALVAGE</div></div>")
        with colC: safe_html(f"<div class='metric-card'><div class='metric-val' style='color:#ff4444;'>{res.get('hazards', {}).get('level', 'UNKNOWN').upper()}</div><div class='metric-label'>HAZARD LEVEL</div></div>")
        
        with st.expander("VIEW RAW ENGINEERING DATA"):
            st.json(res)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📋 SEND TO WORKBENCH (NEW BUILD)"):
            try:
                r = httpx.post(f"{WORKSHOP_SERVICE_URL}/scans/{scan['scan_id']}/to-workbench", headers=api_headers(), timeout=10.0)
                if r.status_code == 200:
                    st.session_state["prefill_workbench"] = r.json()["workbench_text"]
                    st.success("✅ Sent! Switch to NEW BUILD tab.")
            except: st.error("Failed to transfer.")

# ── TAB 3: ADMIN (Thread-Safe Dashboard) ──────────────────────────────────────
def tab_admin():
    sec_head("👑", "CONTROL ROOM (ADMIN)")
    if not st.session_state.is_admin: return
    try:
        dash = httpx.get(f"{ADMIN_SERVICE_URL}/dashboard", headers={"x-master-key": MASTER_KEY}, timeout=10.0).json()
        fin = dash.get("financials", {})
        
        c1, c2, c3, c4 = st.columns(4)
        with c1: safe_html(f"<div class='metric-card'><div class='metric-val'>{fin.get('estimated_mrr')}</div><div class='metric-label'>GROSS MRR</div></div>")
        with c2: safe_html(f"<div class='metric-card'><div class='metric-val' style='color:#00cc66;'>{fin.get('gross_margin')}</div><div class='metric-label'>NET MARGIN</div></div>")
        with c3: safe_html(f"<div class='metric-card'><div class='metric-val' style='color:#ffaa00;'>{fin.get('est_api_costs_monthly')}</div><div class='metric-label'>EST API COST</div></div>")
        with c4: safe_html(f"<div class='metric-card'><div class='metric-val' style='color:#fff;'>{dash['licenses']['active']}</div><div class='metric-label'>ACTIVE USERS</div></div>")
        
        st.markdown("<br>### 👤 Recent Signups", unsafe_allow_html=True)
        st.table(dash.get("recent_signups", []))
    except: st.error("Admin dashboard offline.")

# ── MAIN LAYOUT ───────────────────────────────────────────────────────────────
if not st.session_state.authenticated: login()
else:
    render_header()
    with st.sidebar:
        if st.button("⏻ LOCK TERMINAL"):
            for k in _DEFAULTS: st.session_state[k] = _DEFAULTS[k]
            st.rerun()

    tabs = st.tabs(["⚡ THE FORGE", "🔬 X-RAY SCANNER", "🔩 THE SHOP FLOOR", "📊 LOGBOOK"] + (["🔐 CONTROL ROOM"] if st.session_state.is_admin else []))
    with tabs[0]: tab_new_build()
    with tabs[1]: tab_scanner()
    with tabs[2]: st.info("Workshop Active. Send a build here from The Forge.")
    with tabs[3]: st.info("Logbook syncing from Postgres.")
    if st.session_state.is_admin and len(tabs) > 4:
        with tabs[4]: tab_admin()

    safe_html("<div style='text-align:center; padding:40px; font-family:Share Tech Mono; color:#333; font-size:10px; letter-spacing:3px;'>AoC3P0 SYSTEMS · BUILD FOR THE FUTURE</div>")
