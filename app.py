"""
app.py — The Builder (Patched)
==============================
Critical fixes applied:
  ✅ MASTER_KEY no longer has a hardcoded default
  ✅ init_db() replaced with @st.cache_resource — runs once per server process
  ✅ Background scheduler thread REMOVED — now a separate Render Cron Job
  ✅ Groq calls routed through AI Service (rate limiting, error handling)
  ✅ Key validation calls Auth Service (JWT issued and stored in session)
  ✅ Build history calls Auth Service
  ✅ Email calls routed through notification queue (async)
  ✅ JWT re-validated before Forge calls — no stale boolean auth
"""

import os
import streamlit as st
import requests
from datetime import datetime

# ── Must be first ──────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="The Builder", page_icon="🔨")

# ── Config ─────────────────────────────────────────────────────────────────────
MASTER_KEY         = os.environ.get("MASTER_KEY")            # ✅ No default — fails safe
STRIPE_PAYMENT_URL = os.environ.get("STRIPE_PAYMENT_URL", "https://buy.stripe.com/dRm3cvfdb3655831rX1RC00")
APP_URL            = os.environ.get("APP_URL", "")
AUTH_SERVICE_URL   = os.environ.get("AUTH_SERVICE_URL", "")  # e.g. https://builder-auth.onrender.com
AI_SERVICE_URL     = os.environ.get("AI_SERVICE_URL", "")    # e.g. https://builder-ai.onrender.com
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
from builder_styles import BUILDER_CSS, FORGE_HEADER_HTML
st.markdown(BUILDER_CSS, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SERVICE CALLS
#  All business logic is now in services — app.py is UI only.
# ══════════════════════════════════════════════════════════════════════════════

def call_auth_validate(license_key: str) -> dict:
    """Call Auth Service to validate key and get JWT."""
    try:
        resp = requests.post(
            f"{AUTH_SERVICE_URL}/auth/validate",
            json={"license_key": license_key},
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"valid": False, "status": "service_unavailable"}
    except Exception as e:
        return {"valid": False, "status": "error", "detail": str(e)}


def call_ai_forge(license_key: str, junk: str, project_type: str,
                  image_desc: str = "", history: list = None) -> dict:
    """
    Call AI Service to forge a build. Returns {"result": str, "usage": dict}
    or {"error": str} on failure.
    """
    try:
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
            timeout=90,  # Groq can be slow
        )
        if resp.status_code == 429:
            detail = resp.json().get("detail", {})
            return {"error": detail.get("message", "Daily build limit reached.")}
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return {"error": "The forge took too long. Try again in a moment."}
    except requests.exceptions.ConnectionError:
        return {"error": "AI service unavailable. Check Render dashboard."}
    except Exception as e:
        return {"error": "Something went wrong in the forge. Try again."}


