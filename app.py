"""
app.py — The MECH FORGE UI (Ultimate Edition)
=============================================
AoC3P0 Systems · AI-Powered Robotics Forge
CRT Scanlines, Deep Mech Customization, and Arena Combat.
"""

import streamlit as st
import streamlit.components.v1 as components
import os, html as html_lib, secrets, httpx, time, base64, threading
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="MECH FORGE | AoC3P0", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

def normalize_url(raw: str, default: str) -> str:
    if not raw: return default
    return raw.strip() if raw.startswith("http") else f"http://{raw}:10000"

AUTH_URL     = normalize_url(os.getenv("AUTH_SERVICE_URL"), "http://localhost:10001")
AI_URL       = normalize_url(os.getenv("AI_SERVICE_URL"), "http://localhost:10002")
ADMIN_URL    = normalize_url(os.getenv("ADMIN_SERVICE_URL"), "http://localhost:10005")
EXPORT_URL   = normalize_url(os.getenv("EXPORT_SERVICE_URL"), "http://localhost:10006")
WORKSHOP_URL = normalize_url(os.getenv("WORKSHOP_SERVICE_URL"), "http://localhost:10007")
ANALYTICS_URL = normalize_url(os.getenv("ANALYTICS_SERVICE_URL"), "http://localhost:10004")

INTERNAL_API_KEY   = os.getenv("INTERNAL_API_KEY")
MASTER_KEY         = os.getenv("MASTER_KEY")
STRIPE_PAYMENT_URL = os.getenv("STRIPE_PAYMENT_URL", "#")

_IFRAME_CSS = '<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&family=Orbitron:wght@700;900&display=swap" rel="stylesheet">'
def safe_html(content: str, height: int = 0):
    if height > 0:
        components.html(f"<html><head>{_IFRAME_CSS}<style>body{{margin:0;padding:0;background:transparent;overflow:hidden;font-family:'Rajdhani',sans-serif;color:#e8d5b0;}}</style></head><body>{content}</body></html>", height=height, scrolling=False)
        return
    st.markdown(content, unsafe_allow_html=True)

def esc(text): return html_lib.escape(str(text)) if text else ""
def api_headers():
    h = {"x-internal-key": INTERNAL_API_KEY}
    if st.session_state.get("user_token"): h["Authorization"] = f"Bearer {st.session_state['user_token']}"
    return h

def track_event(event_type: str, metadata: dict = None):
    email = st.session_state.get("user_email", "guest")
    def _send():
        try: httpx.post(f"{ANALYTICS_URL}/track/event", json={"event_type": event_type, "user_email": email, "metadata": metadata or {}}, headers={"x-internal-key": INTERNAL_API_KEY}, timeout=3.0)
        except: pass 
    threading.Thread(target=_send).start()

# ── 1. INSANE CYBERPUNK CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Share+Tech+Mono&family=Orbitron:wght@700;900&family=Rajdhani:wght@500;700&display=swap');
:root { --orange: #ff4400; --dark: #030303; --border: #3a1500; --text: #ffcc88; --green: #00ff66; --red: #ff2222; }
html, body, .stApp { background-color: var(--dark) !important; color: var(--text) !important; font-family: 'Rajdhani', sans-serif !important; }

/* CRT Scanline Effect overlay on the whole app */
.stApp::before {
    content: " "; display: block; position: absolute; top: 0; left: 0; bottom: 0; right: 0;
    background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
    z-index: 999; background-size: 100% 2px, 3px 100%; pointer-events: none; opacity: 0.6;
}

#MainMenu, footer, header, .stDeployButton { display: none !important; }
::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: var(--orange); }

