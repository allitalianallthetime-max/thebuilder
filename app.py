import streamlit as st
import os, httpx, time, base64, secrets, threading
from dotenv import load_dotenv
import html as html_lib

load_dotenv()
st.set_page_config(page_title="Bob the Robot Builder", page_icon="⚙️", layout="wide")

def get_url(env_var, default):
    val = os.getenv(env_var)
    return val.strip() if val and val.startswith("http") else default

AUTH_URL     = get_url("AUTH_SERVICE_URL", "http://localhost:10001")
AI_URL       = get_url("AI_SERVICE_URL", "http://localhost:10002")
ADMIN_URL    = get_url("ADMIN_SERVICE_URL", "http://localhost:10005")
EXPORT_URL   = get_url("EXPORT_SERVICE_URL", "http://localhost:10006")
WORKSHOP_URL = get_url("WORKSHOP_SERVICE_URL", "http://localhost:10007")
ANALYTICS_URL= get_url("ANALYTICS_SERVICE_URL", "http://localhost:10004")

INTERNAL_KEY = os.getenv("INTERNAL_API_KEY")
MASTER_KEY   = os.getenv("MASTER_KEY")
STRIPE_URL   = os.getenv("STRIPE_PAYMENT_URL", "#")

def api_headers():
    h = {"x-internal-key": INTERNAL_KEY}
    if st.session_state.get("user_token"): h["Authorization"] = f"Bearer {st.session_state['user_token']}"
    return h

# ── Clean Professional Engineering CSS ──
st.markdown("""
<style>
    :root { --bg: #0F172A; --panel: #1E293B; --text: #F8FAFC; --border: #334155; --accent: #2563EB; }
    .stApp { background-color: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    #MainMenu, footer, header { display: none !important; }
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
        background-color: #0F172A !important; color: var(--text) !important; border: 1px solid var(--border) !important; border-radius: 4px; font-size: 14px;
    }
    .stButton > button {
        background-color: var(--accent) !important; color: white !important; font-weight: 500; font-size: 14px; border: none; border-radius: 4px; padding: 10px 16px; width: 100%; transition: 0.2s;
    }
    .stButton > button:hover { background-color: #1D4ED8 !important; }
    h1, h2, h3, h4 { color: white !important; font-weight: 600 !important; border-bottom: 1px solid var(--border); padding-bottom: 8px; margin-bottom: 16px; }
    .status-console { background-color: #020617; border: 1px solid var(--border); padding: 12px; font-family: 'Consolas', monospace; font-size: 13px; color: #34D399; border-radius: 4px; margin-bottom: 15px; }
    .blueprint-panel { background-color: var(--panel); border: 1px solid var(--border); padding: 24px; border-radius: 6px; font-size: 15px; line-height: 1.6; }
    .stTabs [data-baseweb="tab-list"] { background-color: transparent !important; border-bottom: 1px solid var(--border); }
    .stTabs [data-baseweb="tab"] { color: #9CA3AF !important; font-weight: 500 !important; font-size: 14px !important; padding: 10px 20px !important; border: none !important; }
    .stTabs [aria-selected="true"] { color: white !important; border-bottom: 2px solid var(--accent) !important; background-color: rgba(59, 130, 246, 0.1) !important; }
</style>
""", unsafe_allow_html=True)

# ── State Management ──
defaults = {"auth": False, "tier": "guest", "name": "", "email": "", "token": "", "admin": False, "parts_list": "", "blueprint": None, "build_id": None, "last_project_type": None}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

def enforce_tier(feature):
    if st.session_state.tier in ["guest", "starter", "none", ""]:
        st.error(f"🔒 {feature} requires a Professional Engineering License.")
        st.markdown(f"[Upgrade License to Unlock]({STRIPE_URL})")
        return True
    return False

def poll_task(url: str, success_msg: str):
    box = st.empty(); bar = st.progress(0)
    with st.spinner("Processing computation..."):
        while True:
            time.sleep(1.5)
            try:
                r = httpx.get(url, headers=api_headers(), timeout=5.0).json()
                if r.get("status") in ["processing", "pending"]:
                    box.markdown(f"<div class='status-console'>[EXECUTING] {r.get('message', 'Calculating kinematics...')}</div>", unsafe_allow_html=True)
                    st.session_state._prog = min(90, getattr(st.session_state, '_prog', 10) + 15)
                    bar.progress(st.session_state._prog)
                elif r.get("status") == "complete":
                    bar.progress(100); box.success(f"✅ {success_msg}"); time.sleep(1)
                    box.empty(); bar.empty(); return r.get("result", True)
                elif r.get("status") == "failed":
                    box.error(f"Error: {r.get('error')}"); return None
            except: box.warning("Awaiting server connection..."); time.sleep(2)

