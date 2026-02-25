"""
app.py — The Builder UI
========================
AoC3P0 Systems · AI-Powered Engineering Forge
Full dashboard connecting all microservices.
"""

import streamlit as st
import streamlit.components.v1 as components
import os
import html as html_lib
import secrets
import httpx
from dotenv import load_dotenv

load_dotenv()

# ── HTML Renderer ─────────────────────────────────────────────────────────────
# Streamlit versions handle unsafe_allow_html differently.
# This helper tries st.markdown first, falls back to components.html (iframe).
def st.html(content: str, height: int = 0):
    """Render raw HTML. Uses st.markdown with unsafe_allow_html.
    For large standalone blocks, set height > 0 to use components.html (iframe) instead."""
    if height > 0:
        # Iframe mode — fully isolated, works in any Streamlit version.
        # Inject dark background to match theme.
        wrapped = f"""
        <html><head>
        <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
        <style>body {{ margin:0; padding:0; background:#060606; overflow-x:hidden; }}</style>
        </head><body>{content}</body></html>"""
        components.html(wrapped, height=height, scrolling=False)
    else:
        st.html(content)

# ── URL Normalizer ────────────────────────────────────────────────────────────
# Render's RENDER_INTERNAL_HOSTNAME gives bare hostnames (e.g. "builder-auth").
# We need full URLs like "http://builder-auth:10000".
def normalize_url(raw: str, default: str) -> str:
    """Ensure a service URL has protocol and port."""
    if not raw:
        return default
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return f"http://{raw}:10000"

# ── Configuration ─────────────────────────────────────────────────────────────
AUTH_SERVICE_URL      = normalize_url(os.getenv("AUTH_SERVICE_URL", ""),      "http://builder-auth:10000")
AI_SERVICE_URL        = normalize_url(os.getenv("AI_SERVICE_URL", ""),        "http://builder-ai:10000")
BILLING_SERVICE_URL   = normalize_url(os.getenv("BILLING_SERVICE_URL", ""),   "http://builder-billing:10000")
ANALYTICS_SERVICE_URL = normalize_url(os.getenv("ANALYTICS_SERVICE_URL", ""), "http://builder-analytics:10000")
ADMIN_SERVICE_URL     = normalize_url(os.getenv("ADMIN_SERVICE_URL", ""),     "http://builder-admin:10000")
EXPORT_SERVICE_URL    = normalize_url(os.getenv("EXPORT_SERVICE_URL", ""),    "http://builder-export:10000")
WORKSHOP_SERVICE_URL  = normalize_url(os.getenv("WORKSHOP_SERVICE_URL", ""),  "http://builder-workshop:10000")
INTERNAL_API_KEY      = os.getenv("INTERNAL_API_KEY")
MASTER_KEY            = os.getenv("MASTER_KEY")
STRIPE_PAYMENT_URL    = os.getenv("STRIPE_PAYMENT_URL", "#")

