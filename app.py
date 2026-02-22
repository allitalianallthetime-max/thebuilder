import streamlit as st
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
MASTER_KEY = os.getenv("MASTER_KEY")

st.set_page_config(page_title="THE BUILDER", page_icon="⚙️", layout="wide")

# ── FORGE UI STYLES ───────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');

/* ── GLOBAL RESET ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, .stApp {
    background-color: #0a0a0a !important;
    color: #e8d5b0 !important;
    font-family: 'Rajdhani', sans-serif !important;
}

/* ── ANIMATED FORGE BACKGROUND ── */
.stApp::before {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: 
        radial-gradient(ellipse at 20% 50%, rgba(255, 80, 0, 0.04) 0%, transparent 60%),
        radial-gradient(ellipse at 80% 20%, rgba(255, 140, 0, 0.03) 0%, transparent 50%),
        repeating-linear-gradient(
            0deg,
            transparent,
            transparent 2px,
            rgba(255, 100, 0, 0.015) 2px,
            rgba(255, 100, 0, 0.015) 4px
        );
    pointer-events: none;
    z-index: 0;
}

/* ── HIDE STREAMLIT CHROME ── */
#MainMenu, footer, header, .stDeployButton { display: none !important; }
.block-container { 
    padding: 0 !important; 
    max-width: 100% !important;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background: #0d0d0d !important;
    border-right: 1px solid #2a1a0a !important;
    min-width: 260px !important;
}
[data-testid="stSidebar"] > div {
    padding: 0 !important;
}

.sidebar-header {
    background: linear-gradient(135deg, #1a0a00, #0d0d0d);
    border-bottom: 2px solid #ff6600;
    padding: 30px 20px 20px;
    position: relative;
    overflow: hidden;
}
.sidebar-header::after {
    content: '⚙';
    position: absolute;
    right: -10px;
    top: -10px;
    font-size: 80px;
    opacity: 0.06;
    animation: spin 20s linear infinite;
}
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.sidebar-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 28px;
    color: #ff6600;
    letter-spacing: 3px;
    text-shadow: 0 0 20px rgba(255, 100, 0, 0.5);
    line-height: 1;
}
.sidebar-subtitle {
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: #666;
    letter-spacing: 2px;
    margin-top: 4px;
    text-transform: uppercase;
}

.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #00ff88;
    border-radius: 50%;
    margin-right: 6px;
    box-shadow: 0 0 8px #00ff88;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 8px #00ff88; }
    50% { opacity: 0.5; box-shadow: 0 0 20px #00ff88; }
}

.sys-status {
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: #00ff88;
    margin-top: 12px;
    letter-spacing: 1px;
}

.sidebar-nav-item {
    padding: 12px 20px;
    border-left: 3px solid transparent;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 600;
    font-size: 13px;
    letter-spacing: 2px;
    color: #888;
    text-transform: uppercase;
    transition: all 0.2s;
    cursor: pointer;
    font-family: 'Share Tech Mono', monospace;
}

/* ── MAIN AREA ── */
.main-wrap {
    padding: 0;
    min-height: 100vh;
}

/* ── TOP HEADER BAR ── */
.forge-header {
    background: linear-gradient(90deg, #0d0500, #0a0a0a, #050d00);
    border-bottom: 1px solid #1f1005;
    padding: 20px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: relative;
    overflow: hidden;
}
.forge-header::before {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, #ff6600, #ffaa00, #ff6600, transparent);
}
.forge-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 52px;
    letter-spacing: 8px;
    color: #ff6600;
    text-shadow: 
        0 0 30px rgba(255, 100, 0, 0.6),
        0 0 60px rgba(255, 100, 0, 0.2);
    line-height: 1;
}
.forge-subtitle {
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: #664400;
    letter-spacing: 4px;
    margin-top: 4px;
    text-transform: uppercase;
}
.forge-badge {
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: #ff6600;
    border: 1px solid #331a00;
    padding: 6px 14px;
    letter-spacing: 2px;
    background: rgba(255, 100, 0, 0.05);
}

