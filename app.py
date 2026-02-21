"""
app.py — The Builder (Refined)
==============================
Updates:
  ✅ Added diagnostic status codes to error messages.
  ✅ Improved "Non-fatal" calls to notify user of sync issues.
  ✅ Ensured case-sensitivity safety for Linux deployments.
  ✅ Added explicit timeout handling for long AI Forge runs.
"""

import os
import streamlit as st
import requests
from datetime import datetime

# ── Must be first ──────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="The Builder", page_icon="🔨")

# ── Config ─────────────────────────────────────────────────────────────────────
MASTER_KEY         = os.environ.get("MASTER_KEY")
STRIPE_PAYMENT_URL = os.environ.get("STRIPE_PAYMENT_URL", "https://buy.stripe.com/dRm3cvfdb3655831rX1RC00")
APP_URL            = os.environ.get("APP_URL", "")
AUTH_SERVICE_URL   = os.environ.get("AUTH_SERVICE_URL", "")
AI_SERVICE_URL     = os.path.normpath(os.environ.get("AI_SERVICE_URL", "")) # Clean trailing slashes
INTERNAL_API_KEY   = os.environ.get("INTERNAL_API_KEY", "")

# Guard: fail loudly if critical env vars are missing
if not MASTER_KEY:
    st.error("⚠️ Server misconfigured: MASTER_KEY environment variable not set.")
    st.stop()
if not AUTH_SERVICE_URL:
    st.error("⚠️ Server misconfigured: AUTH_SERVICE_URL not set.")
    st.stop()
if not AI_SERVICE_URL:
    st.error("⚠️ Server misconfigured: AI_SERVICE_URL not set.")
    st.stop()

INTERNAL_HEADERS = {"X-Internal-Key": INTERNAL_API_KEY}

# ── Styles ─────────────────────────────────────────────────────────────────────
# Using lowercase import for Linux/Render compatibility
try:
    from builder_styles import BUILDER_CSS, FORGE_HEADER_HTML
    st.markdown(BUILDER_CSS, unsafe_allow_html=True)
except ImportError:
    st.error("System Error: Could not find 'builder_styles.py'. Ensure filename is lowercase in GitHub.")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
#  SERVICE CALLS
# ══════════════════════════════════════════════════════════════════════════════

def call_auth_validate(license_key: str) -> dict:
    try:
        resp = requests.post(
            f"{AUTH_SERVICE_URL}/auth/validate",
            json={"license_key": license_key},
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        return {"valid": False, "status": "error", "detail": f"HTTP {resp.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"valid": False, "status": "service_unavailable"}
    except Exception as e:
        return {"valid": False, "status": "error", "detail": str(e)}


def call_ai_forge(license_key: str, junk: str, project_type: str,
                  image_desc: str = "", history: list = None) -> dict:
    try:
        # Increased timeout slightly and added diagnostic status tracking
        resp = requests.post(
            f"{AI_SERVICE_URL}/ai/forge",
            json={
                "license_key":  license_key,
                "junk_desc":    junk,
                "project_type": project_type,
                "image_desc":   image_desc,
                "history":      history or [],
            },
            headers=INTERNAL_HEADERS,
            timeout=100, # Bob might need more time for complex builds
        )
        
        if resp.status_code == 429:
            return {"error": "Daily build limit reached (429). Take a break, Boss."}
        
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return {"error": "The forge timed out (100s). The brain is overloaded—try a shorter junk description."}
    except requests.exceptions.ConnectionError:
        return {"error": f"AI service unreachable at {AI_SERVICE_URL}. Check your server logs."}
    except Exception as e:
        return {"error": f"Forge Error ({type(e).__name__}): {str(e)}"}


def call_save_build(license_key: str, entry: str):
    """Saves build but alerts user if history sync fails."""
    try:
        resp = requests.post(
            f"{AUTH_SERVICE_URL}/auth/save-build",
            json={"license_key": license_key, "entry": entry},
            headers=INTERNAL_HEADERS,
            timeout=7
        )
        resp.raise_for_status()
    except Exception:
        st.toast("⚠️ Warning: Build finished but failed to save to History.", icon="☁️")


# ══════════════════════════════════════════════════════════════════════════════
#  UI & LOGIC (Kept consistent with your original structure)
# ══════════════════════════════════════════════════════════════════════════════

# ... (Previous session_state and sidebar logic remains the same) ...

# ── Updated Forge Button Logic ────────────────────────────────────────────────
with tab1:
    # ... (Inputs remain same) ...

    with col_forge:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("FORGE IT\n🔥", use_container_width=True, type="primary"):
            if junk.strip():
                with st.spinner("⚡ SPARKS FLYING... THE BUILDER IS IN THE GARAGE"):
                    history_entries = []
                    if st.session_state.active_key:
                        raw_history = call_get_history(st.session_state.active_key)
                        history_entries = [e["entry"] for e in raw_history[:10]]

                    response = call_ai_forge(
                        st.session_state.active_key or "admin",
                        junk,
                        project_type,
                        image_desc,
                        history_entries
                    )

                    if "error" in response:
                        st.error(f"🚨 {response['error']}")
                    else:
                        st.session_state.last_result = response["result"]
                        st.session_state.last_usage  = response.get("usage")

                        if st.session_state.active_key:
                            ts = datetime.now().strftime("%b %d %H:%M")
                            # Now uses the improved call_save_build with user feedback
                            call_save_build(
                                st.session_state.active_key,
                                f"[{ts}] {project_type}: {junk[:80]}"
                            )
            else:
                st.warning("Need some junk to work with, boss.")

# ... (Rest of your original app logic) ...