st.set_page_config(
    page_title="THE BUILDER — AoC3P0 Forge",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ════════════════════════════════════════════════════════════
#   GLOBAL STYLES
# ════════════════════════════════════════════════════════════
st.html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&family=Orbitron:wght@400;700;900&display=swap');

:root {
    --orange:   #ff6600;
    --orange2:  #ffaa00;
    --dark:     #060606;
    --dark2:    #0d0d0d;
    --dark3:    #111111;
    --plate:    #0f0f0f;
    --border:   #2a1500;
    --border2:  #1a1a1a;
    --text:     #e8d5b0;
    --text2:    #b08060;
    --dim:      #664400;
    --green:    #00cc66;
    --red:      #ff4444;
    --blue:     #6699ff;
    --purple:   #cc88ff;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, .stApp { background-color: var(--dark) !important; color: var(--text) !important; font-family: 'Rajdhani', sans-serif !important; }
#MainMenu, footer, header, .stDeployButton { display: none !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--dark); }
::-webkit-scrollbar-thumb { background: var(--orange); }

@keyframes spin    { to { transform: rotate(360deg); } }
@keyframes pulse   { 0%,100% { box-shadow: 0 0 6px var(--green); opacity:1; } 50% { box-shadow: 0 0 18px var(--green); opacity:.6; } }
@keyframes flicker { 0%,100%{opacity:1;} 92%{opacity:1;} 93%{opacity:.8;} 94%{opacity:1;} }
@keyframes flow    { 0%{background-position:200% 0;} 100%{background-position:-200% 0;} }

/* ── SIDEBAR ── */
[data-testid="stSidebar"] { background: #080808 !important; border-right: 1px solid #1a1a1a !important; }
[data-testid="stSidebar"] > div { padding: 0 !important; }

.sb-head {
    background: linear-gradient(160deg,#120800,#080808);
    border-bottom: 1px solid var(--border);
    padding: 24px 18px 18px; position: relative; overflow: hidden;
}
.sb-head::before {
    content:''; position:absolute; top:0; left:0; right:0; height:2px;
    background: linear-gradient(90deg,transparent,var(--orange),var(--orange2),var(--orange),transparent);
}
.sb-head::after {
    content:'⚙'; position:absolute; right:-12px; top:-12px;
    font-size:80px; opacity:.04; animation:spin 25s linear infinite; pointer-events:none;
}
.sb-title { font-family:'Bebas Neue',sans-serif; font-size:24px; color:var(--orange); letter-spacing:3px; text-shadow:0 0 20px rgba(255,100,0,.4); line-height:1.1; }
.sb-sub   { font-family:'Share Tech Mono',monospace; font-size:8px; color:var(--dim); letter-spacing:2px; text-transform:uppercase; margin-top:4px; }
.status-row { display:flex; align-items:center; gap:6px; margin-top:12px; font-family:'Share Tech Mono',monospace; font-size:9px; color:var(--green); letter-spacing:1px; }
.pulse-dot  { width:7px; height:7px; background:var(--green); border-radius:50%; animation:pulse 2s infinite; }
.srv-row    { padding:8px 18px; font-family:'Share Tech Mono',monospace; font-size:9px; letter-spacing:1px; color:#444; display:flex; justify-content:space-between; border-bottom:1px solid #0f0f0f; }
.srv-on     { color:var(--green); }
.srv-off    { color:var(--red); }

.sb-section { padding:6px 18px 2px; font-family:'Share Tech Mono',monospace; font-size:8px; letter-spacing:2px; color:#222; text-transform:uppercase; border-bottom:1px solid #0f0f0f; margin-top:8px; }

/* ── BUTTONS ── */
.stButton > button {
    background: linear-gradient(135deg,#cc4400,var(--orange)) !important;
    color: #000 !important; border: none !important; border-radius: 0 !important;
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 18px !important; letter-spacing: 4px !important; padding: 12px 40px !important;
    clip-path: polygon(8px 0%,100% 0%,calc(100% - 8px) 100%,0% 100%) !important;
    transition: all .2s !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg,var(--orange),var(--orange2)) !important;
    box-shadow: 0 0 40px rgba(255,100,0,.5) !important; transform: translateY(-2px) !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important; border: 1px solid var(--border) !important;
    color: var(--dim) !important; font-size: 9px !important; padding: 7px 14px !important;
    clip-path: none !important; letter-spacing: 2px !important;
    margin: 4px 14px !important; width: calc(100% - 28px) !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    border-color: var(--orange) !important; color: var(--orange) !important;
    box-shadow: none !important; background: rgba(255,100,0,.04) !important;
}

/* ── INPUTS ── */
.stTextArea textarea, .stTextInput input {
    background: #0c0c0c !important; border: 1px solid var(--border) !important;
    border-radius: 0 !important; color: var(--text) !important;
    font-family: 'Share Tech Mono', monospace !important; font-size: 13px !important; padding: 14px !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: var(--orange) !important; box-shadow: 0 0 0 1px rgba(255,100,0,.15) !important;
}
.stTextArea label, .stTextInput label, .stSelectbox label, [data-testid="stWidgetLabel"] p {
    font-family: 'Share Tech Mono', monospace !important; font-size: 9px !important;
    letter-spacing: 3px !important; color: var(--dim) !important; text-transform: uppercase !important;
}
.stSelectbox > div > div {
    background: #0c0c0c !important; border: 1px solid var(--border) !important;
    border-radius: 0 !important; color: var(--text) !important;
    font-family: 'Share Tech Mono', monospace !important;
}

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] { background:var(--dark) !important; border-bottom:1px solid var(--border2) !important; padding:0 40px !important; gap:0 !important; }
.stTabs [data-baseweb="tab"] { background:transparent !important; color:#333 !important; font-family:'Share Tech Mono',monospace !important; font-size:9px !important; letter-spacing:3px !important; text-transform:uppercase !important; padding:14px 20px !important; border:none !important; border-bottom:2px solid transparent !important; }
.stTabs [aria-selected="true"] { color:var(--orange) !important; border-bottom:2px solid var(--orange) !important; }
.stTabs [data-baseweb="tab-panel"] { padding:36px !important; background:var(--dark) !important; }

/* ── ALERTS ── */
.stAlert { background:#0c0800 !important; border:1px solid var(--border) !important; border-radius:0 !important; color:#c8a060 !important; font-family:'Share Tech Mono',monospace !important; font-size:11px !important; }

/* ── MARKDOWN ── */
.stMarkdown h1,.stMarkdown h2,.stMarkdown h3 { font-family:'Bebas Neue',sans-serif !important; letter-spacing:3px !important; color:#ff8833 !important; }
.stMarkdown p,.stMarkdown li { font-family:'Share Tech Mono',monospace !important; font-size:13px !important; color:#c8b890 !important; line-height:1.8 !important; }
.stMarkdown strong { color:var(--orange2) !important; }
.stMarkdown code { background:#111 !important; color:#ff8833 !important; border:1px solid #222 !important; border-radius:0 !important; padding:2px 6px !important; font-family:'Share Tech Mono',monospace !important; }
.stMarkdown hr { border:none !important; height:1px !important; background:linear-gradient(90deg,transparent,var(--border),transparent) !important; margin:1rem 0 !important; }

/* ── SECTION HEADERS ── */
.sec-head { display:flex; align-items:center; gap:14px; margin-bottom:24px; }
.sec-num  { font-family:'Bebas Neue',sans-serif; font-size:44px; color:#1a1a1a; line-height:1; }
.sec-title{ font-family:'Bebas Neue',sans-serif; font-size:28px; color:var(--text); letter-spacing:4px; }
.sec-line { flex:1; height:1px; background:linear-gradient(90deg,var(--border),transparent); }

/* ── METRIC CARDS ── */
.metric-card {
    background: linear-gradient(135deg,#0f0f0f,#111);
    border: 1px solid var(--border2); border-top: 2px solid var(--orange);
    padding: 20px 24px; position: relative;
}
.metric-card::before { content:''; position:absolute; top:8px; left:10px; width:6px; height:6px; border-radius:50%; background:radial-gradient(circle at 35% 35%,#666,#222); }
.metric-card::after  { content:''; position:absolute; top:8px; right:10px; width:6px; height:6px; border-radius:50%; background:radial-gradient(circle at 35% 35%,#666,#222); }
.metric-val   { font-family:'Bebas Neue',sans-serif; font-size:42px; color:var(--orange); line-height:1; }
.metric-label { font-family:'Share Tech Mono',monospace; font-size:8px; letter-spacing:3px; color:#444; text-transform:uppercase; margin-top:4px; }

/* ── BUILD OUTPUT ── */
.output-header {
    font-family:'Share Tech Mono',monospace; font-size:8px; letter-spacing:3px;
    color:var(--orange); border-bottom:1px solid var(--border2); padding-bottom:10px; margin-bottom:16px;
}

/* ── HISTORY ROW ── */
.history-row {
    background:#0d0d0d; border:1px solid var(--border2); border-left:3px solid var(--border);
    padding:14px 20px; margin-bottom:4px; display:flex; justify-content:space-between; align-items:center;
    transition: border-left-color .2s;
}
.history-row:hover { border-left-color:var(--orange); }

/* ── ADMIN ROW ── */
.admin-row {
    background:#0d0d0d; border:1px solid var(--border2); border-left:2px solid #2a2a2a;
    padding:12px 18px; margin-bottom:3px; font-family:'Share Tech Mono',monospace; font-size:10px;
}
.admin-row:hover { border-left-color:var(--orange); }
</style>
""")

# ════════════════════════════════════════════════════════════
#   SESSION STATE
# ════════════════════════════════════════════════════════════
_DEFAULTS = {
    "authenticated":    False,
    "user_tier":        "guest",
    "user_name":        "",
    "user_email":       "",
    "is_admin":         False,
    "last_blueprint":   None,
    "last_build_id":    None,
    "last_project_type": None,
    "last_junk_input":  None,
}

for _key, _val in _DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

# ════════════════════════════════════════════════════════════
#   HELPERS
# ════════════════════════════════════════════════════════════
def esc(text) -> str:
    """HTML-escape user data to prevent XSS."""
    if text is None:
        return ""
    return html_lib.escape(str(text))

def api_headers():
    return {"x-internal-key": INTERNAL_API_KEY}

def sec_head(num: str, title: str):
    st.html(f"""
    <div class="sec-head">
        <div class="sec-num">{esc(num)}</div>
        <div class="sec-title">{esc(title)}</div>
        <div class="sec-line"></div>
    </div>""")

def metric_card(value, label):
    return f"""
    <div class="metric-card">
        <div class="metric-val">{esc(value)}</div>
        <div class="metric-label">{esc(label)}</div>
    </div>"""

@st.cache_data(ttl=30)
def check_service_health(url: str) -> tuple:
    """Check a service health endpoint with 30s cache to avoid blocking sidebar."""
    try:
        r = httpx.get(f"{url}/health", headers={"x-internal-key": INTERNAL_API_KEY}, timeout=3)
        if r.status_code == 200:
            return ("srv-on", "ONLINE")
        return ("srv-off", "ERROR")
    except Exception:
        return ("srv-off", "OFFLINE")

# ════════════════════════════════════════════════════════════
#   LANDING PAGE
# ════════════════════════════════════════════════════════════
def login():
    render_html("""
    <div style="min-height:100vh;
        background:
            repeating-linear-gradient(90deg,rgba(255,255,255,.010) 0,rgba(255,255,255,.010) 1px,transparent 1px,transparent 64px),
            repeating-linear-gradient(180deg,rgba(255,255,255,.010) 0,rgba(255,255,255,.010) 1px,transparent 1px,transparent 64px),
            linear-gradient(160deg,#100900 0%,#060606 45%,#080a04 100%);
        position:relative; overflow:hidden; display:flex; flex-direction:column; align-items:center; padding-bottom:60px;">

    <!-- TOP CHROME -->
    <div style="position:absolute;top:0;left:0;right:0;height:4px;
        background:linear-gradient(90deg,#111 0%,#555 8%,#999 15%,#ccc 20%,#ff6600 30%,#ffaa00 50%,#ff6600 70%,#ccc 80%,#999 85%,#555 92%,#111 100%);
        box-shadow:0 0 20px rgba(255,100,0,.5);"></div>

    <!-- BOTTOM CHROME -->
    <div style="position:absolute;bottom:0;left:0;right:0;height:3px;
        background:linear-gradient(90deg,transparent,#662200,#ff6600,#662200,transparent);"></div>

    <!-- LEFT PLATE -->
    <div style="position:absolute;left:0;top:0;bottom:0;width:24px;background:linear-gradient(90deg,#111,#1a1a1a,#0a0a0a);border-right:1px solid #2a2a2a;">
        <div style="position:absolute;top:28px;left:50%;transform:translateX(-50%);width:9px;height:9px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#888,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,.9);"></div>
        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:9px;height:9px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#888,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,.9);"></div>
        <div style="position:absolute;bottom:28px;left:50%;transform:translateX(-50%);width:9px;height:9px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#888,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,.9);"></div>
    </div>

    <!-- RIGHT PLATE -->
    <div style="position:absolute;right:0;top:0;bottom:0;width:24px;background:linear-gradient(270deg,#111,#1a1a1a,#0a0a0a);border-left:1px solid #2a2a2a;">
        <div style="position:absolute;top:28px;left:50%;transform:translateX(-50%);width:9px;height:9px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#888,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,.9);"></div>
        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:9px;height:9px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#888,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,.9);"></div>
        <div style="position:absolute;bottom:28px;left:50%;transform:translateX(-50%);width:9px;height:9px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#888,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,.9);"></div>
    </div>

    <!-- GEARS -->
    <div style="position:absolute;right:-160px;top:-160px;font-size:540px;opacity:.022;line-height:1;animation:spin 80s linear infinite;pointer-events:none;">⚙</div>
    <div style="position:absolute;left:-100px;bottom:-100px;font-size:360px;opacity:.018;line-height:1;animation:spin 55s linear infinite reverse;pointer-events:none;">⚙</div>

    <!-- AOC3P0 TAG BAR -->
    <div style="width:100%;background:linear-gradient(90deg,#0a0a0a,#111,#0a0a0a);border-bottom:1px solid #1a1a1a;
        padding:9px 48px;margin-top:4px;display:flex;justify-content:space-between;align-items:center;position:relative;z-index:10;">
        <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#2a2a2a;letter-spacing:3px;">▸ CLASSIFIED // ENGINEERING SYSTEM</div>
        <div style="font-family:'Orbitron',sans-serif;font-size:11px;font-weight:700;letter-spacing:4px;color:#664400;
            border:1px solid #2a1500;padding:5px 16px;background:rgba(255,100,0,.04);animation:flicker 8s infinite;">AoC3P0 SYSTEMS</div>
        <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#2a2a2a;letter-spacing:3px;">EST. 2024 // ALL RIGHTS RESERVED ◂</div>
    </div>

    <!-- HERO -->
    <div style="text-align:center;position:relative;z-index:10;padding:48px 60px 20px;max-width:1200px;width:100%;">

        <div style="font-family:'Share Tech Mono',monospace;font-size:9px;letter-spacing:8px;color:#442200;margin-bottom:18px;">── AI-POWERED · ROUND TABLE ENGINEERING ──</div>

        <div style="font-family:'Bebas Neue',sans-serif;font-size:clamp(72px,13vw,140px);line-height:.85;letter-spacing:14px;
            background:linear-gradient(180deg,#ffdd99 0%,#ff8800 35%,#cc3300 80%,#880000 100%);
            -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
            filter:drop-shadow(0 0 50px rgba(255,100,0,.35));animation:flicker 12s infinite;">THE<br>BUILDER</div>

        <!-- NAMEPLATE -->
        <div style="display:inline-block;margin-top:14px;
            background:linear-gradient(180deg,#2a2a2a 0%,#1a1a1a 40%,#222 60%,#1a1a1a 100%);
            border-top:2px solid #555;border-bottom:2px solid #0a0a0a;border-left:1px solid #333;border-right:1px solid #333;
            padding:10px 52px;position:relative;
            box-shadow:0 8px 32px rgba(0,0,0,.9),inset 0 1px 0 rgba(255,255,255,.07);">
            <div style="position:absolute;top:5px;left:7px;width:6px;height:6px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);"></div>
            <div style="position:absolute;top:5px;right:7px;width:6px;height:6px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);"></div>
            <div style="position:absolute;bottom:5px;left:7px;width:6px;height:6px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);"></div>
            <div style="position:absolute;bottom:5px;right:7px;width:6px;height:6px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);"></div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:18px;letter-spacing:9px;color:#888;">AI-POWERED ENGINEERING FORGE</div>
        </div>

        <div style="margin-top:32px;font-family:'Rajdhani',sans-serif;font-size:clamp(17px,2.5vw,26px);
            font-weight:600;color:#c89050;letter-spacing:1px;font-style:italic;">
            "Where AI logic meets heavy metal."</div>

        <!-- DIVIDER PLATE -->
        <div style="display:flex;align-items:center;gap:0;margin:32px auto;max-width:600px;">
            <div style="height:1px;flex:1;background:linear-gradient(90deg,transparent,#2a1500);"></div>
            <div style="background:linear-gradient(135deg,#1a1a1a,#222,#1a1a1a);border:1px solid #333;border-top:1px solid #444;
                padding:5px 18px;font-family:'Share Tech Mono',monospace;font-size:8px;color:#444;letter-spacing:4px;position:relative;">
                <span style="position:absolute;top:3px;left:4px;width:4px;height:4px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#666,#222);"></span>
                <span style="position:absolute;top:3px;right:4px;width:4px;height:4px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#666,#222);"></span>
                ROUND TABLE ACTIVE
            </div>
            <div style="height:1px;flex:1;background:linear-gradient(90deg,#2a1500,transparent);"></div>
        </div>

        <!-- MARKETING COPY -->
        <div style="margin:0 auto;max-width:900px;
            background:linear-gradient(160deg,#100900,#090806,#0c0900);
            border:1px solid #2a1500;border-top:2px solid #3a2000;
            padding:40px 52px;position:relative;
            box-shadow:0 24px 80px rgba(0,0,0,.9),inset 0 1px 0 rgba(255,150,0,.05);">
            <div style="position:absolute;top:9px;left:12px;width:8px;height:8px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,.9);"></div>
            <div style="position:absolute;top:9px;right:12px;width:8px;height:8px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,.9);"></div>
            <div style="position:absolute;bottom:9px;left:12px;width:8px;height:8px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,.9);"></div>
            <div style="position:absolute;bottom:9px;right:12px;width:8px;height:8px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,.9);"></div>
            <div style="position:absolute;top:50%;left:12px;transform:translateY(-50%);width:6px;height:6px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#666,#1a1a1a);"></div>
            <div style="position:absolute;top:50%;right:12px;transform:translateY(-50%);width:6px;height:6px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#666,#1a1a1a);"></div>
            <div style="position:absolute;left:0;top:15%;bottom:15%;width:3px;background:linear-gradient(180deg,transparent,#ff6600,transparent);"></div>
            <div style="position:absolute;right:0;top:15%;bottom:15%;width:3px;background:linear-gradient(180deg,transparent,#ff6600,transparent);"></div>
            <p style="font-family:'Rajdhani',sans-serif;font-size:clamp(15px,1.8vw,18px);font-weight:500;color:#b08050;line-height:2;text-align:center;">
                Why settle for <span style='color:#ff8833;font-weight:700;'>one AI</span> when you can have a
                <span style='color:#ff8833;font-weight:700;'>Board of Directors?</span><br>
                The Builder puts <span style='color:#ffaa00;font-weight:700;'>Gemini, Grok, and Claude</span>
                in the same room to tackle your toughest design challenges.<br><br>
                Whether we're repurposing <span style='color:#ff8833;'>medical X-ray tech for armor plating</span>
                or engineering <span style='color:#ff8833;'>off-road chassis for 500hp builds</span>,
                our <strong style='color:#ffcc00;'>'Round Table' logic</strong> ensures every bolt and wire is accounted for.<br><br>
                <span style='font-family:Share Tech Mono,monospace;font-size:12px;color:#ff6600;letter-spacing:2px;'>
                    It's not just a program — it's an automated engineering department.
                </span>
            </p>
        </div>

        <!-- AI BADGES -->
        <div style="display:flex;justify-content:center;gap:3px;margin-top:32px;flex-wrap:wrap;">
            <div style="background:linear-gradient(160deg,#131313,#1c1c1c,#111);border:1px solid #2a2a2a;border-top:1px solid #3a3a3a;
                padding:16px 28px;text-align:center;clip-path:polygon(12px 0%,100% 0%,calc(100% - 12px) 100%,0% 100%);min-width:170px;">
                <div style="font-size:20px;margin-bottom:4px;">🔵</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:4px;color:#6699ff;">GEMINI</div>
                <div style="font-family:'Share Tech Mono',monospace;font-size:7px;letter-spacing:2px;color:#333;margin-top:2px;">THE GENERAL CONTRACTOR</div>
            </div>
            <div style="background:linear-gradient(160deg,#131313,#1c1c1c,#111);border:1px solid #2a2a2a;border-top:1px solid #3a3a3a;
                padding:16px 28px;text-align:center;clip-path:polygon(12px 0%,100% 0%,calc(100% - 12px) 100%,0% 100%);min-width:170px;">
                <div style="font-size:20px;margin-bottom:4px;">⚡</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:4px;color:#ff6600;">GROK</div>
                <div style="font-family:'Share Tech Mono',monospace;font-size:7px;letter-spacing:2px;color:#333;margin-top:2px;">THE SHOP FOREMAN</div>
            </div>
            <div style="background:linear-gradient(160deg,#131313,#1c1c1c,#111);border:1px solid #2a2a2a;border-top:1px solid #3a3a3a;
                padding:16px 28px;text-align:center;clip-path:polygon(12px 0%,100% 0%,calc(100% - 12px) 100%,0% 100%);min-width:170px;">
                <div style="font-size:20px;margin-bottom:4px;">🤖</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:4px;color:#cc88ff;">CLAUDE</div>
                <div style="font-family:'Share Tech Mono',monospace;font-size:7px;letter-spacing:2px;color:#333;margin-top:2px;">THE PRECISION ENGINEER</div>
            </div>
        </div>

        <!-- SPEC STRIP -->
        <div style="display:flex;justify-content:center;gap:28px;margin-top:36px;flex-wrap:wrap;
            font-family:'Share Tech Mono',monospace;font-size:8px;letter-spacing:3px;color:#2a2a2a;text-transform:uppercase;">
            <span>⚙ TRIPLE REDUNDANT AI</span><span>//</span>
            <span>🛡 ENCRYPTED ACCESS</span><span>//</span>
            <span>🗄 POSTGRESQL LOGBOOK</span><span>//</span>
            <span>🔩 INDUSTRIAL GRADE</span>
        </div>

    </div>
    </div>
    """)

    # ── LOGIN BOX ──
    st.html("<div style='height:4px;background:#060606'></div>")
    col1, col2, col3 = st.columns([1, 1.0, 1])
    with col2:
        st.html("""
        <div style="border:1px solid #2a1500;border-top:3px solid #ff6600;
            background:linear-gradient(160deg,#0f0900,#090909);padding:28px 28px 8px;position:relative;
            box-shadow:0 20px 60px rgba(0,0,0,.95);">
            <div style='position:absolute;top:7px;left:9px;width:6px;height:6px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);'></div>
            <div style='position:absolute;top:7px;right:9px;width:6px;height:6px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);'></div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:8px;letter-spacing:4px;color:#664400;text-transform:uppercase;margin-bottom:18px;">
                // GARAGE ACCESS REQUIRED
            </div>
        </div>""")

        key_input = st.text_input("MASTER KEY", type="password", placeholder="Enter access key...")

        if st.button("⚡  IGNITE THE FORGE"):
            if not key_input:
                st.error("⛔  KEY REQUIRED")
            elif MASTER_KEY and secrets.compare_digest(key_input, MASTER_KEY):
                st.session_state.authenticated = True
                st.session_state.is_admin      = True
                st.session_state.user_name     = "Anthony"
                st.session_state.user_tier     = "master"
                st.session_state.user_email    = "admin"
                st.rerun()
            else:
                try:
                    resp = httpx.post(
                        f"{AUTH_SERVICE_URL}/verify-license",
                        json={"license_key": key_input},
                        headers=api_headers(), timeout=10.0
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state.authenticated = True
                        st.session_state.is_admin      = False
                        st.session_state.user_tier     = data.get("tier", "pro")
                        st.session_state.user_name     = data.get("name", "Builder")
                        st.session_state.user_email    = data.get("email", "")
                        st.rerun()
                    else:
                        st.error("⛔  ACCESS DENIED — KEY NOT RECOGNIZED")
                except Exception as e:
                    st.error(f"⛔  AUTH SERVICE OFFLINE: {e}")

        st.html("""
        <div style="text-align:center;padding:12px 0 4px;font-family:'Share Tech Mono',monospace;font-size:8px;color:#2a1500;letter-spacing:2px;">
            NO LICENSE? CONTACT AoC3P0 SYSTEMS TO ACQUIRE ACCESS
        </div>""")

    # Purchase link
    if STRIPE_PAYMENT_URL and STRIPE_PAYMENT_URL != "#":
        st.html("<div style='height:8px'></div>")
        col1, col2, col3 = st.columns([1, 1.0, 1])
        with col2:
            st.html(f"""
            <a href="{STRIPE_PAYMENT_URL}" target="_blank" style="display:block;background:linear-gradient(135deg,#8B1A00,#cc4400,#ff6600);
                color:#000;font-family:'Bebas Neue',sans-serif;font-size:18px;letter-spacing:4px;
                text-align:center;padding:14px;text-decoration:none;border:1px solid #ff8800;
                box-shadow:0 0 30px rgba(255,100,0,.3);margin-top:4px;">
                🔥 GET ACCESS — BUY A LICENSE
            </a>""")


# ════════════════════════════════════════════════════════════
#   SIDEBAR (authenticated)
# ════════════════════════════════════════════════════════════
def render_sidebar():
    with st.sidebar:
        name  = esc(st.session_state.user_name)
        tier  = esc(st.session_state.user_tier.upper())
        admin = st.session_state.is_admin

        st.html(f"""
        <div class="sb-head">
            <div class="sb-title">ANTHONY'S<br>GARAGE</div>
            <div class="sb-sub">AoC3P0 Builder · {tier}</div>
            <div class="status-row"><div class="pulse-dot"></div>ALL SYSTEMS OPERATIONAL</div>
        </div>""")

        # Service status — cached (30s) so sidebar doesn't block on every rerun
        st.html("<div class='sb-section'>ACTIVE SERVICES</div>")
        services = [
            ("⚙", "FORGE ENGINE",   AI_SERVICE_URL),
            ("🛡", "AUTH GUARD",     AUTH_SERVICE_URL),
            ("💳", "BILLING",        BILLING_SERVICE_URL),
            ("📊", "ANALYTICS",      ANALYTICS_SERVICE_URL),
            ("🔩", "WORKSHOP",       WORKSHOP_SERVICE_URL),
            ("🗄", "DATABASE",       None),
        ]
        for icon, label, url in services:
            if url:
                status, tag = check_service_health(url)
            else:
                status, tag = "srv-on", "ONLINE"
            st.html(f"""
            <div class="srv-row">
                <span>{icon} {label}</span>
                <span class="{status}">{tag}</span>
            </div>""")

        st.html("<div style='height:12px'></div>")

        if admin:
            st.html("<div class='sb-section'>ADMIN</div>")
            st.html(f"""
            <div style="padding:10px 18px;font-family:'Share Tech Mono',monospace;font-size:9px;color:#444;">
                👤 {name} &nbsp;·&nbsp; <span style='color:#ff6600;'>MASTER ACCESS</span>
            </div>""")

        st.html("<div style='height:8px'></div>")
        if st.button("⏻  LOCK GARAGE"):
            # Reset ALL session state to correct default types
            for key, val in _DEFAULTS.items():
                st.session_state[key] = val
            st.rerun()


# ════════════════════════════════════════════════════════════
#   DASHBOARD HEADER
# ════════════════════════════════════════════════════════════
def render_header():
    tier = st.session_state.user_tier.upper()
    st.html(f"""
    <div style="background:linear-gradient(90deg,#0a0500,#060606,#050a00);
        border-bottom:1px solid #151515;padding:18px 40px;
        display:flex;align-items:center;justify-content:space-between;position:relative;overflow:hidden;">
        <div style="position:absolute;bottom:0;left:0;right:0;height:1px;
            background:linear-gradient(90deg,transparent,#ff6600,#ffaa00,#ff6600,transparent);"></div>
        <div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:44px;letter-spacing:8px;
                color:#ff6600;text-shadow:0 0 30px rgba(255,100,0,.5);line-height:1;">THE FORGE</div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:8px;color:#442200;
                letter-spacing:4px;text-transform:uppercase;margin-top:2px;">
                AoC3P0 Systems · Round Table AI · v3.0
            </div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
            <div style="font-family:'Share Tech Mono',monospace;font-size:8px;color:#ff6600;
                border:1px solid #2a1500;padding:8px 14px;letter-spacing:2px;
                background:rgba(255,100,0,.04);text-align:center;">
                🔥 GEMINI · GROK · CLAUDE<br>
                <span style='color:#333;font-size:7px;'>ROUND TABLE ONLINE</span>
            </div>
            <div style="font-family:'Orbitron',sans-serif;font-size:9px;font-weight:700;
                border:1px solid #2a1500;padding:8px 14px;letter-spacing:2px;
                color:#664400;background:rgba(255,100,0,.02);">
                {tier}<br><span style='font-size:7px;color:#2a2a2a;'>LICENSE</span>
            </div>
        </div>
    </div>""")


# ════════════════════════════════════════════════════════════
#   TAB: NEW BUILD
# ════════════════════════════════════════════════════════════
def tab_new_build():
    sec_head("01", "LOAD THE WORKBENCH")

    # Check for prefill from X-Ray Scanner
    prefill = st.session_state.pop("prefill_workbench", "")
    if prefill:
        st.html("""
        <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#00cc66;
            border:1px solid rgba(0,200,100,.3);border-left:3px solid #00cc66;
            padding:10px 14px;margin-bottom:12px;">
            ✅ WORKBENCH LOADED FROM X-RAY SCAN — Parts list populated below. Hit FORGE to build.
        </div>""")

    junk_input = st.text_area(
        "PARTS ON THE WORKBENCH",
        value=prefill,
        placeholder="Example: GE Aestiva 5 Anesthesia Machine, hydraulic rams, titanium plate, servo motors, 3-phase motor...\n\n💡 TIP: Use the X-RAY SCANNER tab to upload a photo and auto-populate this field.",
        height=150
    )

    col1, col2 = st.columns(2)
    with col1:
        sec_head("02", "BUILD TYPE")
        project_type = st.selectbox("BUILD CLASSIFICATION", [
            "Combat Robot", "Shop Tool", "Hydraulic Lift",
            "Custom Vehicle Mod", "Industrial Machine",
            "Defense System", "Automation Rig", "Power System"
        ])
    with col2:
        sec_head("03", "DETAIL LEVEL")
        detail = st.selectbox("OUTPUT DETAIL", [
            "Full Blueprint (All 3 Tiers)",
            "Quick Concept (Novice Only)",
            "Master Build (Expert Only)"
        ])

    st.html("<div style='height:16px'></div>")

    if st.button("🔥  FORGE THE BLUEPRINT"):
        if not junk_input.strip():
            st.warning("⚠  PARTS LIST REQUIRED — Load the workbench first.")
        else:
            with st.spinner("The Round Table is deliberating... Grok is checking the torque specs... Claude is writing the code... Gemini is synthesizing..."):
                try:
                    resp = httpx.post(
                        f"{AI_SERVICE_URL}/generate",
                        json={
                            "junk_desc":    junk_input,
                            "project_type": project_type,
                            "detail_level": detail,
                            "user_email":   st.session_state.user_email
                        },
                        headers=api_headers(),
                        timeout=180.0
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state.last_blueprint    = data.get("content", "")
                        st.session_state.last_build_id     = data.get("build_id")
                        st.session_state.last_project_type = project_type
                        st.session_state.last_junk_input   = junk_input
                        st.rerun()
                    else:
                        st.error(f"⛔  FORGE ERROR: {resp.status_code} — {resp.text[:200]}")
                except Exception as e:
                    st.error(f"⛔  AI ENGINE OFFLINE: {e}")

    # ── BLUEPRINT OUTPUT ──
    if st.session_state.last_blueprint:
        st.html(f"""
        <div class="output-header">
            ⚙ BLUEPRINT FORGED — ROUND TABLE CONSENSUS REACHED
            &nbsp;·&nbsp; BUILD #{st.session_state.last_build_id or '—'}
        </div>""")

        st.markdown(st.session_state.last_blueprint)

        # ── EXPORT BUTTONS ──
        # Use stored session values so exports always match the blueprint
        export_type  = st.session_state.last_project_type or project_type
        export_parts = st.session_state.last_junk_input or junk_input

        st.html("<div style='height:20px'></div>")
        st.html("""
        <div style="font-family:'Share Tech Mono',monospace;font-size:8px;letter-spacing:3px;color:#442200;margin-bottom:12px;">
            ── EXPORT OPTIONS ──
        </div>""")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📄  EXPORT PDF"):
                try:
                    r = httpx.post(
                        f"{EXPORT_SERVICE_URL}/export/pdf",
                        json={
                            "blueprint":    st.session_state.last_blueprint,
                            "project_type": export_type,
                            "junk_desc":    export_parts,
                            "build_id":     st.session_state.last_build_id or 0
                        },
                        headers=api_headers(), timeout=30.0
                    )
                    if r.status_code == 200:
                        st.download_button(
                            "⬇ DOWNLOAD PDF",
                            data=r.content,
                            file_name=f"blueprint_{st.session_state.last_build_id}.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("PDF export failed")
                except Exception as e:
                    st.error(f"Export offline: {e}")

        with col2:
            if st.button("📝  EXPORT TEXT"):
                try:
                    r = httpx.post(
                        f"{EXPORT_SERVICE_URL}/export/text",
                        json={
                            "blueprint":    st.session_state.last_blueprint,
                            "project_type": export_type,
                            "junk_desc":    export_parts,
                            "build_id":     st.session_state.last_build_id or 0
                        },
                        headers=api_headers(), timeout=15.0
                    )
                    if r.status_code == 200:
                        st.download_button(
                            "⬇ DOWNLOAD TXT",
                            data=r.content,
                            file_name=f"blueprint_{st.session_state.last_build_id}.txt",
                            mime="text/plain"
                        )
                    else:
                        st.error("Text export failed")
                except Exception as e:
                    st.error(f"Export offline: {e}")

        with col3:
            if st.button("🔄  NEW BUILD"):
                st.session_state.last_blueprint    = None
                st.session_state.last_build_id     = None
                st.session_state.last_project_type = None
                st.session_state.last_junk_input   = None
                st.rerun()

        # ── SEND TO WORKSHOP ──
        st.html("<div style='height:16px'></div>")
        if st.button("🔩  SEND TO WORKSHOP — Track This Build"):
            with st.spinner("Creating workshop project with AI parts analysis..."):
                try:
                    r = httpx.post(
                        f"{WORKSHOP_SERVICE_URL}/projects/create",
                        json={
                            "build_id":     st.session_state.last_build_id,
                            "user_email":   st.session_state.user_email,
                            "title":        f"{export_type} Build #{st.session_state.last_build_id or 0}",
                            "project_type": export_type,
                            "junk_desc":    export_parts,
                            "blueprint":    st.session_state.last_blueprint[:2000]
                        },
                        headers=api_headers(), timeout=60.0
                    )
                    if r.status_code == 200:
                        data = r.json()
                        st.success(
                            f"✅ Workshop Project #{data['project_id']} created! "
                            f"({data.get('parts_count', 0)} parts identified, "
                            f"{data.get('tasks_count', 0)} tasks generated, "
                            f"est. {data.get('est_hours', '?')}hrs)"
                        )
                    else:
                        st.error(f"Workshop error: {r.status_code}")
                except Exception as e:
                    st.error(f"Workshop offline: {e}")


# ════════════════════════════════════════════════════════════
#   TAB: HISTORY
# ════════════════════════════════════════════════════════════
def tab_history():
    sec_head("02", "BLUEPRINT HISTORY")

    try:
        resp = httpx.get(f"{AI_SERVICE_URL}/builds", headers=api_headers(), timeout=10.0)
        if resp.status_code == 200:
            builds = resp.json()

            if not builds:
                st.html("""
                <div style="border:1px solid #1a0a00;border-left:3px solid #442200;padding:20px 28px;
                    font-family:Share Tech Mono,monospace;font-size:10px;color:#442200;letter-spacing:1px;">
                    NO BUILDS YET — FIRE UP THE FORGE TO START YOUR LOGBOOK.
                </div>""")
            else:
                st.html(f"""
                <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#442200;
                    letter-spacing:2px;margin-bottom:16px;">
                    {len(builds)} BLUEPRINTS IN THE LOGBOOK
                </div>""")

                for b in builds:
                    created = esc(b.get("created", "")[:16].replace("T", " "))
                    parts   = esc(b['parts'][:80])
                    suffix  = '...' if len(b['parts']) > 80 else ''
                    st.html(f"""
                    <div class="history-row">
                        <div>
                            <span style="font-family:'Bebas Neue',sans-serif;font-size:18px;color:#ff6600;letter-spacing:2px;">
                                #{esc(b['id'])} &nbsp; {esc(b['type']).upper()}
                            </span><br>
                            <span style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#555;">
                                {parts}{suffix}
                            </span>
                        </div>
                        <div style="text-align:right;font-family:'Share Tech Mono',monospace;font-size:8px;color:#333;">
                            {created}<br>
                            <span style="color:#442200;">{esc(b.get('email','')[:24])}</span>
                        </div>
                    </div>""")
        else:
            st.error(f"Could not load history: {resp.status_code}")
    except Exception as e:
        st.html("""
        <div style="border:1px solid #1a0a00;border-left:3px solid #442200;padding:20px 28px;
            font-family:Share Tech Mono,monospace;font-size:10px;color:#442200;">
            LOGBOOK OFFLINE — DATABASE SYNC IN PROGRESS.<br>
            <span style='color:#ff6600;'>ALL BUILDS ARE BEING RECORDED TO POSTGRESQL.</span>
        </div>""")


# ════════════════════════════════════════════════════════════
#   TAB: ANALYTICS
# ════════════════════════════════════════════════════════════
def tab_analytics():
    sec_head("03", "FORGE ANALYTICS")

    try:
        resp = httpx.get(f"{ANALYTICS_SERVICE_URL}/stats/overview", headers=api_headers(), timeout=10.0)
        if resp.status_code == 200:
            stats = resp.json()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.html(metric_card(stats.get("total_builds", 0), "TOTAL BUILDS"))
            with col2:
                st.html(metric_card(stats.get("builds_today", 0), "BUILDS TODAY"))
            with col3:
                st.html(metric_card(stats.get("active_licenses", 0), "ACTIVE LICENSES"))
            with col4:
                st.html(metric_card(stats.get("builds_this_week", 0), "THIS WEEK"))

            st.html("<div style='height:24px'></div>")

            col1, col2 = st.columns(2)

            with col1:
                sec_head("", "BUILD TYPES")
                r2 = httpx.get(f"{ANALYTICS_SERVICE_URL}/stats/builds", headers=api_headers(), timeout=10.0)
                if r2.status_code == 200:
                    for item in r2.json().get("by_type", []):
                        st.html(f"""
                        <div class="admin-row">
                            <span style="color:#ff6600;">{esc(item['type'])}</span>
                            &nbsp;·&nbsp;
                            <span style="color:#888;">{esc(item['count'])} builds</span>
                        </div>""")

            with col2:
                sec_head("", "POPULAR PARTS")
                r3 = httpx.get(f"{ANALYTICS_SERVICE_URL}/stats/popular-parts", headers=api_headers(), timeout=10.0)
                if r3.status_code == 200:
                    for item in r3.json().get("popular_parts", [])[:8]:
                        st.html(f"""
                        <div class="admin-row">
                            <span style="color:#ff6600;">{esc(item['keyword']).upper()}</span>
                            &nbsp;·&nbsp;
                            <span style="color:#888;">{esc(item['count'])} uses</span>
                        </div>""")
        else:
            st.error("Analytics service unavailable")
    except Exception as e:
        st.info(f"Analytics offline: {e}")


# ════════════════════════════════════════════════════════════
#   TAB: X-RAY SCANNER
# ════════════════════════════════════════════════════════════
HAZARD_COLORS = {"none": "#00cc66", "low": "#00cc66", "medium": "#ffaa00",
                 "high": "#ff4444", "critical": "#ff0000", "unknown": "#666"}

def tab_scanner():
    sec_head("02", "X-RAY SCANNER")

    st.html("""
    <div style="font-family:'Share Tech Mono',monospace;font-size:10px;color:#555;
        border:1px solid #1a1a1a;border-left:3px solid #ff6600;padding:14px 20px;margin-bottom:20px;">
        📸 Upload a photo of any equipment, machine, or junk pile.<br>
        The AI will identify it, map the schematics, and break down every salvageable component.
    </div>""")

    # ── Upload Section ──
    col_upload, col_context = st.columns([1.2, 1])

    with col_upload:
        uploaded_file = st.file_uploader(
            "DROP EQUIPMENT PHOTO",
            type=["jpg", "jpeg", "png", "webp"],
            help="JPEG, PNG, or WebP. Max 20MB."
        )

        if uploaded_file:
            st.image(uploaded_file, caption=f"📸 {uploaded_file.name}", use_container_width=True)

    with col_context:
        scan_context = st.text_area(
            "ADDITIONAL CONTEXT (OPTIONAL)",
            placeholder="e.g. 'Found in a hospital basement, looks like a ventilator from the 90s, has a compressor on the side...'",
            height=120
        )
        st.html("""
        <div style="font-family:'Share Tech Mono',monospace;font-size:8px;color:#333;margin-top:8px;">
            Adding context helps the AI identify obscure equipment more accurately.
        </div>""")

    st.html("<div style='height:12px'></div>")

    if st.button("🔬  INITIATE X-RAY SCAN"):
        if not uploaded_file:
            st.warning("⚠  Upload a photo first.")
        else:
            with st.spinner("X-RAY SCAN IN PROGRESS... Gemini is analyzing schematics, identifying components, assessing hazards..."):
                try:
                    import base64 as b64mod
                    img_bytes = uploaded_file.getvalue()
                    img_b64   = b64mod.b64encode(img_bytes).decode("utf-8")
                    mime      = uploaded_file.type or "image/jpeg"

                    resp = httpx.post(
                        f"{WORKSHOP_SERVICE_URL}/scan/base64",
                        json={
                            "image_base64": f"data:{mime};base64,{img_b64}",
                            "user_email":   st.session_state.user_email or "anonymous",
                            "context":      scan_context
                        },
                        headers=api_headers(),
                        timeout=120.0
                    )

                    if resp.status_code == 200:
                        st.session_state.last_scan = resp.json()
                        st.rerun()
                    else:
                        st.error(f"⛔ Scan failed: {resp.status_code} — {resp.text[:200]}")
                except Exception as e:
                    st.error(f"⛔ Scanner offline: {e}")

    # ── SCAN RESULTS ──
    scan = st.session_state.get("last_scan")
    if scan and scan.get("scan_result"):
        result  = scan["scan_result"]
        ident   = result.get("identification", {})
        schema  = result.get("schematics", {})
        specs   = result.get("specifications", {})
        comps   = result.get("components", [])
        hazards = result.get("hazards", {})
        salvage = result.get("salvage_assessment", {})
        builds  = result.get("build_potential", [])

        hazard_level = hazards.get("level", "unknown")
        hazard_color = HAZARD_COLORS.get(hazard_level, "#666")

        # ── IDENTIFICATION HEADER ──
        st.html(f"""
        <div style="background:linear-gradient(135deg,#0f0900,#0d0d0d);border:1px solid #2a1500;
            border-top:3px solid #ff6600;padding:28px 32px;margin:20px 0;position:relative;">
            <div style="position:absolute;top:10px;right:14px;font-family:'Share Tech Mono',monospace;
                font-size:8px;color:{hazard_color};border:1px solid {hazard_color};padding:4px 10px;
                letter-spacing:2px;">
                ⚠ HAZARD: {esc(hazard_level).upper()}
            </div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:42px;color:#ff6600;
                letter-spacing:4px;line-height:1;">
                {esc(ident.get('equipment_name', 'UNKNOWN EQUIPMENT'))}
            </div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:10px;color:#888;
                margin-top:6px;letter-spacing:2px;">
                {esc(ident.get('manufacturer', ''))} &nbsp;·&nbsp;
                MODEL: {esc(ident.get('model', 'N/A'))} &nbsp;·&nbsp;
                ERA: {esc(ident.get('year_range', 'N/A'))} &nbsp;·&nbsp;
                CLASS: {esc(ident.get('category', '').upper())}
            </div>
            <div style="font-family:'Rajdhani',sans-serif;font-size:14px;color:#b08050;margin-top:10px;">
                {esc(ident.get('original_purpose', ''))}
            </div>
            <div style="display:flex;gap:20px;margin-top:14px;font-family:'Share Tech Mono',monospace;font-size:9px;">
                <span style="color:#ff6600;">⚙ {len(comps)} COMPONENTS</span>
                <span style="color:#00cc66;">${salvage.get('total_estimated_value', 0):,.0f} EST. SALVAGE</span>
                <span style="color:#ffaa00;">🔧 {salvage.get('teardown_hours', 0):.0f}hrs TEARDOWN</span>
                <span style="color:#cc88ff;">DIFFICULTY: {'★' * salvage.get('teardown_difficulty', 5)}{'☆' * (10 - salvage.get('teardown_difficulty', 5))}</span>
            </div>
        </div>""")

        # ── METRICS ROW ──
        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            st.html(metric_card(len(comps), "COMPONENTS FOUND"))
        with mc2:
            st.html(metric_card(f"${salvage.get('total_estimated_value', 0):,.0f}", "SALVAGE VALUE"))
        with mc3:
            st.html(metric_card(f"{salvage.get('teardown_hours', 0):.0f}h", "TEARDOWN TIME"))
        with mc4:
            st.html(metric_card(hazard_level.upper(), "HAZARD LEVEL"))

        st.html("<div style='height:20px'></div>")

        # ── SCHEMATICS ──
        if schema:
            sec_head("", "INTERNAL SCHEMATICS")
            schema_fields = [
                ("system_overview",    "🏗 SYSTEM OVERVIEW"),
                ("power_system",       "⚡ POWER SYSTEM"),
                ("control_system",     "🖥 CONTROL SYSTEM"),
                ("mechanical_systems", "⚙ MECHANICAL SYSTEMS"),
                ("fluid_systems",      "💧 FLUID SYSTEMS"),
                ("signal_chain",       "📡 SIGNAL CHAIN"),
            ]
            for key, label in schema_fields:
                val = schema.get(key)
                if val:
                    st.html(f"""
                    <div style="background:#0c0c0c;border:1px solid #1a1a1a;border-left:3px solid #ff6600;
                        padding:12px 18px;margin-bottom:4px;">
                        <div style="font-family:'Share Tech Mono',monospace;font-size:8px;letter-spacing:2px;
                            color:#ff6600;margin-bottom:6px;">{label}</div>
                        <div style="font-family:'Rajdhani',sans-serif;font-size:13px;color:#c8b890;line-height:1.7;">
                            {esc(val)}
                        </div>
                    </div>""")

            # ASCII electrical diagram
            elec = schema.get("electrical_diagram")
            if elec:
                st.html(f"""
                <div style="background:#0a0a0a;border:1px solid #2a1500;padding:18px 22px;margin:10px 0;">
                    <div style="font-family:'Share Tech Mono',monospace;font-size:8px;color:#ff6600;
                        letter-spacing:2px;margin-bottom:8px;">⚡ ELECTRICAL FLOW DIAGRAM</div>
                    <pre style="font-family:'Share Tech Mono',monospace;font-size:11px;color:#00cc66;
                        margin:0;white-space:pre-wrap;line-height:1.5;">{esc(elec)}</pre>
                </div>""")

        st.html("<div style='height:16px'></div>")

        # ── SPECS + HAZARDS side by side ──
        col_specs, col_hazards = st.columns(2)

        with col_specs:
            sec_head("", "SPECIFICATIONS")
            if specs:
                for key, val in specs.items():
                    if val and key != "other_specs":
                        st.html(f"""
                        <div class="admin-row">
                            <span style="color:#ff6600;">{esc(key.replace('_', ' ').upper())}</span>
                            &nbsp;·&nbsp; <span style="color:#c8b890;">{esc(val)}</span>
                        </div>""")
                for extra in specs.get("other_specs", []):
                    if extra:
                        st.html(f"""
                        <div class="admin-row">
                            <span style="color:#888;">{esc(extra)}</span>
                        </div>""")

        with col_hazards:
            sec_head("", "HAZARD ASSESSMENT")
            if hazards:
                for w in hazards.get("warnings", []):
                    st.html(f"""
                    <div style="background:rgba(255,68,68,.08);border:1px solid rgba(255,68,68,.3);
                        border-left:3px solid {hazard_color};padding:10px 14px;margin-bottom:4px;
                        font-family:'Share Tech Mono',monospace;font-size:10px;color:#ff8888;">
                        ⚠ {esc(w)}
                    </div>""")

                ppe = hazards.get("required_ppe", [])
                if ppe:
                    ppe_text = " · ".join(esc(p) for p in ppe)
                    st.html(f"""
                    <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#ffaa00;
                        margin-top:8px;letter-spacing:1px;">
                        🛡 REQUIRED PPE: {ppe_text}
                    </div>""")

                lockout = hazards.get("lockout_tagout")
                if lockout:
                    st.html(f"""
                    <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#ff4444;
                        margin-top:6px;">🔒 LOCKOUT/TAGOUT: {esc(lockout)}</div>""")

        st.html("<div style='height:16px'></div>")

        # ── COMPONENT TEARDOWN TABLE ──
        sec_head("", f"COMPONENT TEARDOWN — {len(comps)} PARTS")

        if comps:
            # Group by category
            cats = {}
            for c in comps:
                cat = c.get("category", "other") if isinstance(c, dict) else "other"
                cats.setdefault(cat, []).append(c)

            for cat_name, cat_parts in sorted(cats.items()):
                st.html(f"""
                <div style="font-family:'Share Tech Mono',monospace;font-size:8px;letter-spacing:3px;
                    color:#442200;margin:12px 0 6px;border-bottom:1px solid #1a1a1a;padding-bottom:4px;">
                    ── {esc(cat_name).upper()} ({len(cat_parts)}) ──
                </div>""")

                for comp in cat_parts:
                    if not isinstance(comp, dict):
                        continue
                    reuse = comp.get("reuse_potential", "medium")
                    reuse_color = {"high": "#00cc66", "medium": "#ffaa00", "low": "#ff4444"}.get(reuse, "#888")
                    val = comp.get("salvage_value", 0)
                    qty = comp.get("quantity", 1)

                    st.html(f"""
                    <div style="background:#0c0c0c;border:1px solid #1a1a1a;border-left:3px solid {reuse_color};
                        padding:10px 16px;margin-bottom:3px;display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <span style="font-family:'Share Tech Mono',monospace;font-size:11px;color:#ff6600;">
                                {esc(comp.get('name', '?'))}</span>
                            {'<span style="color:#555;font-size:9px;"> ×' + str(qty) + '</span>' if qty > 1 else ''}
                            <br>
                            <span style="font-family:'Share Tech Mono',monospace;font-size:8px;color:#555;">
                                {esc(comp.get('location', ''))}
                                {(' — ' + esc(comp.get('specifications', ''))) if comp.get('specifications') else ''}
                            </span>
                            <br>
                            <span style="font-family:'Share Tech Mono',monospace;font-size:8px;color:#444;">
                                {esc(comp.get('condition_notes', ''))}
                            </span>
                        </div>
                        <div style="text-align:right;white-space:nowrap;">
                            <span style="font-family:'Bebas Neue',sans-serif;font-size:18px;color:#00cc66;">
                                ${val:,.0f}</span><br>
                            <span style="font-family:'Share Tech Mono',monospace;font-size:7px;color:{reuse_color};
                                letter-spacing:1px;">{esc(reuse).upper()} REUSE</span>
                        </div>
                    </div>""")

        # ── BUILD POTENTIAL ──
        if builds:
            st.html("<div style='height:16px'></div>")
            sec_head("", "BUILD POTENTIAL — What could this become?")
            for i, idea in enumerate(builds):
                st.html(f"""
                <div class="admin-row">
                    <span style="color:#ff6600;font-family:'Bebas Neue',sans-serif;font-size:16px;
                        letter-spacing:2px;">IDEA {i+1}</span>
                    &nbsp;·&nbsp;
                    <span style="color:#c8b890;">{esc(idea)}</span>
                </div>""")

        # ── ACTION BUTTONS ──
        st.html("<div style='height:20px'></div>")
        st.html("""
        <div style="font-family:'Share Tech Mono',monospace;font-size:8px;letter-spacing:3px;
            color:#442200;margin-bottom:12px;">── ACTIONS ──</div>""")

        acol1, acol2, acol3 = st.columns(3)

        with acol1:
            if st.button("📋  SEND TO WORKBENCH"):
                try:
                    r = httpx.post(
                        f"{WORKSHOP_SERVICE_URL}/scans/{scan['scan_id']}/to-workbench",
                        headers=api_headers(), timeout=10.0
                    )
                    if r.status_code == 200:
                        wb = r.json()
                        st.session_state["prefill_workbench"] = wb["workbench_text"]
                        st.success(f"✅ {wb['parts_count']} components loaded to workbench! Switch to NEW BUILD tab.")
                    else:
                        st.error("Could not generate workbench text")
                except Exception as e:
                    st.error(f"Error: {e}")

        with acol2:
            if st.button("🔩  SEND TO WORKSHOP"):
                try:
                    wb_resp = httpx.post(
                        f"{WORKSHOP_SERVICE_URL}/scans/{scan['scan_id']}/to-workbench",
                        headers=api_headers(), timeout=10.0
                    )
                    wb_text = wb_resp.json().get("workbench_text", "") if wb_resp.status_code == 200 else ident.get("equipment_name", "Scanned Equipment")

                    r = httpx.post(
                        f"{WORKSHOP_SERVICE_URL}/projects/create",
                        json={
                            "user_email":   st.session_state.user_email or "anonymous",
                            "title":        f"SCAN: {ident.get('equipment_name', 'Unknown')}",
                            "project_type": ident.get("category", "other").replace("_", " ").title(),
                            "junk_desc":    wb_text,
                        },
                        headers=api_headers(), timeout=60.0
                    )
                    if r.status_code == 200:
                        d = r.json()
                        st.success(f"✅ Workshop Project #{d['project_id']} created from scan!")
                    else:
                        st.error(f"Workshop error: {r.status_code}")
                except Exception as e:
                    st.error(f"Error: {e}")

        with acol3:
            if st.button("🔬  NEW SCAN"):
                st.session_state.last_scan = None
                st.rerun()

    # ── SCAN HISTORY ──
    st.html("<div style='height:24px'></div>")
    sec_head("", "SCAN HISTORY")

    try:
        resp = httpx.get(f"{WORKSHOP_SERVICE_URL}/scans",
                         headers=api_headers(), timeout=10.0)
        if resp.status_code == 200:
            scans = resp.json()
            if scans:
                for s in scans[:10]:
                    hz_color = HAZARD_COLORS.get(s.get("hazard_level", "unknown"), "#666")
                    st.html(f"""
                    <div class="history-row">
                        <div>
                            <span style="font-family:'Bebas Neue',sans-serif;font-size:16px;color:#ff6600;letter-spacing:2px;">
                                🔬 {esc(s['equipment_name'])}
                            </span><br>
                            <span style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#555;">
                                {esc(s.get('manufacturer', ''))} {esc(s.get('model', ''))} &nbsp;·&nbsp;
                                {s.get('parts_found', 0)} parts &nbsp;·&nbsp;
                                ${s.get('est_salvage', 0):,.0f} salvage &nbsp;·&nbsp;
                                <span style="color:{hz_color};">HAZARD: {esc(s.get('hazard_level', '?')).upper()}</span>
                            </span>
                        </div>
                        <div style="text-align:right;font-family:'Share Tech Mono',monospace;font-size:8px;color:#333;">
                            #{s['id']}<br>{esc(s.get('created_at', '')[:16])}
                        </div>
                    </div>""")
            else:
                st.html("""
                <div style="font-family:'Share Tech Mono',monospace;font-size:10px;color:#442200;">
                    No scans yet. Upload a photo to start.
                </div>""")
    except Exception:
        pass


# ════════════════════════════════════════════════════════════
#   TAB: WORKSHOP (The Shop Floor)
# ════════════════════════════════════════════════════════════
PHASE_ICONS = {"planning": "📐", "fabrication": "🔥", "assembly": "🔩",
               "electrical": "⚡", "testing": "🧪", "complete": "🏆"}
PART_STATUS_COLORS = {"needed": "#ff4444", "sourced": "#ffaa00",
                      "installed": "#00cc66", "missing": "#666"}

def tab_workshop():
    sec_head("04", "THE SHOP FLOOR")

    # Sub-navigation
    if "ws_view" not in st.session_state:
        st.session_state.ws_view = "list"
    if "ws_project_id" not in st.session_state:
        st.session_state.ws_project_id = None

    # ── PROJECT LIST VIEW ──
    if st.session_state.ws_view == "list":
        try:
            resp = httpx.get(
                f"{WORKSHOP_SERVICE_URL}/projects",
                headers=api_headers(), timeout=10.0
            )
            if resp.status_code == 200:
                projects = resp.json()

                # Workshop stats header
                try:
                    sr = httpx.get(f"{WORKSHOP_SERVICE_URL}/workshop/stats",
                                   headers=api_headers(), timeout=5.0)
                    if sr.status_code == 200:
                        ws = sr.json()
                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            st.html(metric_card(ws.get("active_projects", 0), "ACTIVE PROJECTS"))
                        with c2:
                            st.html(metric_card(ws.get("completed", 0), "COMPLETED"))
                        with c3:
                            st.html(metric_card(f"{ws.get('tasks_done', 0)}/{ws.get('tasks_total', 0)}", "TASKS DONE"))
                        with c4:
                            st.html(metric_card(f"${ws.get('total_est_cost', 0):,.0f}", "EST. TOTAL COST"))
                        st.html("<div style='height:20px'></div>")
                except Exception:
                    pass

                if not projects:
                    st.html("""
                    <div style="border:1px solid #1a0a00;border-left:3px solid #442200;padding:20px 28px;
                        font-family:Share Tech Mono,monospace;font-size:10px;color:#442200;letter-spacing:1px;">
                        NO ACTIVE PROJECTS — Forge a blueprint and click "Send to Workshop" to start tracking a build.
                    </div>""")
                else:
                    for p in projects:
                        phase = p["current_phase"]
                        icon  = PHASE_ICONS.get(phase, "⚙")
                        pct   = p["progress"]["percent"]

                        # Progress bar color
                        bar_color = "#ff6600" if pct < 100 else "#00cc66"
                        diff_stars = "★" * p["difficulty"] + "☆" * (10 - p["difficulty"])

                        st.html(f"""
                        <div style="background:#0d0d0d;border:1px solid #1a1a1a;border-left:3px solid {'#00cc66' if phase == 'complete' else '#ff6600'};
                            padding:18px 24px;margin-bottom:6px;position:relative;overflow:hidden;">
                            <div style="position:absolute;bottom:0;left:0;width:{pct}%;height:2px;background:{bar_color};transition:width .3s;"></div>
                            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                                <div>
                                    <span style="font-family:'Bebas Neue',sans-serif;font-size:22px;color:#ff6600;letter-spacing:2px;">
                                        {icon} {esc(p['title'])}
                                    </span><br>
                                    <span style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#555;">
                                        {esc(p['project_type']).upper()} &nbsp;·&nbsp;
                                        PHASE: {esc(phase).upper()} &nbsp;·&nbsp;
                                        {pct}% COMPLETE &nbsp;·&nbsp;
                                        {p['progress']['done_tasks']}/{p['progress']['total_tasks']} tasks
                                    </span><br>
                                    <span style="font-family:'Share Tech Mono',monospace;font-size:8px;color:#442200;">
                                        DIFFICULTY: <span style="color:#ff6600;">{diff_stars}</span> &nbsp;·&nbsp;
                                        EST: {p.get('est_hours', 0):.0f}hrs &nbsp;·&nbsp;
                                        ${p.get('est_cost', 0):,.0f} &nbsp;·&nbsp;
                                        PARTS: {p['progress']['installed_parts']}/{p['progress']['total_parts']} installed
                                    </span>
                                </div>
                                <div style="text-align:right;font-family:'Share Tech Mono',monospace;font-size:8px;color:#333;">
                                    #{p['id']}<br>{esc(p.get('created_at', '')[:10])}
                                </div>
                            </div>
                        </div>""")

                    # Project selector
                    st.html("<div style='height:12px'></div>")
                    project_options = {f"#{p['id']} — {p['title']}": p["id"] for p in projects}
                    selected = st.selectbox("SELECT PROJECT TO OPEN", list(project_options.keys()))
                    if st.button("🔍  OPEN PROJECT"):
                        st.session_state.ws_view = "detail"
                        st.session_state.ws_project_id = project_options[selected]
                        st.rerun()
            else:
                st.error(f"Workshop unavailable: {resp.status_code}")
        except Exception as e:
            st.html(f"""
            <div style="border:1px solid #1a0a00;border-left:3px solid #442200;padding:20px 28px;
                font-family:Share Tech Mono,monospace;font-size:10px;color:#442200;">
                WORKSHOP OFFLINE — Service starting up.<br>
                <span style='color:#ff6600;'>Send a blueprint to the workshop to begin.</span>
            </div>""")
        return

    # ── PROJECT DETAIL VIEW ──
    if st.session_state.ws_view == "detail" and st.session_state.ws_project_id:
        if st.button("← BACK TO ALL PROJECTS"):
            st.session_state.ws_view = "list"
            st.session_state.ws_project_id = None
            st.rerun()

        try:
            resp = httpx.get(
                f"{WORKSHOP_SERVICE_URL}/projects/{st.session_state.ws_project_id}",
                headers=api_headers(), timeout=10.0
            )
            if resp.status_code != 200:
                st.error(f"Could not load project: {resp.status_code}")
                return

            proj = resp.json()
        except Exception as e:
            st.error(f"Workshop offline: {e}")
            return

        # ── Project Header ──
        pct = proj["progress_percent"]
        st.html(f"""
        <div style="background:linear-gradient(135deg,#0f0900,#0d0d0d);border:1px solid #2a1500;
            border-top:3px solid #ff6600;padding:24px 28px;margin-bottom:20px;position:relative;overflow:hidden;">
            <div style="position:absolute;bottom:0;left:0;width:{pct}%;height:3px;
                background:linear-gradient(90deg,#ff6600,#ffaa00);transition:width .3s;"></div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:36px;color:#ff6600;letter-spacing:4px;line-height:1;">
                {esc(proj['title'])}
            </div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#555;margin-top:6px;letter-spacing:2px;">
                {esc(proj['project_type']).upper()} &nbsp;·&nbsp;
                BUILD #{proj.get('build_id') or '—'} &nbsp;·&nbsp;
                PROJECT #{proj['id']} &nbsp;·&nbsp;
                <span style='color:#ff6600;font-size:11px;'>{pct}% COMPLETE</span>
            </div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:8px;color:#442200;margin-top:4px;">
                DIFFICULTY: {'★' * proj['difficulty']}{'☆' * (10 - proj['difficulty'])} &nbsp;·&nbsp;
                EST: {proj.get('est_hours', 0):.0f} hours &nbsp;·&nbsp;
                ${proj.get('est_cost', 0):,.0f}
            </div>
        </div>""")

        # ── Phase Pipeline ──
        st.html("""
        <div style="font-family:'Share Tech Mono',monospace;font-size:8px;letter-spacing:3px;color:#442200;margin-bottom:12px;">
            ── BUILD PIPELINE ──
        </div>""")

        phase_cols = st.columns(len(proj["phases"]))
        for i, phase in enumerate(proj["phases"]):
            with phase_cols[i]:
                is_current = phase["is_current"]
                is_done    = (phase["done"] == phase["total"] and phase["total"] > 0) or \
                             (proj["phases"].index(phase) < [p["is_current"] for p in proj["phases"]].index(True) if True in [p["is_current"] for p in proj["phases"]] else 99)

                border_color = "#ff6600" if is_current else "#00cc66" if is_done else "#1a1a1a"
                bg = "rgba(255,100,0,.06)" if is_current else "rgba(0,200,100,.04)" if is_done else "#0d0d0d"

                st.html(f"""
                <div style="background:{bg};border:1px solid {border_color};
                    {'border-top:3px solid ' + border_color + ';' if is_current else ''}
                    padding:12px 10px;text-align:center;min-height:90px;">
                    <div style="font-size:18px;">{phase['icon']}</div>
                    <div style="font-family:'Share Tech Mono',monospace;font-size:7px;letter-spacing:1px;
                        color:{border_color};margin-top:4px;">
                        {esc(phase['name'])}
                    </div>
                    <div style="font-family:'Bebas Neue',sans-serif;font-size:16px;
                        color:{'#ff6600' if is_current else '#00cc66' if is_done else '#333'};">
                        {phase['done']}/{phase['total']}
                    </div>
                </div>""")

        st.html("<div style='height:16px'></div>")

        # ── Advance Phase Button ──
        current_phase = proj["current_phase"]
        if current_phase != "complete":
            current_phase_info = next((p for p in proj["phases"] if p["key"] == current_phase), None)
            if current_phase_info:
                gate_text = next((p["gate"] for p in [{"key": ph["key"], "gate": ph.get("gate")} for ph in proj["phases"]] if p["key"] == current_phase), "")

                safety_confirmed = st.checkbox(
                    f"⛑ SAFETY GATE — {gate_text or 'Confirm ready to advance'}",
                    key=f"safety_{proj['id']}"
                )
                if st.button(f"⏭  ADVANCE TO NEXT PHASE"):
                    if not safety_confirmed:
                        st.warning("⚠ You must confirm the safety gate before advancing.")
                    else:
                        try:
                            r = httpx.patch(
                                f"{WORKSHOP_SERVICE_URL}/projects/{proj['id']}/phase",
                                json={"safety_confirmed": True},
                                headers=api_headers(), timeout=10.0
                            )
                            if r.status_code == 200:
                                st.success(f"✅ Advanced to: {r.json()['current_phase'].upper()}")
                                st.rerun()
                            else:
                                st.error(f"Cannot advance: {r.json().get('detail', r.status_code)}")
                        except Exception as e:
                            st.error(f"Error: {e}")

        st.html("<div style='height:20px'></div>")

        # ── Two-column: Tasks + Parts ──
        col_left, col_right = st.columns([1.3, 1])

        with col_left:
            sec_head("", "TASKS — CURRENT PHASE")

            current_tasks = []
            for phase in proj["phases"]:
                if phase["key"] == current_phase:
                    current_tasks = phase["tasks"]
                    break

            if not current_tasks:
                st.html("<div style='font-family:Share Tech Mono,monospace;font-size:10px;color:#442200;'>No tasks for this phase.</div>")
            else:
                for task in current_tasks:
                    is_done = task["is_complete"]
                    is_safety = task.get("is_safety", False)

                    icon = "✅" if is_done else ("⛑" if is_safety else "⬜")
                    color = "#00cc66" if is_done else ("#ffaa00" if is_safety else "#888")
                    strike = "text-decoration:line-through;opacity:.5;" if is_done else ""

                    task_key = f"task_{proj['id']}_{task['id']}"
                    checked = st.checkbox(
                        f"{icon} {task['title']}",
                        value=is_done,
                        key=task_key
                    )

                    # If user toggled it
                    if checked != is_done:
                        try:
                            httpx.patch(
                                f"{WORKSHOP_SERVICE_URL}/projects/{proj['id']}/tasks/{task['id']}",
                                json={"is_complete": checked},
                                headers=api_headers(), timeout=5.0
                            )
                            st.rerun()
                        except Exception:
                            pass

        with col_right:
            sec_head("", "PARTS CHECKLIST")

            parts = proj.get("parts", [])
            ps = proj.get("parts_summary", {})

            if parts:
                st.html(f"""
                <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#555;margin-bottom:10px;">
                    {ps.get('installed', 0)} installed · {ps.get('sourced', 0)} sourced ·
                    {ps.get('needed', 0)} needed · ${ps.get('total_value', 0):,.0f} est. value
                </div>""")

                for part in parts[:20]:
                    status_color = PART_STATUS_COLORS.get(part["status"], "#666")
                    source_tag = f"[{part['source']}]" if part["source"] != "salvage" else ""

                    st.html(f"""
                    <div style="background:#0c0c0c;border:1px solid #1a1a1a;border-left:3px solid {status_color};
                        padding:8px 12px;margin-bottom:3px;font-family:'Share Tech Mono',monospace;font-size:9px;">
                        <span style="color:#ff6600;">{esc(part['name'])}</span>
                        <span style="color:#333;"> · {esc(part['category'])} {source_tag}</span>
                        <span style="float:right;color:{status_color};font-size:8px;letter-spacing:1px;">
                            {esc(part['status']).upper()}
                        </span>
                    </div>""")

                if len(parts) > 20:
                    st.html(f"<div style='font-family:Share Tech Mono;font-size:8px;color:#442200;'>...and {len(parts) - 20} more parts</div>")
            else:
                st.html("<div style='font-family:Share Tech Mono,monospace;font-size:10px;color:#442200;'>No parts tracked yet.</div>")

        # ── Build Notes ──
        st.html("<div style='height:20px'></div>")
        sec_head("", "BUILD LOG")

        notes = proj.get("notes", [])
        if notes:
            for note in notes[:10]:
                note_icon = {"safety": "⚠️", "tools": "🔧", "phase_change": "⏭", "log": "📝"}.get(note["note_type"], "📝")
                st.html(f"""
                <div class="admin-row">
                    <span style="color:#ff6600;">{note_icon}</span>&nbsp;
                    <span style="color:#888;">{esc(note['content'][:200])}</span>
                    <span style="float:right;color:#333;font-size:8px;">{esc(note.get('created_at', '')[:16])}</span>
                </div>""")

        # Add note form
        new_note = st.text_input("ADD BUILD NOTE", placeholder="Log progress, issues, observations...",
                                 key=f"note_input_{proj['id']}")
        if st.button("📝  LOG NOTE", key=f"note_btn_{proj['id']}"):
            if new_note.strip():
                try:
                    httpx.post(
                        f"{WORKSHOP_SERVICE_URL}/projects/{proj['id']}/notes",
                        json={"phase": current_phase, "content": new_note, "note_type": "log"},
                        headers=api_headers(), timeout=5.0
                    )
                    st.rerun()
                except Exception:
                    st.error("Could not save note")


# ════════════════════════════════════════════════════════════
#   TAB: ADMIN (master only)
# ════════════════════════════════════════════════════════════
def tab_admin():
    sec_head("04", "CONTROL ROOM")

    try:
        resp = httpx.get(
            f"{ADMIN_SERVICE_URL}/dashboard",
            headers={"x-master-key": MASTER_KEY},
            timeout=10.0
        )
        if resp.status_code == 200:
            dash = resp.json()
            lic  = dash.get("licenses", {})
            rev  = dash.get("revenue", {})

            # Revenue metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.html(metric_card(rev.get("estimated_mrr", "$0"), "EST. MONTHLY REVENUE"))
            with col2:
                st.html(metric_card(lic.get("active", 0), "ACTIVE LICENSES"))
            with col3:
                st.html(metric_card(lic.get("expiring_soon", 0), "EXPIRING SOON"))

            st.html("<div style='height:24px'></div>")

            col1, col2 = st.columns(2)

            with col1:
                sec_head("", "RECENT SIGNUPS")
                for u in dash.get("recent_signups", []):
                    st.html(f"""
                    <div class="admin-row">
                        <span style="color:#ff6600;">{esc(u['name'])}</span> · {esc(u['email'])}<br>
                        <span style="color:#555;font-size:8px;">{esc(u['tier']).upper()} · {esc(u['joined'][:10])}</span>
                    </div>""")

            with col2:
                sec_head("", "MANAGE LICENSES")
                action = st.selectbox("ACTION", ["Create License", "Extend License", "Revoke License"])

                if action == "Create License":
                    email = st.text_input("EMAIL")
                    name  = st.text_input("NAME")
                    tier  = st.selectbox("TIER", ["starter", "pro", "master"])
                    days  = st.number_input("DAYS", value=30, min_value=1)
                    if st.button("⚡ CREATE LICENSE"):
                        r = httpx.post(
                            f"{ADMIN_SERVICE_URL}/licenses/create",
                            json={"email": email, "name": name, "tier": tier, "days": days},
                            headers={"x-master-key": MASTER_KEY}, timeout=15.0
                        )
                        if r.status_code == 200:
                            d = r.json()
                            st.success(f"✅ License created: {d.get('key')}")
                        else:
                            st.error(f"Failed: {r.status_code}")

                elif action == "Extend License":
                    lic_key = st.text_input("LICENSE KEY")
                    days    = st.number_input("DAYS TO ADD", value=30, min_value=1)
                    if st.button("⚡ EXTEND"):
                        r = httpx.post(
                            f"{ADMIN_SERVICE_URL}/licenses/extend",
                            json={"license_key": lic_key, "days": days},
                            headers={"x-master-key": MASTER_KEY}, timeout=15.0
                        )
                        st.success("✅ Extended!") if r.status_code == 200 else st.error(f"Failed: {r.status_code}")

                elif action == "Revoke License":
                    lic_key = st.text_input("LICENSE KEY")
                    reason  = st.text_input("REASON", value="Admin revoked")
                    if st.button("⛔ REVOKE"):
                        r = httpx.post(
                            f"{ADMIN_SERVICE_URL}/licenses/revoke",
                            json={"license_key": lic_key, "reason": reason},
                            headers={"x-master-key": MASTER_KEY}, timeout=15.0
                        )
                        st.success("✅ Revoked!") if r.status_code == 200 else st.error(f"Failed: {r.status_code}")

            # All users
            st.html("<div style='height:24px'></div>")
            sec_head("", "ALL USERS")
            ur = httpx.get(
                f"{ADMIN_SERVICE_URL}/users",
                headers={"x-master-key": MASTER_KEY}, timeout=10.0
            )
            if ur.status_code == 200:
                for u in ur.json():
                    exp_color = "#ff4444" if u["status"] != "active" else "#888"
                    st.html(f"""
                    <div class="admin-row">
                        <span style="color:#ff6600;font-family:'Share Tech Mono',monospace;font-size:10px;">
                            {esc(u['license_key'])}
                        </span><br>
                        <span style="color:#888;">{esc(u['name'])} · {esc(u['email'])}</span>
                        &nbsp;&nbsp;
                        <span style="color:{exp_color};font-size:8px;">
                            {esc(u['status']).upper()} · {esc(u['tier']).upper()} · expires {esc(u['expires_at'][:10])}
                            · {esc(u['actual_builds'])} builds
                        </span>
                    </div>""")
        else:
            st.error(f"Admin service error: {resp.status_code}")
    except Exception as e:
        st.error(f"Admin offline: {e}")


# ════════════════════════════════════════════════════════════
#   MAIN DASHBOARD
# ════════════════════════════════════════════════════════════
def main_dashboard():
    render_sidebar()
    render_header()

    # Build tab list based on permissions
    tab_labels = ["⚡  NEW BUILD", "🔬  X-RAY SCANNER", "🔩  WORKSHOP", "📜  HISTORY", "📊  ANALYTICS"]
    if st.session_state.is_admin:
        tab_labels.append("🔐  CONTROL ROOM")

    tabs = st.tabs(tab_labels)

    with tabs[0]:
        tab_new_build()
    with tabs[1]:
        tab_scanner()
    with tabs[2]:
        tab_workshop()
    with tabs[3]:
        tab_history()
    with tabs[4]:
        tab_analytics()
    if st.session_state.is_admin and len(tabs) > 5:
        with tabs[5]:
            tab_admin()


# ════════════════════════════════════════════════════════════
#   ROUTING
# ════════════════════════════════════════════════════════════
if not st.session_state.authenticated:
    login()
else:
    main_dashboard()