/* Badass Glow Buttons */
.stButton > button { 
    background: linear-gradient(135deg,#aa2200,var(--orange)) !important; color: #000 !important; border: 1px solid #ffaa00 !important; 
    font-family: 'Orbitron', sans-serif !important; font-size: 18px !important; letter-spacing: 4px !important; 
    padding: 12px 30px !important; clip-path: polygon(15px 0%,100% 0%,calc(100% - 15px) 100%,0% 100%) !important; 
    transition: all .2s !important; box-shadow: 0 0 20px rgba(255,68,0,.4) !important; width: 100%; text-shadow: 0 0 5px rgba(255,255,255,0.5);
}
.stButton > button:hover { transform: scale(1.02) !important; box-shadow: 0 0 40px rgba(255,68,0,.8) !important; background: #ffaa00 !important;}

/* Inputs & Selects */
.stTextArea textarea, .stTextInput input, .stSelectbox > div > div { 
    background: rgba(10,5,0,0.8) !important; border: 1px solid var(--border) !important; color: var(--green) !important; 
    font-family: 'Share Tech Mono', monospace !important; border-radius: 0 !important; box-shadow: inset 0 0 10px rgba(0,0,0,1);
}
.stTextArea textarea:focus, .stTextInput input:focus { border-color: var(--orange) !important; box-shadow: 0 0 15px rgba(255,68,0,.3) !important; }

.sec-head { display:flex; align-items:center; gap:14px; margin-bottom:20px; margin-top:20px;}
.sec-num { font-family:'Orbitron',sans-serif; font-size:40px; color:var(--orange); opacity: 0.5;}
.sec-title{ font-family:'Bebas Neue',sans-serif; font-size:30px; color:#fff; letter-spacing:4px; text-shadow: 0 0 10px var(--orange);}
.sec-line { flex:1; height:2px; background:linear-gradient(90deg,var(--orange),transparent); }

.terminal-box { background: #020202; border: 1px solid #333; border-left: 4px solid var(--orange); padding: 15px; font-family: 'Share Tech Mono', monospace; color: var(--green); font-size: 14px; margin-bottom: 15px; text-shadow: 0 0 5px rgba(0,255,100,0.5);}
.stProgress > div > div > div > div { background-color: var(--orange) !important; box-shadow: 0 0 10px var(--orange) !important;}
</style>
""", unsafe_allow_html=True)

_DEFAULTS = {"authenticated": False, "user_tier": "guest", "user_name": "", "user_email": "", "user_token": "", "is_admin": False, "last_blueprint": None, "last_build_id": None, "last_project_type": None, "last_junk_input": None, "prefill_workbench": "", "last_scan": None}
for _key, _val in _DEFAULTS.items():
    if _key not in st.session_state: st.session_state[_key] = _val

def sec_head(num, title): safe_html(f"<div class='sec-head'><div class='sec-num'>{esc(num)}</div><div class='sec-title'>{esc(title)}</div><div class='sec-line'></div></div>")

def upgrade_wall(feature_name: str):
    if st.session_state.user_tier in ["guest", "starter", "none"]:
        safe_html(f"""<div style="background:rgba(20,0,0,0.8); border:1px solid var(--red); border-left:4px solid var(--red); padding:20px; margin:20px 0;"><h3 style="color:var(--red); margin-top:0; font-family:'Orbitron'; font-size: 24px;">⛔ CLEARANCE LEVEL INSUFFICIENT: {feature_name}</h3><p style="color:#aaa; font-family:'Share Tech Mono'; font-size:12px;">Your current security clearance restricts this action. Upgrade to PRO tier to bypass.</p><a href="{STRIPE_PAYMENT_URL}" target="_blank" style="display:inline-block; background:var(--red); color:#000; padding:10px 20px; font-family:'Orbitron'; text-decoration:none; font-weight:bold;">⚡ OVERRIDE CLEARANCE (UPGRADE)</a></div>""")
        return True
    return False

def poll_task(poll_url: str, success_msg: str):
    status_box = st.empty(); progress_bar = st.progress(0)
    with st.spinner("Establishing secure uplink..."):
        while True:
            time.sleep(2.0)
            try:
                r = httpx.get(poll_url, headers=api_headers(), timeout=5.0)
                data = r.json(); state = data.get("status")
                if state in ["processing", "pending"]:
                    status_box.markdown(f"<div class='terminal-box'>⏳ [PROCESSING] {data.get('message', 'Compiling geometry...')}</div>", unsafe_allow_html=True)
                    st.session_state._sim_prog = min(90, getattr(st.session_state, '_sim_prog', 10) + 15)
                    progress_bar.progress(st.session_state._sim_prog)
                elif state == "complete":
                    progress_bar.progress(100)
                    status_box.markdown(f"<div class='terminal-box' style='border-left-color:#00ff66; color:#00ff66;'>✅ [SUCCESS] {success_msg}</div>", unsafe_allow_html=True)
                    st.session_state._sim_prog = 10; time.sleep(1.5)
                    status_box.empty(); progress_bar.empty()
                    return data.get("result", True)
                elif state == "failed":
                    status_box.error(f"⛔ SYSTEM FAILURE: {data.get('error', 'Unknown anomaly')}")
                    return None
            except: status_box.warning("📡 Waiting for telemetry..."); time.sleep(2)

# ── 2. THE JAW-DROPPING LOGIN SCREEN ─────────────────────────────────────────
def login():
    st.markdown("""<style>[data-testid="stSidebar"] {display: none;}</style>""", unsafe_allow_html=True)
    
    _hero = """
    <style>
    @keyframes scanline { 0% { transform: translateY(-100%); } 100% { transform: translateY(100vh); } }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
    @keyframes glitch { 0% { text-shadow: 2px 0 #ff2222, -2px 0 #00ff66; } 50% { text-shadow: -2px 0 #ff2222, 2px 0 #00ff66; } 100% { text-shadow: 2px 0 #ff2222, -2px 0 #00ff66; } }
    </style>
    <div style="position:relative; min-height:55vh; background: radial-gradient(circle at center, #1a0a00 0%, #000 70%); display:flex; flex-direction:column; align-items:center; justify-content:center; overflow:hidden; border-bottom: 2px solid #ff4400; box-shadow: 0 10px 50px rgba(255,68,0,0.15);">
        <div style="position:absolute; width:100%; height:150px; background:linear-gradient(to bottom, transparent, rgba(255,85,0,0.1), transparent); animation: scanline 4s linear infinite; pointer-events:none;"></div>
        <div style="position:absolute; inset:0; background-image: linear-gradient(#111 1px, transparent 1px), linear-gradient(90deg, #111 1px, transparent 1px); background-size: 30px 30px; opacity:0.3;"></div>
        
        <div style="z-index:10; text-align:center;">
            <div style="font-family:'Share Tech Mono',monospace; font-size:14px; letter-spacing:10px; color:#ff3300; margin-bottom:15px; animation: blink 2s infinite;">WARNING: RESTRICTED MILITARY NETWORK</div>
            <div style="font-family:'Orbitron',sans-serif; font-size:clamp(60px, 10vw, 130px); font-weight:900; line-height:0.9; letter-spacing:15px; color:#ff4400; text-shadow: 0 0 20px #ff4400, 2px 0 #fff; animation: glitch 3s infinite;">MECH FORGE</div>
            <div style="margin-top:20px; font-family:'Share Tech Mono',monospace; font-size:18px; color:#00ff66; letter-spacing:4px; text-transform: uppercase;">▶ Initialize Auto-Battler & Engineering Suite_</div>
        </div>
    </div>
    """
    safe_html(_hero, height=400)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        safe_html("<div style='background:rgba(10,5,0,0.9); border:1px solid #331100; border-top:4px solid #ff5500; padding:40px; box-shadow: 0 15px 40px rgba(0,0,0,0.9); margin-top: -40px; position:relative; z-index:20; backdrop-filter: blur(10px);'>")
        
        st.markdown("<h3 style='color:#fff; font-family:Orbitron; text-align:center; letter-spacing: 2px; font-size:18px;'>INSERT COMMANDER CREDENTIALS</h3>", unsafe_allow_html=True)
        key_input = st.text_input("LICENSE KEY", type="password", placeholder="XXXX-XXXX-XXXX...", label_visibility="collapsed")
        
        if st.button("⚡ INITIALIZE NEURAL LINK"):
            if MASTER_KEY and secrets.compare_digest(key_input, MASTER_KEY):
                st.session_state.update({"authenticated": True, "is_admin": True, "user_name": "Commander", "user_tier": "master", "user_email": "admin"}); st.rerun()
            else:
                with st.spinner("Decrypting credential payload..."):
                    try:
                        resp = httpx.post(f"{AUTH_URL}/verify-license", json={"license_key": key_input}, headers=api_headers(), timeout=10.0)
                        if resp.status_code == 200:
                            data = resp.json()
                            st.session_state.update({"authenticated": True, "is_admin": False, "user_tier": data.get("tier", "pro"), "user_name": data.get("name", "Builder"), "user_email": data.get("email", ""), "user_token": data.get("token", "")})
                            st.rerun()
                        else: st.error("⛔ OVERRIDE DENIED: INVALID KEY")
                    except: st.error("Auth Server Offline. Check DNS/Render Logs.")
        
        safe_html("</div>")
        if STRIPE_PAYMENT_URL and STRIPE_PAYMENT_URL != "#":
            st.markdown(f'<div style="text-align:center; margin-top:30px;"><a href="{STRIPE_PAYMENT_URL}" target="_blank" style="color:#ffaa00; font-family:\'Share Tech Mono\'; font-size:14px; text-decoration:none; border-bottom:1px solid #ffaa00; padding-bottom:2px; letter-spacing: 2px; text-transform: uppercase;">[ Acquire Clearance Badge ]</a></div>', unsafe_allow_html=True)

def render_header():
    safe_html(f"""<div style="background:linear-gradient(90deg, #110500, #000); border-bottom:2px solid #ff4400; padding:15px 40px; display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px; box-shadow: 0 5px 20px rgba(255,68,0,0.2);"><div><span style="font-family:'Orbitron',sans-serif; font-size:28px; color:#ff4400; letter-spacing:6px; text-shadow: 0 0 10px #ff4400;">AOC3P0 NEURAL NET</span></div><div style="text-align:right;"><span style="font-family:'Share Tech Mono',monospace; font-size:14px; color:#000; border:1px solid #00ff66; padding:5px 15px; background:#00ff66; font-weight:bold; box-shadow: 0 0 10px #00ff66;">LEVEL: {st.session_state.user_tier.upper()}</span></div></div>""")

# ── 3. MASSIVE ROBOT BUILDER OPTIONS ─────────────────────────────────────────
def tab_new_build():
    sec_head("01", "CHASSIS & CORE CONFIGURATION")
    
    # 3-Column Layout for deep configuration
    c1, c2, c3 = st.columns(3)
    with c1:
        mech_class = st.selectbox("MECH CLASSIFICATION", [
            "Heavy Siege Mech (Bipedal)", "Autonomous Combat Drone", "Scrap-Built Exoskeleton", 
            "Sentry Turret (AI-Tracking)", "High-Mobility Quadruped", "EMP Defusal Rover", 
            "Swarm-Bot Commander Unit", "Plasma-Cutting Fabrication Arm", "Hydraulic Power Loader",
            "Deep-Sea Salvage Crawler", "Cybernetic Prosthetic Interface"
        ])
    with c2:
        power_core = st.selectbox("POWER CORE", [
            "Scavenged Diesel Generator", "High-Discharge Li-Po Array", "Micro-Fusion Reactor", 
            "Solar-Capacitor Hybrid", "Kinetic-Flywheel System"
        ])
    with c3:
        armor_type = st.selectbox("ARMOR PLATING", [
            "Rusted Iron Scrap", "Titanium Carbon-Weave", "Ablative Ceramic", 
            "Tungsten Alloy", "Scavenged Kevlar & Diamond-Plate"
        ])

    st.markdown("<br>", unsafe_allow_html=True)
    sec_head("02", "RAW MATERIALS & INVENTORY")
    
    prefill = st.session_state.pop("prefill_workbench", "")
    junk_input = st.text_area("LIST AVAILABLE SALVAGE / WEAPONRY", value=prefill, placeholder="Example: 5HP electric motor, dual buzz-saws, arduino mega, hydraulic pistons, laser diode...", height=100)
    
    detail = st.radio("ENGINEERING DETAIL LEVEL", ["Quick Concept (Novice)", "Full Schematic (Journeyman)"] + (["Master-Class Blueprint (Expert)"] if st.session_state.user_tier in ["master", "pro"] else []), horizontal=True)

    st.markdown("<br/>", unsafe_allow_html=True)
    if st.button("🔥 IGNITE FORGE (COMPILE SCHEMATICS)"):
        if not junk_input.strip(): st.warning("⚠ Salvage inventory required."); return
        
        # Combine the dropdowns into a massive prompt for the AI
        combined_desc = f"CLASS: {mech_class} | CORE: {power_core} | ARMOR: {armor_type} | RAW PARTS: {junk_input}"
        track_event("forge_started", {"project_type": mech_class})
        
        try:
            resp = httpx.post(f"{AI_URL}/generate", json={"junk_desc": combined_desc, "project_type": mech_class, "detail_level": detail, "user_email": st.session_state.user_email}, headers=api_headers(), timeout=10.0)
            if resp.status_code == 200:
                result = poll_task(f"{AI_URL}/generate/status/{resp.json()['task_id']}", "Schematics Compiled!")
                if result:
                    st.session_state.last_blueprint = result["content"]; st.session_state.last_build_id = result["build_id"]; st.session_state.last_project_type = mech_class; st.session_state.last_junk_input = combined_desc
                    st.rerun()
            elif resp.status_code == 402: st.error("⛔ CREDITS EXHAUSTED.")
        except Exception as e: st.error(f"Forge offline: {e}")

    if st.session_state.last_blueprint:
        st.markdown("<div style='border: 1px solid #ff4400; padding: 20px; background: rgba(10,0,0,0.5); box-shadow: inset 0 0 20px rgba(255,68,0,0.2);'>", unsafe_allow_html=True)
        st.markdown(st.session_state.last_blueprint)
        st.markdown("</div>", unsafe_allow_html=True)
        
        sec_head("03", "DEPLOYMENT OPTIONS")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📄 PRINT SECURE PDF"):
                try:
                    r = httpx.post(f"{EXPORT_URL}/export/pdf", json={"blueprint": st.session_state.last_blueprint, "project_type": st.session_state.last_project_type, "junk_desc": st.session_state.last_junk_input, "build_id": st.session_state.last_build_id, "tier": st.session_state.user_tier}, headers=api_headers(), timeout=30.0)
                    if r.status_code == 200: st.download_button("⬇ DOWNLOAD SECURE FILE", data=r.content, file_name=f"MECH_{st.session_state.last_build_id}.pdf", mime="application/pdf")
                except: st.error("Print shop offline.")
        with col2:
            if st.button("🔩 SEND TO PROVING GROUNDS"):
                st.success("Save this Rig's specs! Go to the Proving Grounds tab to battle it against others.")

# ── 4. ARENA & CHAT ──────────────────────────────────────────────────────────
@st.fragment(run_every=2)
def render_global_chat():
    try:
        messages = httpx.get(f"{AI_URL}/arena/chat/recent", headers=api_headers(), timeout=2.0).json()
        chat_html = "<div id='arena-chat' style='height:400px; overflow-y:auto; background:#050505; border:1px solid #ff4400; padding:15px; display:flex; flex-direction:column; gap:8px; box-shadow: inset 0 0 20px rgba(255,68,0,0.1);'>"
        for msg in messages:
            color = "#ff4400" if msg.get('tier') == 'master' else "#00ff66" if msg.get('tier') == 'pro' else "#888"
            chat_html += f"""<div style="font-family:'Share Tech Mono', monospace; font-size:14px; border-bottom: 1px solid #111; padding-bottom: 5px;"><span style="color:#444; font-size:10px;">[{msg.get('time', '')}]</span> <strong style="color:{color}; font-family:'Orbitron'; font-size:16px;">[{msg.get('tier','GUEST').upper()}] {esc(msg.get('user',''))}:</strong> <span style="color:#ddd; text-shadow:none;">{esc(msg.get('text',''))}</span></div>"""
        safe_html(chat_html + "</div><script>var cb = document.getElementById('arena-chat'); if(cb){cb.scrollTop = cb.scrollHeight;}</script>")
    except: pass

def tab_arena():
    sec_head("⚔️", "THE PROVING GROUNDS")
    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.markdown("<h3 style='font-family:Orbitron; color:#ff4400;'>📡 GLOBAL COMMS</h3>", unsafe_allow_html=True)
        if not upgrade_wall("Global Comms Link"):
            render_global_chat()
            with st.form("chat_form", clear_on_submit=True):
                msg = st.text_input("Transmit to network...", label_visibility="collapsed")
                if st.form_submit_button("TRANSMIT") and msg.strip():
                    httpx.post(f"{AI_URL}/arena/chat/send", json={"user_name": st.session_state.user_name, "tier": st.session_state.user_tier, "message": msg}, headers=api_headers())
                    st.rerun()
    with col2:
        st.markdown("<h3 style='font-family:Orbitron; color:#ff4400;'>🔥 VIRTUAL COMBAT SIMULATOR</h3>", unsafe_allow_html=True)
        c_a, c_b = st.columns(2)
        with c_a: robot_a = st.text_input("YOUR RIG", value="Titanium Crusher"); desc_a = st.text_area("YOUR SPECS", value=st.session_state.last_junk_input or "Bipedal mech, 5HP motor, circular saw", height=120)
        with c_b: robot_b = st.text_input("CHALLENGER", value="Hydra-Flipp"); desc_b = st.text_area("ENEMY SPECS", value="Pneumatic flipper, extreme speed, Ablative armor.", height=120)
        if st.button("⚡ INITIATE COMBAT SEQUENCE", use_container_width=True):
            if not upgrade_wall("Virtual Auto-Battler"):
                try:
                    resp = httpx.post(f"{AI_URL}/arena/battle", json={"robot_a_name": robot_a, "robot_a_specs": desc_a, "robot_b_name": robot_b, "robot_b_specs": desc_b}, headers=api_headers(), timeout=10.0)
                    if resp.status_code == 200:
                        res = poll_task(f"{AI_URL}/generate/status/{resp.json()['task_id']}", "Combat Complete!")
                        if res and "combat_log" in res: safe_html(f"<div class='terminal-box' style='color:#e8d5b0; border-left-color:var(--red); font-size:16px; line-height:1.6;'>{res['combat_log'].replace(chr(10), '<br>')}</div>")
                except: st.error("Arena offline.")

# ── 5. X-RAY SCANNER ─────────────────────────────────────────────────────────
def tab_scanner():
    sec_head("🔬", "X-RAY VISION SCANNER")
    if upgrade_wall("AI Vision Teardown"): return
    c1, c2 = st.columns([1.5, 1])
    with c1: uploaded_file = st.file_uploader("DROP SALVAGE PHOTO", type=["jpg", "png", "webp"])
    with c2: context = st.text_area("CONTEXT / LOCATION", placeholder="e.g. Found in an abandoned factory")
    if st.button("👁️ INITIATE DEEP SCAN"):
        if uploaded_file:
            img_b64 = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
            r = httpx.post(f"{WORKSHOP_URL}/scan/base64", json={"image_base64": f"data:{uploaded_file.type};base64,{img_b64}", "user_email": st.session_state.user_email, "context": context}, headers=api_headers(), timeout=10.0)
            if r.status_code == 200 and (res := poll_task(f"{WORKSHOP_URL}/task/status/{r.json()['task_id']}", "Analysis Complete.")): 
                st.session_state.last_scan = res; st.rerun()

    scan = st.session_state.get("last_scan")
    if scan and scan.get("scan_result"):
        res = scan["scan_result"]
        st.markdown(f"<h2 style='color:var(--green);font-family:Orbitron;'>🎯 IDENTIFIED: {res.get('identification', {}).get('equipment_name', 'UNKNOWN')}</h2>", unsafe_allow_html=True)
        with st.expander("VIEW RAW ENGINEERING DATA"): st.json(res)
        if st.button("📋 SEND TO MECH FORGE"):
            r = httpx.post(f"{WORKSHOP_URL}/scans/{scan['scan_id']}/to-workbench", headers=api_headers(), timeout=10.0)
            if r.status_code == 200: st.session_state["prefill_workbench"] = r.json()["workbench_text"]; st.success("✅ Sent!"); st.rerun()

# ── 6. ADMIN DASHBOARD ───────────────────────────────────────────────────────
def tab_admin():
    sec_head("👑", "COMMANDER DASHBOARD")
    if not st.session_state.is_admin: return
    try:
        dash = httpx.get(f"{ADMIN_URL}/dashboard", headers={"x-master-key": MASTER_KEY}, timeout=10.0).json()
        fin = dash.get("financials", {})
        c1, c2, c3 = st.columns(3)
        with c1: safe_html(f"<div class='terminal-box' style='text-align:center;'><div style='font-family:Orbitron; font-size:40px; color:var(--orange);'>{fin.get('estimated_mrr')}</div><div style='color:#666;'>GROSS MRR</div></div>")
        with c2: safe_html(f"<div class='terminal-box' style='text-align:center;'><div style='font-family:Orbitron; font-size:40px; color:var(--green);'>{fin.get('gross_margin')}</div><div style='color:#666;'>NET MARGIN</div></div>")
        with c3: safe_html(f"<div class='terminal-box' style='text-align:center;'><div style='font-family:Orbitron; font-size:40px; color:#fff;'>{dash.get('licenses', {}).get('active')}</div><div style='color:#666;'>ACTIVE OPERATORS</div></div>")
    except: st.error("Admin dashboard offline.")

# ── MAIN LAYOUT ───────────────────────────────────────────────────────────────
if not st.session_state.authenticated: login()
else:
    render_header()
    with st.sidebar:
        st.markdown("<h2 style='font-family:Orbitron; color:#ff4400; text-align:center;'>SYSTEMS</h2>", unsafe_allow_html=True)
        if st.button("⏻ DISCONNECT NEURAL LINK"):
            for k in _DEFAULTS: st.session_state[k] = _DEFAULTS[k]
            st.rerun()
            
    # Clean up standard Streamlit Tabs
    st.markdown("""<style>.stTabs [data-baseweb="tab-list"] button { font-family: 'Orbitron', sans-serif !important; letter-spacing: 2px !important; font-size: 18px !important; }</style>""", unsafe_allow_html=True)
    
    tabs = st.tabs(["⚡ MECH FORGE", "⚔️ PROVING GROUNDS", "🔬 X-RAY SCANNER", "🔐 COMMANDER"] if st.session_state.is_admin else ["⚡ MECH FORGE", "⚔️ PROVING GROUNDS", "🔬 X-RAY SCANNER"])
    
    with tabs[0]: tab_new_build()
    with tabs[1]: tab_arena()
    with tabs[2]: tab_scanner()
    if st.session_state.is_admin:
        with tabs[3]: tab_admin()