/* ── TAB STYLING ── */
.stTabs [data-baseweb="tab-list"] {
    background: #0a0a0a !important;
    border-bottom: 1px solid #1a1a1a !important;
    padding: 0 40px !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #444 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 3px !important;
    text-transform: uppercase !important;
    padding: 16px 24px !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
}
.stTabs [aria-selected="true"] {
    color: #ff6600 !important;
    border-bottom: 2px solid #ff6600 !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] {
    padding: 40px !important;
    background: #0a0a0a !important;
}

/* ── SECTION HEADERS ── */
.section-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 32px;
}
.section-num {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 48px;
    color: #1a1a1a;
    line-height: 1;
}
.section-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 32px;
    color: #e8d5b0;
    letter-spacing: 4px;
}
.section-line {
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, #2a1a0a, transparent);
}

/* ── INPUT STYLING ── */
.stTextArea textarea, .stTextInput input {
    background: #0f0f0f !important;
    border: 1px solid #2a1a0a !important;
    border-radius: 0 !important;
    color: #e8d5b0 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 13px !important;
    padding: 16px !important;
    transition: border-color 0.2s !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: #ff6600 !important;
    box-shadow: 0 0 0 1px rgba(255, 100, 0, 0.2), inset 0 0 30px rgba(255, 100, 0, 0.02) !important;
}

.stTextArea label, .stTextInput label, .stSelectbox label {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 10px !important;
    letter-spacing: 3px !important;
    color: #664400 !important;
    text-transform: uppercase !important;
}

/* ── SELECT BOX ── */
.stSelectbox > div > div {
    background: #0f0f0f !important;
    border: 1px solid #2a1a0a !important;
    border-radius: 0 !important;
    color: #e8d5b0 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 13px !important;
}

/* ── BUTTONS ── */
.stButton > button {
    background: linear-gradient(135deg, #cc4400, #ff6600) !important;
    color: #000 !important;
    border: none !important;
    border-radius: 0 !important;
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 20px !important;
    letter-spacing: 4px !important;
    padding: 14px 48px !important;
    cursor: pointer !important;
    position: relative !important;
    overflow: hidden !important;
    transition: all 0.2s !important;
    text-transform: uppercase !important;
    clip-path: polygon(8px 0%, 100% 0%, calc(100% - 8px) 100%, 0% 100%) !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #ff6600, #ffaa00) !important;
    box-shadow: 0 0 30px rgba(255, 100, 0, 0.4) !important;
    transform: translateY(-1px) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
}

/* ── LOGOUT BUTTON (sidebar) ── */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: 1px solid #2a1a0a !important;
    color: #664400 !important;
    font-size: 11px !important;
    padding: 8px 20px !important;
    letter-spacing: 2px !important;
    clip-path: none !important;
    margin: 10px 20px !important;
    width: calc(100% - 40px) !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    border-color: #ff6600 !important;
    color: #ff6600 !important;
    box-shadow: none !important;
    background: rgba(255,100,0,0.05) !important;
}

/* ── OUTPUT CARD ── */
.blueprint-output {
    background: #0d0d0d;
    border: 1px solid #2a1a0a;
    border-left: 3px solid #ff6600;
    padding: 32px;
    margin-top: 24px;
    position: relative;
    font-family: 'Share Tech Mono', monospace;
    font-size: 13px;
    line-height: 1.8;
    color: #c8b890;
}
.blueprint-output::before {
    content: 'BLUEPRINT OUTPUT';
    position: absolute;
    top: -10px;
    left: 20px;
    background: #0a0a0a;
    padding: 0 10px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 9px;
    letter-spacing: 3px;
    color: #ff6600;
}

/* ── ALERTS ── */
.stAlert {
    background: #0f0a05 !important;
    border: 1px solid #2a1a0a !important;
    border-radius: 0 !important;
    color: #c8a060 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 12px !important;
}

/* ── SPINNER ── */
.stSpinner > div {
    border-top-color: #ff6600 !important;
}

