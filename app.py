import streamlit as st
import os
import httpx
import jwt
from dotenv import load_dotenv

load_dotenv()

# ── Configuration & Environment Check ─────────────────────────────────────────
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
MASTER_KEY = os.getenv("MASTER_KEY")

# Safety check to prevent the pink error box
if not MASTER_KEY:
    st.error("Server misconfigured: MASTER_KEY environment variable not set.")
    st.stop()

# ── Page Setup ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="The Builder", page_icon="🔧", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "token" not in st.session_state:
    st.session_state.token = None

# ── Login Logic ──────────────────────────────────────────────────────────────
def login():
    st.title("🔧 The Builder: Garage Access")
    key_input = st.text_input("Enter License Key", type="password")
    
    if st.button("Access Forge"):
        if key_input == MASTER_KEY:
            st.session_state.authenticated = True
            st.success("Master override accepted.")
            st.rerun()
        else:
            # Check with Auth Service
            try:
                headers = {"x-internal-key": INTERNAL_API_KEY}
                response = httpx.post(
                    f"{AUTH_SERVICE_URL}/verify-license",
                    json={"license_key": key_input},
                    headers=headers,
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.token = data["token"]
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid Key. Access Denied.")
            except Exception as e:
                st.error(f"Communication error with Auth Service: {e}")

# ── Main Dashboard ───────────────────────────────────────────────────────────
def main_dashboard():
    st.sidebar.title("Anthony's Garage")
    if st.sidebar.button("Log Out"):
        st.session_state.authenticated = False
        st.rerun()

    st.title("The Forge")
    
    tab1, tab2 = st.tabs(["🚀 New Build", "📜 History"])
    
    with tab1:
        st.header("Start a Build")
        junk_input = st.text_area("What junk are we using today?", placeholder="Old diesel parts, hydraulic pump, scrap steel...")
        project_type = st.selectbox("What are we making?", ["Combat Robot", "Industrial Tool", "Garage Utility"])
        
        if st.button("Forge It"):
            if not junk_input:
                st.warning("I can't build something out of nothing. Put your parts in the list.")
            else:
                with st.spinner("The AI is over-engineering your build..."):
                    try:
                        headers = {"x-internal-key": INTERNAL_API_KEY}
                        ai_response = httpx.post(
                            f"{AI_SERVICE_URL}/generate",
                            json={"junk_desc": junk_input, "project_type": project_type},
                            headers=headers,
                            timeout=100.0
                        )
                        if ai_response.status_code == 200:
                            st.markdown(ai_response.json()["content"])
                        else:
                            st.error("The Brain stalled. Try again.")
                    except Exception as e:
                        st.error(f"AI Service is unresponsive: {e}")

    with tab2:
        st.header("Previous Blueprints")
        st.info("Build history will appear here once the database sync is complete.")

# ── Routing ──────────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    login()
else:
    main_dashboard()
