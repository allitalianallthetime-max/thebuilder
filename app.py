import streamlit as st
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

# ── Configuration Check ──────────────────────────────────────────────────────
# These match the names we set in your Render environment variables
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
MASTER_KEY = os.getenv("MASTER_KEY")

# ── Page Setup ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="The Builder", page_icon="🔧", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# ── Login Screen ─────────────────────────────────────────────────────────────
def login():
    st.title("🔧 The Builder: Garage Access")
    st.write("Enter your master key or license to start the forge.")
    
    key_input = st.text_input("Access Key", type="password")
    
    if st.button("Open Garage"):
        # Check Master Key first (No database needed)
        if MASTER_KEY and key_input == MASTER_KEY:
            st.session_state.authenticated = True
            st.success("Master override accepted. Welcome back, Anthony.")
            st.rerun()
        else:
            # Try to verify with the Auth Service database
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
                    st.error("Access Denied. Key not recognized.")
            except Exception as e:
                st.error(f"Auth Service is offline: {e}")

# ── Dashboard (The Forge) ────────────────────────────────────────────────────
def main_dashboard():
    st.sidebar.title("Anthony's Garage")
    if st.sidebar.button("Log Out"):
        st.session_state.authenticated = False
        st.rerun()

    st.title("The Forge")
    
    tab1, tab2 = st.tabs(["🚀 New Build", "📜 History"])
    
    with tab1:
        st.header("Start a Build")
        junk_input = st.text_area("What parts are on the workbench?", placeholder="Old diesel engine, hydraulic rams, scrap plate...")
        project_type = st.selectbox("What are we building?", ["Combat Robot", "Shop Tool", "Hydraulic Lift"])
        
        if st.button("Forge It"):
            if not junk_input:
                st.warning("I need a parts list to start the build.")
            else:
                with st.spinner("AI is crunching the mechanics..."):
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
                            st.error("AI service failed to respond.")
                    except Exception as e:
                        st.error(f"Cannot reach AI Service: {e}")

    with tab2:
        st.header("Previous Blueprints")
        st.info("Build history is currently syncing with the database.")

# ── Routing ──────────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    login()
else:
    main_dashboard()