/* ── MARKDOWN STYLING ── */
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    font-family: 'Bebas Neue', sans-serif !important;
    letter-spacing: 3px !important;
    color: #ff8833 !important;
}
.stMarkdown p, .stMarkdown li {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 13px !important;
    color: #c8b890 !important;
    line-height: 1.8 !important;
}
.stMarkdown strong {
    color: #ffaa00 !important;
}
.stMarkdown code {
    background: #1a1a1a !important;
    color: #ff8833 !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 0 !important;
    padding: 2px 6px !important;
    font-family: 'Share Tech Mono', monospace !important;
}

/* ── LOGIN SCREEN ── */
.login-wrap {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    background: 
        radial-gradient(ellipse at center, rgba(255,80,0,0.05) 0%, transparent 70%),
        #0a0a0a;
}
.login-logo {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 100px;
    color: #ff6600;
    letter-spacing: 16px;
    text-shadow: 
        0 0 60px rgba(255,100,0,0.5),
        0 0 120px rgba(255,100,0,0.2);
    line-height: 1;
    text-align: center;
}
.login-tagline {
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: #664400;
    letter-spacing: 6px;
    text-align: center;
    margin-top: 8px;
    margin-bottom: 60px;
}
.login-box {
    width: 420px;
    border: 1px solid #2a1a0a;
    background: #0d0d0d;
    padding: 40px;
    position: relative;
}
.login-box::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #ff6600, transparent);
}
.login-box-title {
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    letter-spacing: 4px;
    color: #664400;
    text-transform: uppercase;
    margin-bottom: 24px;
}

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #2a1a0a; }
::-webkit-scrollbar-thumb:hover { background: #ff6600; }

/* ── DIVIDER ── */
hr {
    border-color: #1a1a1a !important;
}
</style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# ── LOGIN SCREEN ─────────────────────────────────────────────────────────────
def login():
    st.markdown("""
    <div class="login-wrap">
        <div class="login-logo">THE<br>BUILDER</div>
        <div class="login-tagline">⚙ &nbsp; AI-POWERED ENGINEERING FORGE &nbsp; ⚙</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown('<div class="login-box-title">// GARAGE ACCESS REQUIRED</div>', unsafe_allow_html=True)
        key_input = st.text_input("MASTER KEY", type="password", placeholder="Enter access key...")

        if st.button("⚡  IGNITE THE FORGE"):
            if MASTER_KEY and key_input == MASTER_KEY:
                st.session_state.authenticated = True
                st.rerun()
            else:
                try:
                    headers = {"x-internal-key": INTERNAL_API_KEY}
                    response = httpx.post(
                        f"{AUTH_SERVICE_URL}/verify-license",
                        json={"license_key": key_input},
                        headers=headers,
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.error("⛔  ACCESS DENIED — KEY NOT RECOGNIZED")
                except Exception as e:
                    st.error(f"⛔  AUTH SERVICE OFFLINE: {e}")

# ── MAIN DASHBOARD ────────────────────────────────────────────────────────────
def main_dashboard():

    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-header">
            <div class="sidebar-title">ANTHONY'S<br>GARAGE</div>
            <div class="sidebar-subtitle">Builder Command Center</div>
            <div class="sys-status"><span class="status-dot"></span>ALL SYSTEMS OPERATIONAL</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        st.markdown("""
        <div style='padding: 10px 20px; font-family: Share Tech Mono, monospace; font-size: 9px; 
                    letter-spacing: 2px; color: #333; text-transform: uppercase; border-bottom: 1px solid #111;'>
            ACTIVE SERVICES
        </div>
        """, unsafe_allow_html=True)

        services = [("⚙", "FORGE ENGINE", "ONLINE"), ("🛡", "AUTH GUARD", "ONLINE"), ("🗄", "LOGBOOK DB", "ONLINE")]
        for icon, name, status in services:
            color = "#00ff88"
            st.markdown(f"""
            <div style='padding: 10px 20px; font-family: Share Tech Mono, monospace; font-size: 10px;
                        letter-spacing: 1px; color: #555; display: flex; justify-content: space-between;'>
                <span>{icon} {name}</span>
                <span style='color: {color}'>{status}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button("⏻  LOCK GARAGE"):
            st.session_state.authenticated = False
            st.rerun()

    # Top Header
    st.markdown("""
    <div class="forge-header">
        <div>
            <div class="forge-title">THE FORGE</div>
            <div class="forge-subtitle">Round Table AI Engineering System · v2.0</div>
        </div>
        <div class="forge-badge">
            🔥 GEMINI · GROK · CLAUDE · ONLINE
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["⚡  NEW BUILD", "📜  BLUEPRINT HISTORY"])

    # ── TAB 1: NEW BUILD ──
    with tab1:
        st.markdown("""
        <div class="section-header">
            <div class="section-num">01</div>
            <div class="section-title">LOAD THE WORKBENCH</div>
            <div class="section-line"></div>
        </div>
        """, unsafe_allow_html=True)

        junk_input = st.text_area(
            "PARTS ON THE WORKBENCH",
            placeholder="Example: GE Aestiva 5 Anesthesia Machine, hydraulic rams, titanium plate, servo motors...",
            height=160
        )

        st.markdown("""
        <div class="section-header" style="margin-top: 32px;">
            <div class="section-num">02</div>
            <div class="section-title">SELECT BUILD TYPE</div>
            <div class="section-line"></div>
        </div>
        """, unsafe_allow_html=True)

        project_type = st.selectbox(
            "BUILD CLASSIFICATION",
            ["Combat Robot", "Shop Tool", "Hydraulic Lift", "Custom Vehicle Mod", "Industrial Machine", "Defense System"]
        )

        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

        if st.button("🔥  FORGE THE BLUEPRINT"):
            if not junk_input:
                st.warning("⚠  PARTS LIST REQUIRED — Load the workbench first.")
            else:
                with st.spinner("The Round Table is forging your blueprint..."):
                    try:
                        headers = {"x-internal-key": INTERNAL_API_KEY}
                        ai_response = httpx.post(
                            f"{AI_SERVICE_URL}/generate",
                            json={"junk_desc": junk_input, "project_type": project_type},
                            headers=headers,
                            timeout=100.0
                        )
                        if ai_response.status_code == 200:
                            st.markdown("""
                            <div style='font-family: Share Tech Mono, monospace; font-size: 9px; 
                                        letter-spacing: 3px; color: #ff6600; margin-bottom: 16px;
                                        border-bottom: 1px solid #1a1a1a; padding-bottom: 12px;'>
                                ⚙ BLUEPRINT FORGED — ROUND TABLE CONSENSUS REACHED
                            </div>
                            """, unsafe_allow_html=True)
                            st.markdown(ai_response.json()["content"])
                        else:
                            st.error(f"⛔  FORGE ERROR: {ai_response.status_code}")
                    except Exception as e:
                        st.error(f"⛔  AI ENGINE OFFLINE: {e}")

    # ── TAB 2: HISTORY ──
    with tab2:
        st.markdown("""
        <div class="section-header">
            <div class="section-num">02</div>
            <div class="section-title">PREVIOUS BLUEPRINTS</div>
            <div class="section-line"></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style='border: 1px solid #1a1a0a; border-left: 3px solid #664400; padding: 24px 32px;
                    font-family: Share Tech Mono, monospace; font-size: 11px; color: #664400;
                    letter-spacing: 1px; line-height: 2;'>
            <div style='font-size: 9px; letter-spacing: 3px; margin-bottom: 8px; color: #333;'>
                LOGBOOK STATUS
            </div>
            DATABASE SYNC IN PROGRESS...<br>
            BUILD HISTORY WILL APPEAR HERE ONCE CONNECTED.<br>
            <span style='color: #ff6600'>ALL BUILDS ARE BEING RECORDED TO POSTGRESQL.</span>
        </div>
        """, unsafe_allow_html=True)

# ── ROUTING ──────────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    login()
else:
    main_dashboard()