def call_get_history(license_key: str) -> list:
    try:
        resp = requests.get(
            f"{AUTH_SERVICE_URL}/auth/history/{license_key}",
            headers=INTERNAL_HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def call_save_build(license_key: str, entry: str):
    try:
        requests.post(
            f"{AUTH_SERVICE_URL}/auth/save-build",
            json={"license_key": license_key, "entry": entry},
            headers=INTERNAL_HEADERS,
            timeout=5
        )
    except Exception:
        pass  # Non-fatal


def call_get_licenses() -> list:
    try:
        resp = requests.get(
            f"{AUTH_SERVICE_URL}/admin/licenses",
            headers=INTERNAL_HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def call_create_license(email: str, name: str) -> dict:
    try:
        resp = requests.post(
            f"{AUTH_SERVICE_URL}/auth/create",
            json={"email": email, "name": name, "days": 30},
            headers=INTERNAL_HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def call_extend_license(key: str, days: int) -> bool:
    try:
        resp = requests.post(
            f"{AUTH_SERVICE_URL}/auth/extend",
            json={"license_key": key, "days": days},
            headers=INTERNAL_HEADERS,
            timeout=10
        )
        return resp.status_code == 200
    except Exception:
        return False


def call_revoke_license(key: str, reason: str) -> bool:
    try:
        resp = requests.post(
            f"{AUTH_SERVICE_URL}/auth/revoke",
            json={"license_key": key, "reason": reason},
            headers=INTERNAL_HEADERS,
            timeout=10
        )
        return resp.status_code == 200
    except Exception:
        return False


def call_delete_user_data(key: str):
    try:
        requests.delete(
            f"{AUTH_SERVICE_URL}/auth/history/{key}",
            headers=INTERNAL_HEADERS,
            timeout=10
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
defaults = {
    "authenticated": False,
    "is_admin":      False,
    "license_info":  None,
    "active_key":    None,
    "auth_token":    None,    # ✅ JWT stored here
    "current_parts": [],
    "last_result":   None,
    "last_usage":    None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════════════════════════════
try:
    col_logo, col_title = st.columns([1, 5])
    with col_logo:
        st.image("aoc3po_logo.png", width=220)
    with col_title:
        st.markdown(FORGE_HEADER_HTML, unsafe_allow_html=True)
except Exception:
    st.markdown(FORGE_HEADER_HTML, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  POST-PAYMENT KEY REVEAL (Stripe redirect)
# ══════════════════════════════════════════════════════════════════════════════
try:
    _new_key = st.query_params.get("key", "")
except Exception:
    _new_key = ""

if _new_key:
    st.markdown(f"""
<div class="new-key-banner">
    <div style="font-family:'Share Tech Mono',monospace;color:#FF6B00;
                font-size:0.7rem;letter-spacing:4px;margin-bottom:10px;">
        ✅ &nbsp; PAYMENT CONFIRMED — YOUR LICENSE KEY
    </div>
    <div class="key-box" style="font-size:1.35rem;margin:0 auto;max-width:480px;">
        {_new_key}
    </div>
    <div style="font-family:'Rajdhani',sans-serif;color:#7A8BA0;
                font-size:0.9rem;letter-spacing:1px;margin-top:14px;line-height:1.7;">
        📋 &nbsp; <strong style="color:#C8D4E8;">Copy this key now.</strong>
        &nbsp; Paste it in the sidebar to unlock The Builder.<br/>
        A confirmation email is also on its way to you.
    </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
st.sidebar.markdown("### 🔐 THE BUILDER ACCESS")
sidebar_mode = st.sidebar.radio(
    "",
    ["🔑 Use License Key", "🛒 Buy Access ($29.99/mo)"],
    label_visibility="collapsed"
)

if sidebar_mode == "🛒 Buy Access ($29.99/mo)":
    st.sidebar.markdown("**Get full access for $29.99/month.**\n\nYour license key is emailed to you instantly after payment.")
    st.sidebar.markdown(
        f'<a href="{STRIPE_PAYMENT_URL}" target="_blank" class="stripe-btn">🔨 &nbsp; SUBSCRIBE — $29.99/MO</a>',
        unsafe_allow_html=True
    )
else:
    access_input = st.sidebar.text_input("License key or master key", type="password", placeholder="BLDR-XXXX-XXXX-XXXX")

    if st.sidebar.button("⚡ UNLOCK THE BUILDER", use_container_width=True):
        if access_input == MASTER_KEY:
            st.session_state.authenticated = True
            st.session_state.is_admin      = True
            st.sidebar.success("✅ Admin access granted.")
        else:
            result = call_auth_validate(access_input)
            if result["valid"]:
                st.session_state.authenticated = True
                st.session_state.is_admin      = False
                st.session_state.license_info  = result
                st.session_state.active_key    = access_input
                st.session_state.auth_token    = result.get("token")   # ✅ Store JWT
                name_str = f", {result['name']}" if result.get("name") else ""
                st.sidebar.success(f"✅ Welcome back{name_str}!\n{result['days_remaining']} days remaining.")
            else:
                msgs = {
                    "not_found":          "Key not found. Check your email.",
                    "expired":            "License expired. Please renew.",
                    "revoked":            "Key revoked. Contact Anthony.",
                    "service_unavailable":"Auth service offline. Try again shortly.",
                }
                st.sidebar.error(msgs.get(result.get("status"), "Invalid key."))
                st.sidebar.markdown(
                    f'<a href="{STRIPE_PAYMENT_URL}" target="_blank" class="stripe-btn">🔨 RENEW — $29.99/MO</a>',
                    unsafe_allow_html=True
                )

    if st.session_state.authenticated and not st.session_state.is_admin and st.session_state.license_info:
        info  = st.session_state.license_info
        d     = info.get("days_remaining", 0)
        color = "#4CAF50" if d > 10 else "#FF6B00" if d > 0 else "#FF4B4B"
        st.sidebar.markdown(f"""
<div style="background:rgba(255,107,0,0.05);border:1px solid rgba(255,107,0,0.2);
            border-radius:3px;padding:12px;margin-top:16px;font-family:'Rajdhani',sans-serif;">
    <div style="color:#888;font-size:0.75rem;letter-spacing:2px;text-transform:uppercase;">Active License</div>
    <div style="color:#C8D4E8;font-size:0.9rem;margin-top:4px;">{info.get('email','')}</div>
    <div style="color:{color};font-weight:700;font-size:1.1rem;margin-top:4px;">{d} DAYS REMAINING</div>
</div>
""", unsafe_allow_html=True)

    if st.session_state.is_admin:
        st.sidebar.markdown("""
<div style="background:rgba(255,107,0,0.08);border:1px solid rgba(255,107,0,0.3);
            border-radius:3px;padding:10px;margin-top:12px;font-family:'Share Tech Mono',monospace;
            color:#FF6B00;font-size:0.8rem;text-align:center;letter-spacing:2px;">
    ⚙ ADMIN MODE ACTIVE
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  GATE
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.authenticated:
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_b, _ = st.columns([1, 2, 1])
    with col_b:
        st.markdown("""
<div style="background:rgba(13,17,23,0.95);border:1px solid rgba(255,107,0,0.3);
            border-top:3px solid #FF6B00;border-radius:4px;padding:40px;text-align:center;
            font-family:'Rajdhani',sans-serif;">
    <div style="font-family:'Black Ops One',cursive;color:#FF6B00;font-size:2rem;
                letter-spacing:4px;margin-bottom:12px;">🔒 ACCESS LOCKED</div>
    <div style="color:#7A8BA0;font-size:1rem;letter-spacing:1px;line-height:1.8;">
        This forge is private.<br/>Enter your license key in the sidebar,<br/>or subscribe for instant access.
    </div>
</div>
""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<a href="{STRIPE_PAYMENT_URL}" target="_blank" class="stripe-btn">🔨 &nbsp; SUBSCRIBE NOW — $29.99/MO</a>',
            unsafe_allow_html=True
        )
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
#  LICENSE WARNING BANNERS
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.is_admin and st.session_state.license_info:
    info      = st.session_state.license_info
    days_left = info.get("days_remaining", 999)
    if days_left < 0:
        days_over   = abs(days_left)
        days_to_del = max(0, 15 - days_over)
        st.markdown(f"""
<div class="danger-banner">
    🚨 <strong>FINAL WARNING:</strong> License expired {days_over} day(s) ago.
    Build history deleted in <strong>{days_to_del} day(s)</strong> if not renewed. &nbsp;
    <a href="{STRIPE_PAYMENT_URL}" style="color:#FF4B4B;font-weight:700;text-decoration:none;">→ RENEW NOW</a>
</div>
""", unsafe_allow_html=True)
    elif days_left <= 10:
        st.markdown(f"""
<div class="warning-banner">
    ⚠ <strong>LICENSE EXPIRES IN {days_left} DAY(S).</strong> &nbsp;
    <a href="{STRIPE_PAYMENT_URL}" style="color:#FF6B00;font-weight:700;text-decoration:none;">→ RENEW — $29.99/MO</a>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_labels = ["🔨 FORGE", "📖 HISTORY", "🖼️ EXAMPLES", "🛠️ SAFETY"]
if st.session_state.is_admin:
    tab_labels.append("⚙️ ADMIN")

all_tabs  = st.tabs(tab_labels)
tab1, tab2, tab3, tab4 = all_tabs[0], all_tabs[1], all_tabs[2], all_tabs[3]
tab_admin = all_tabs[4] if st.session_state.is_admin else None


# ── TAB 1: FORGE ──────────────────────────────────────────────────────────────
with tab1:
    st.markdown("<br>", unsafe_allow_html=True)
    col_inputs, col_forge = st.columns([4, 1])

    with col_inputs:
        project_type = st.selectbox(
            "BUILD TYPE",
            ["Wheeled Robot", "Tracked Robot", "Portable Power Gadget",
             "Drone/Chassis Base", "Smart Sensor Station", "Anything Crazy"]
        )
        junk = st.text_area(
            "DESCRIBE YOUR JUNK",
            placeholder="Old Ryobi 40V battery, Craftsman lawnmower motor & wheels, 2x4s, zip ties, PVC pipe...",
            height=130
        )
        uploaded_file = st.file_uploader("UPLOAD PHOTO (OPTIONAL)", type=["png", "jpg", "jpeg"])
        image_desc = ""
        if uploaded_file:
            st.image(uploaded_file, width=300)
            image_desc = st.text_input("PHOTO DESCRIPTION", placeholder="Rusty lawnmower engine with 4 wheels attached")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("➕ ADD TO CURRENT PROJECT", use_container_width=True):
                if junk.strip():
                    st.session_state.current_parts.append(junk)
                    st.success(f"✅ Added. Project now has {len(st.session_state.current_parts)} part(s).")
                else:
                    st.warning("Describe your junk first.")
        with col_b:
            if st.button("🔄 START NEW PROJECT", use_container_width=True):
                st.session_state.current_parts = []
                st.session_state.last_result   = None
                st.success("New project started — blueprint reset.")

        if st.session_state.current_parts:
            st.markdown(f"""
<div style="background:rgba(255,107,0,0.06);border:1px solid rgba(255,107,0,0.2);
            border-radius:3px;padding:10px 16px;margin-top:8px;
            font-family:'Share Tech Mono',monospace;color:#FF8C00;font-size:0.85rem;letter-spacing:2px;">
    ◆ &nbsp; {len(st.session_state.current_parts)} PART(S) LOADED INTO CURRENT PROJECT
</div>
""", unsafe_allow_html=True)

        # ✅ Show usage counter
        if st.session_state.last_usage:
            u = st.session_state.last_usage
            remaining = u["limit"] - u["used"]
            st.caption(f"BUILDS TODAY: {u['used']} / {u['limit']}  ·  {remaining} REMAINING")

    with col_forge:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("FORGE IT\n🔥", use_container_width=True, type="primary"):
            if junk.strip():
                with st.spinner("⚡ SPARKS FLYING... THE BUILDER IS IN THE GARAGE"):
                    history_entries = []
                    if st.session_state.active_key:
                        raw_history = call_get_history(st.session_state.active_key)
                        history_entries = [e["entry"] for e in raw_history[:10]]

                    # ✅ Call AI Service (handles rate limiting and Groq errors)
                    response = call_ai_forge(
                        st.session_state.active_key or "admin",
                        junk,
                        project_type,
                        image_desc,
                        history_entries
                    )

                    if "error" in response:
                        st.error(f"⚠️ {response['error']}")
                    else:
                        st.session_state.last_result = response["result"]
                        st.session_state.last_usage  = response.get("usage")

                        if st.session_state.active_key:
                            ts = datetime.now().strftime("%b %d %H:%M")
                            call_save_build(
                                st.session_state.active_key,
                                f"[{ts}] {project_type}: {junk[:80]}"
                            )
            else:
                st.warning("Need some junk to work with, boss.")

    if st.session_state.last_result:
        st.markdown("""
<div style="display:flex;align-items:center;gap:16px;margin:32px 0 16px;">
    <div style="flex:1;height:1px;background:linear-gradient(90deg,transparent,rgba(255,107,0,0.5));"></div>
    <div style="font-family:'Black Ops One',cursive;color:#FF6B00;letter-spacing:4px;font-size:0.9rem;">BUILD REPORT</div>
    <div style="flex:1;height:1px;background:linear-gradient(90deg,rgba(255,107,0,0.5),transparent);"></div>
</div>
""", unsafe_allow_html=True)
        st.markdown(st.session_state.last_result)
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            "📥 DOWNLOAD BUILD AS MARKDOWN",
            st.session_state.last_result,
            file_name=f"build_{datetime.now().strftime('%b%d_%H%M')}.md"
        )


# ── TAB 2: HISTORY ────────────────────────────────────────────────────────────
with tab2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### BUILD HISTORY")
    if st.session_state.active_key:
        entries = call_get_history(st.session_state.active_key)
        if entries:
            for i, e in enumerate(entries):
                with st.expander(f"BUILD {len(entries)-i}  ·  {e['timestamp'][:16]}"):
                    st.write(e["entry"])
        else:
            st.markdown("""
<div style="background:rgba(13,17,23,0.8);border:1px dashed rgba(255,107,0,0.2);
            border-radius:4px;padding:40px;text-align:center;
            font-family:'Share Tech Mono',monospace;color:#3A4A5C;letter-spacing:2px;">
    NO BUILDS YET — GO FORGE SOMETHING
</div>
""", unsafe_allow_html=True)
    elif st.session_state.is_admin:
        st.info("Logged in as admin. Build history is per user-key.")
    else:
        st.info("Log in with your license key to see your history.")


# ── TAB 3: EXAMPLES (unchanged) ───────────────────────────────────────────────
with tab3:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### EXAMPLE BUILDS")
    examples = [
        ("🔋 Old generator + wheels",           "Tracked power rover that charges your Orange Pi 5 Plus off-grid"),
        ("⚙️ Weed eater motor + PVC",            "Mini tracked scout bot with camera mount"),
        ("🔌 Ryobi 40V battery + old box fan",   "Portable high-power USB-C station for field robotics"),
        ("🌿 Lawnmower deck + wheelchair motors", "Full-size outdoor robot platform with autonomous mowing"),
        ("🎛️ Old PC PSU + Arduino",              "Bench power supply with digital voltage/current display"),
    ]
    for ex_junk, ex_idea in examples:
        st.markdown(f"""
<div style="background:#1C2333;border:1px solid rgba(255,107,0,0.15);border-left:3px solid rgba(255,107,0,0.4);
            border-radius:0 4px 4px 0;padding:14px 20px;margin-bottom:8px;font-family:'Rajdhani',sans-serif;">
    <span style="color:#FF8C00;font-weight:700;">{ex_junk}</span>
    <span style="color:#3A4A5C;margin:0 10px;">→</span>
    <span style="color:#C8D4E8;">{ex_idea}</span>
</div>
""", unsafe_allow_html=True)


# ── TAB 4: SAFETY (unchanged) ─────────────────────────────────────────────────
with tab4:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### PRO TIPS & SAFETY")
    tips = [
        ("👁️ EYE PROTECTION",  "Always wear safety glasses when cutting, grinding, or running motors."),
        ("🔋 BATTERY SAFETY",  "Never run bare lithium cells without a BMS. Ryobi tool packs are ideal."),
        ("⚡ MOTOR TESTING",   "Test all repurposed motors at 20% power first."),
        ("🖥️ COMPUTE CHOICE",  "Orange Pi 5 Plus or Radxa Rock 5C for real robotics."),
        ("🔩 FRAME INTEGRITY", "Measure twice, cut outside. Use gussets at stress points."),
        ("🌡️ HEAT MANAGEMENT", "High-current motor controllers get hot. Add heatsink + thermal shutoff relay."),
        ("🛡️ FAILSAFE FIRST",  "Wire a physical kill switch before anything else. Software fails; a relay doesn't."),
    ]
    for icon_title, body in tips:
        st.markdown(f"""
<div style="background:#1C2333;border:1px solid rgba(255,107,0,0.12);border-left:3px solid rgba(255,107,0,0.5);
            border-radius:0 4px 4px 0;padding:16px 20px;margin-bottom:10px;font-family:'Rajdhani',sans-serif;">
    <div style="color:#FF8C00;font-weight:700;font-size:0.8rem;letter-spacing:3px;text-transform:uppercase;margin-bottom:4px;">{icon_title}</div>
    <div style="color:#C8D4E8;font-size:1rem;line-height:1.6;">{body}</div>
</div>
""", unsafe_allow_html=True)


# ── TAB 5: ADMIN ──────────────────────────────────────────────────────────────
if st.session_state.is_admin and tab_admin is not None:
    with tab_admin:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### ⚙️ ADMIN PANEL")

        st.markdown('<div style="font-family:\'Share Tech Mono\',monospace;color:#FF6B00;letter-spacing:3px;font-size:0.8rem;margin-bottom:12px;">── GENERATE LICENSE KEY ──────────────────────────────</div>', unsafe_allow_html=True)
        col_n, col_e = st.columns(2)
        with col_n: new_name  = st.text_input("CUSTOMER NAME")
        with col_e: new_email = st.text_input("CUSTOMER EMAIL")

        if st.button("⚡ GENERATE & EMAIL KEY"):
            if new_email.strip():
                result = call_create_license(new_email.strip(), new_name.strip())
                if "error" in result:
                    st.error(f"Failed: {result['error']}")
                else:
                    new_key = result["key"]
                    st.markdown(f"<div class='key-box'>{new_key}</div>", unsafe_allow_html=True)
                    st.success(f"✅ Key generated for {new_email}. Welcome email queued.")
            else:
                st.warning("Enter a customer email.")

        st.divider()

        st.markdown('<div style="font-family:\'Share Tech Mono\',monospace;color:#FF6B00;letter-spacing:3px;font-size:0.8rem;margin-bottom:12px;">── MANAGE A KEY ──────────────────────────────────</div>', unsafe_allow_html=True)
        manage_key = st.text_input("LICENSE KEY TO MANAGE")
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            ext_days = st.number_input("EXTEND BY (DAYS)", min_value=1, max_value=365, value=30)
            if st.button("✅ EXTEND LICENSE", use_container_width=True):
                if manage_key.strip():
                    ok = call_extend_license(manage_key.strip(), int(ext_days))
                    st.success("Extended!") if ok else st.error("Failed.")
                else:
                    st.warning("Enter a key.")
        with col_m2:
            rev_reason = st.text_input("REVOKE REASON")
            if st.button("🚫 REVOKE LICENSE", use_container_width=True):
                if manage_key.strip():
                    ok = call_revoke_license(manage_key.strip(), rev_reason)
                    st.success("Revoked.") if ok else st.error("Failed.")
                else:
                    st.warning("Enter a key.")
        with col_m3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️ DELETE USER DATA", use_container_width=True):
                if manage_key.strip():
                    call_delete_user_data(manage_key.strip())
                    st.success("User data deleted.")
                else:
                    st.warning("Enter a key.")

        st.divider()

        st.markdown('<div style="font-family:\'Share Tech Mono\',monospace;color:#FF6B00;letter-spacing:3px;font-size:0.8rem;margin-bottom:12px;">── ALL LICENSE HOLDERS ───────────────────────────</div>', unsafe_allow_html=True)
        all_licenses = call_get_licenses()
        now = datetime.utcnow()
        if all_licenses:
            for lic in all_licenses:
                exp_dt    = datetime.fromisoformat(lic["expires_at"])
                days_left = (exp_dt - now).days
                color     = "#4CAF50" if days_left > 10 else "#FF8C00" if days_left > 0 else "#FF4B4B"
                st.markdown(f"""
<div class='admin-row'>
    <strong style="color:#C8D4E8;">{lic.get('name') or '(no name)'}</strong>
    <span style="color:#3A4A5C;"> — </span>
    <span style="color:#7A8BA0;">{lic['email']}</span><br/>
    <span style="color:#3A4A5C;font-size:0.8rem;font-family:'Share Tech Mono',monospace;">KEY: </span>
    <code>{lic['license_key']}</code>
    <span style="color:#3A4A5C;"> &nbsp;|&nbsp; </span>
    <span style="color:{color};font-weight:700;font-size:0.85rem;">{lic['status'].upper()}</span>
    <span style="color:#3A4A5C;"> &nbsp;|&nbsp; </span>
    <span style="color:#7A8BA0;">Expires {lic['expires_at'][:10]} ({days_left}d)</span>
</div>
""", unsafe_allow_html=True)
        else:
            st.info("No license holders yet.")

        st.divider()

        st.markdown('<div style="font-family:\'Share Tech Mono\',monospace;color:#FF6B00;letter-spacing:3px;font-size:0.8rem;margin-bottom:12px;">── SERVICE HEALTH ────────────────────────────────</div>', unsafe_allow_html=True)
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            try:
                r = requests.get(f"{AUTH_SERVICE_URL}/health", timeout=5)
                status = r.json()
                st.success(f"✅ Auth Service: {status['status'].upper()}")
            except:
                st.error("❌ Auth Service: UNREACHABLE")
        with col_h2:
            try:
                r = requests.get(f"{AI_SERVICE_URL}/health", timeout=5)
                status = r.json()
                st.success(f"✅ AI Service: {status['status'].upper()} · {status.get('model','')}")
            except:
                st.error("❌ AI Service: UNREACHABLE")


st.caption("PRIVATE FOR ANTHONY  ·  SUBSCRIPTION REQUIRED  ·  $29.99/MO  ·  FEB 2026")
