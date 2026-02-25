import streamlit as st
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
# We prioritize the public URL for the free tier to bypass internal networking blocks
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "https://builder-auth.onrender.com")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "https://builder-ai-233g.onrender.com")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
MASTER_KEY = os.getenv("MASTER_KEY")

st.set_page_config(page_title="THE BUILDER — AI Engineering Forge", page_icon="⚙️", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&family=Orbitron:wght@400;700;900&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, .stApp {
    background-color: #060606 !important;
    color: #e8d5b0 !important;
    font-family: 'Rajdhani', sans-serif !important;
}

#MainMenu, footer, header, .stDeployButton { display: none !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #060606; }
::-webkit-scrollbar-thumb { background: #ff6600; }

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes glow {
    0%,100% { box-shadow: 0 0 6px #00cc66; opacity:1; }
    50% { box-shadow: 0 0 18px #00cc66; opacity:0.6; }
}
@keyframes flicker {
    0%,100% { opacity:1; } 92% { opacity:1; } 93% { opacity:0.8; } 94% { opacity:1; }
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background: #080808 !important;
    border-right: 1px solid #1a1a1a !important;
}
[data-testid="stSidebar"] > div { padding: 0 !important; }

.sidebar-header {
    background: linear-gradient(160deg, #120800, #080808);
    border-bottom: 1px solid #2a1500;
    padding: 28px 20px 22px;
    position: relative; overflow: hidden;
}
.sidebar-header::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #ff6600, #ffaa00, #ff6600, transparent);
}
.sidebar-header::after {
    content: '⚙';
    position: absolute; right: -15px; top: -15px;
    font-size: 90px; opacity: 0.04;
    animation: spin 25s linear infinite;
    pointer-events: none;
}
.sidebar-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 26px; color: #ff6600; letter-spacing: 3px;
    text-shadow: 0 0 20px rgba(255,100,0,0.4); line-height: 1.1;
}
.sidebar-sub {
    font-family: 'Share Tech Mono', monospace;
    font-size: 9px; color: #442200; letter-spacing: 2px;
    text-transform: uppercase; margin-top: 5px;
}
.status-row {
    display: flex; align-items: center; gap: 6px; margin-top: 14px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 9px; color: #00cc66; letter-spacing: 1px;
}
.pulse {
    width: 7px; height: 7px; background: #00cc66;
    border-radius: 50%; animation: glow 2s infinite;
}
.srv-row {
    padding: 9px 20px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px; letter-spacing: 1px; color: #444;
    display: flex; justify-content: space-between;
    border-bottom: 1px solid #0f0f0f;
}
.srv-on { color: #00cc66; }

/* ── BUTTONS ── */
.stButton > button {
    background: linear-gradient(135deg, #cc4400, #ff6600) !important;
    color: #000 !important; border: none !important; border-radius: 0 !important;
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 20px !important; letter-spacing: 4px !important;
    padding: 14px 48px !important;
    clip-path: polygon(10px 0%, 100% 0%, calc(100% - 10px) 100%, 0% 100%) !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #ff6600, #ffcc00) !important;
    box-shadow: 0 0 40px rgba(255,100,0,0.5) !important;
    transform: translateY(-2px) !important;
}

/* ── INPUTS ── */
.stTextArea textarea, .stTextInput input {
    background: #0c0c0c !important; border: 1px solid #2a1500 !important;
    border-radius: 0 !important; color: #e8d5b0 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 13px !important; padding: 16px !important;
}
</style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# --- LOGIN ---
def login():
    # (Keeping your massive HTML Landing Page structure here)
    # [Paste your Landing Page HTML section from your previous message here]
    
    st.markdown("<div style='height:4px;background:#060606'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.0, 1])
    with col2:
        key_input = st.text_input("MASTER KEY", type="password", placeholder="Enter access key...")
        if st.button("⚡ IGNITE THE FORGE"):
            if MASTER_KEY and key_input == MASTER_KEY:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("⛔ ACCESS DENIED")

# --- DASHBOARD ---
def main_dashboard():
    # Dashboard logic here
    st.title("THE FORGE")
    junk_input = st.text_area("PARTS ON THE WORKBENCH")
    project_type = st.selectbox("BUILD CLASSIFICATION", ["Combat Robot", "Shop Tool"])
    
    if st.button("🔥 FORGE THE BLUEPRINT"):
        with st.spinner("Connecting to Round Table..."):
            try:
                headers = {"x-internal-key": INTERNAL_API_KEY}
                # This call now uses the Public HTTPS URL
                with httpx.Client(timeout=100.0) as client:
                    response = client.post(
                        f"{AI_SERVICE_URL}/generate",
                        json={"junk_desc": junk_input, "project_type": project_type},
                        headers=headers
                    )
                if response.status_code == 200:
                    st.markdown(response.json()["content"])
                else:
                    st.error(f"Forge Error: {response.status_code}")
            except Exception as e:
                st.error(f"Connection Failed: Ensure AI_SERVICE_URL is set to the HTTPS address.")

if not st.session_state.authenticated:
    login()
else:
    main_dashboard()