# ── Authentication ──
if not st.session_state.auth:
    st.markdown("<div style='text-align:center; padding-top:10vh;'><h1 style='border:none; font-size:36px; color:#3B82F6;'>Bob the Robot Builder</h1><p style='color:#94A3B8; font-size:16px;'>Advanced Robotics Engineering & Physics Simulation Platform</p></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<div style='background:#1E293B; padding:24px; border-radius:6px; border:1px solid #334155;'>", unsafe_allow_html=True)
        st.markdown("<h3 style='border:none; margin-top:0;'>System Authentication</h3>", unsafe_allow_html=True)
        key = st.text_input("License Key", type="password", placeholder="Enter assigned credentials")
        if st.button("Access Terminal"):
            if MASTER_KEY and secrets.compare_digest(key, MASTER_KEY):
                st.session_state.update({"auth": True, "admin": True, "name": "Admin", "tier": "master", "email": "admin"}); st.rerun()
            else:
                try:
                    res = httpx.post(f"{AUTH_URL}/verify-license", json={"license_key": key}, headers=api_headers(), timeout=10)
                    if res.status_code == 200:
                        d = res.json(); st.session_state.update({"auth": True, "admin": False, "tier": d["tier"], "name": d["name"], "email": d["email"], "token": d["token"]}); st.rerun()
                    else: st.error("Invalid credentials.")
                except: st.error("Authentication Service Offline.")
        if STRIPE_URL and STRIPE_URL != "#":
            st.markdown(f"<div style='text-align:center; margin-top:15px;'><a href='{STRIPE_URL}' style='color:#60A5FA; text-decoration:none; font-size:14px;'>Acquire Commercial License</a></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

else:
    # Header
    st.markdown(f"<div style='display:flex; justify-content:space-between; padding: 15px 20px; background:#1E293B; border-bottom:1px solid #334155; margin-bottom:20px;'><div><strong style='font-size:18px;'>Bob the Robot Builder</strong></div><div><span style='background:#2563EB; padding:4px 10px; border-radius:4px; font-size:12px;'>{st.session_state.tier.upper()} LICENSE</span></div></div>", unsafe_allow_html=True)
    
    tabs = st.tabs(["🏗️ Engineering Workspace", "🌐 Global Network & Simulation", "⚙️ System Admin"] if st.session_state.admin else ["🏗️ Engineering Workspace", "🌐 Global Network & Simulation"])

    # ── TAB 1: WORKSPACE & VISION ──
    with tabs[0]:
        c1, c2 = st.columns([1, 2], gap="large")
        with c1:
            st.markdown("### 1. Component Identification")
            st.markdown("<span style='font-size:14px; color:#94A3B8;'>Upload imagery of raw materials to automatically extract a Bill of Materials.</span>", unsafe_allow_html=True)
            img = st.file_uploader("Upload Image (Hardware)", type=["jpg", "png", "jpeg"], label_visibility="collapsed")
            if st.button("Run Diagnostic Hardware Scan"):
                if img:
                    b64 = base64.b64encode(img.getvalue()).decode("utf-8")
                    r = httpx.post(f"{WORKSHOP_URL}/scan/base64", json={"image_base64": f"data:{img.type};base64,{b64}", "user_email": st.session_state.email, "context": "Identify mechanical components"}, headers=api_headers(), timeout=15)
                    if r.status_code == 200 and (res := poll_task(f"{WORKSHOP_URL}/task/status/{r.json()['task_id']}", "Extraction complete.")):
                        parts_list = "\n".join([f"- {c.get('name')} (x{c.get('quantity', 1)})" for c in res.get('scan_result', {}).get('components', [])])
                        st.session_state.parts_list = parts_list
                        st.rerun()

            st.markdown("<br>### 2. Assembly Parameters", unsafe_allow_html=True)
            parts_input = st.text_area("Bill of Materials (Auto-filled from above)", value=st.session_state.parts_list, height=150, placeholder="- 12V High-Torque Motor\n- Aluminum chassis\n- Arduino Microcontroller")
            robot_type = st.selectbox("Design Classification", ["Industrial Automation Arm", "Autonomous Surveillance Drone", "Heavy Logistics Rover", "Bipedal Utility Mech", "Pneumatic Exoskeleton"])
            detail = st.radio("Documentation Depth", ["Standard Assembly Draft", "Advanced Engineering Schematic"])
            
            if st.button("Compile Engineering Blueprint"):
                if not parts_input.strip(): st.warning("Bill of Materials required."); st.stop()
                r = httpx.post(f"{AI_URL}/generate", json={"junk_desc": parts_input, "project_type": robot_type, "detail_level": detail, "user_email": st.session_state.email}, headers=api_headers(), timeout=10)
                if r.status_code == 200:
                    if res := poll_task(f"{AI_URL}/generate/status/{r.json()['task_id']}", "Blueprint Generated Successfully."):
                        st.session_state.blueprint = res["content"]; st.session_state.build_id = res["build_id"]; st.session_state.last_project_type = robot_type
                        st.session_state.parts_list = parts_input
                        st.rerun()
                elif r.status_code == 402: st.error("Quota exceeded. Upgrade license.")

        with c2:
            st.markdown("### 3. Output Schematics")
            if st.session_state.blueprint:
                st.markdown(f"<div class='blueprint-panel'>{st.session_state.blueprint}</div>", unsafe_allow_html=True)
                if st.button("Export Standardized PDF"):
                    r = httpx.post(f"{EXPORT_URL}/export/pdf", json={"blueprint": st.session_state.blueprint, "project_type": st.session_state.last_project_type, "build_id": st.session_state.build_id, "tier": st.session_state.tier}, headers=api_headers(), timeout=30)
                    if r.status_code == 200: st.download_button("Download Secure PDF", data=r.content, file_name=f"BOB_Schematic_{st.session_state.build_id}.pdf", mime="application/pdf")
            else:
                st.info("Awaiting input data to generate schematics.")

    # ── TAB 2: NETWORK & SIMULATION ──
    with tabs[1]:
        c_net, c_sim = st.columns([1, 1.5], gap="large")
        with c_net:
            st.markdown("### Engineering Communications")
            if not enforce_tier("Global Comms"):
                @st.fragment(run_every=3)
                def chat_box():
                    try:
                        msgs = httpx.get(f"{AI_URL}/arena/chat/recent", headers=api_headers(), timeout=2).json()
                        html = "<div style='height:400px; overflow-y:auto; background:#0F172A; border:1px solid #334155; padding:15px; border-radius:4px; font-size:14px;'>"
                        for m in msgs: html += f"<div style='margin-bottom:8px; border-bottom: 1px solid #1E293B; padding-bottom: 5px;'><span style='color:#64748B;'>[{m.get('time')}]</span> <strong style='color:#60A5FA;'>[{m.get('tier','').upper()}] {html_lib.escape(m.get('user'))}:</strong> <span style='color:#E2E8F0;'>{html_lib.escape(m.get('text'))}</span></div>"
                        st.markdown(html + "</div>", unsafe_allow_html=True)
                    except: pass
                chat_box()
                with st.form("chat", clear_on_submit=True):
                    msg = st.text_input("Transmit Data", label_visibility="collapsed")
                    if st.form_submit_button("Send") and msg.strip():
                        httpx.post(f"{AI_URL}/arena/chat/send", json={"user_name": st.session_state.name, "tier": st.session_state.tier, "message": msg}, headers=api_headers())

        with c_sim:
            st.markdown("### Structural & Physics Simulation")
            st.markdown("<p style='font-size:14px; color:#94A3B8;'>Run a physics-based kinetic simulation between two operational designs to test material stress and kinetic impact.</p>", unsafe_allow_html=True)
            if not enforce_tier("Physics Simulator"):
                ca, cb = st.columns(2)
                with ca: 
                    r1 = st.text_input("Subject A Designation", "Unit Alpha")
                    s1 = st.text_area("Subject A Specs", st.session_state.parts_list or "Heavy servo motors, steel frame.", height=100)
                with cb: 
                    r2 = st.text_input("Subject B Designation", "Unit Beta")
                    s2 = st.text_area("Subject B Specs", "Pneumatic hydraulics, carbon fiber.", height=100)
                if st.button("Execute Kinematic Test"):
                    r = httpx.post(f"{AI_URL}/arena/battle", json={"robot_a_name": r1, "robot_a_specs": s1, "robot_b_name": r2, "robot_b_specs": s2}, headers=api_headers(), timeout=10)
                    if r.status_code == 200 and (res := poll_task(f"{AI_URL}/generate/status/{r.json()['task_id']}", "Simulation Complete")):
                        st.markdown(f"<div class='blueprint-panel' style='font-family: monospace;'>{res['combat_log'].replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

    # ── TAB 3: ADMIN ──
    if st.session_state.admin and len(tabs) > 2:
        with tabs[2]:
            st.markdown("### System Administration")
            try:
                d = httpx.get(f"{ADMIN_URL}/dashboard", headers={"x-master-key": MASTER_KEY}, timeout=10).json()
                c1, c2, c3 = st.columns(3)
                c1.metric("Gross MRR", d.get("financials", {}).get("estimated_mrr"))
                c2.metric("Net Margin", d.get("financials", {}).get("gross_margin"))
                c3.metric("Active Users", d.get("licenses", {}).get("active"))
            except: st.error("Admin API offline.")
