import streamlit as st
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

# --- NEW VIRTUAL WIRING ---
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "https://builder-auth.onrender.com")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "https://builder-ai-233g.onrender.com")
# NEW: Point this to your builder-vision public URL
VISION_SERVICE_URL = os.getenv("VISION_SERVICE_URL", "https://builder-vision.onrender.com")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
MASTER_KEY = os.getenv("MASTER_KEY")

st.set_page_config(page_title="THE BUILDER — AI Engineering Forge", page_icon="⚙️", layout="wide")

# (Keep your existing <style> block here)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def main_dashboard():
    # --- SIDEBAR & HEADER (Keep existing code) ---

    tab1, tab2, tab3 = st.tabs(["⚡ NEW BUILD", "👁️ VISION INSPECTOR", "💬 THE ROUND TABLE"])

    with tab1:
        st.markdown("### 🛠️ MANUAL LOAD")
        junk_input = st.text_area("PARTS ON THE WORKBENCH", height=150)
        project_type = st.selectbox("BUILD TYPE", ["Combat Robot", "Vehicle Mod", "Shop Tool"])
        
        if st.button("🔥 FORGE THE BLUEPRINT"):
            # (Keep your existing Forge logic here)
            pass

    with tab2:
        st.markdown("### 👁️ HARDWARE INSPECTION")
        st.info("Upload a photo of your parts. The Inspector will identify model numbers and salvageable components.")
        uploaded_file = st.file_uploader("Upload Hardware Image", type=["jpg", "jpeg", "png"])
        
        if uploaded_file and st.button("🔍 RUN INSPECTION"):
            with st.spinner("Scanning hardware..."):
                try:
                    files = {"file": uploaded_file.getvalue()}
                    response = httpx.post(f"{VISION_SERVICE_URL}/inspect", files=files, timeout=60.0)
                    if response.status_code == 200:
                        analysis = response.json()["analysis"]
                        st.success("Analysis Complete")
                        st.markdown(analysis)
                        # Option to "Load into Forge"
                        if st.button("📥 SEND TO WORKBENCH"):
                            st.session_state.parts_list = analysis
                    else:
                        st.error(f"Vision Error: {response.status_code}")
                except Exception as e:
                    st.error(f"Vision Service Offline: {e}")

    with tab3:
        st.markdown("### 💬 CHALLENGE THE BOARD")
        st.write("Argue with Gemini, Grok, Claude, and ChatGPT about your design.")
        
        for msg in st.session_state.chat_history:
            st.chat_message(msg["role"]).write(msg["content"])
            
        if prompt := st.chat_input("Challenge the mechanical logic..."):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)
            # Add logic here to call AI_SERVICE_URL for a chat response
