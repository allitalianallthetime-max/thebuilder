



import streamlit as st
import requests
import os
import threading
from datetime import datetime

# ── Must be first ──────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="The Builder", page_icon="🔨")

# ── Config ─────────────────────────────────────────────────────────────────────
MASTER_KEY         = os.environ.get("MASTER_KEY",         "AoC3P01216")
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY",       "")
STRIPE_PAYMENT_URL = os.environ.get("STRIPE_PAYMENT_URL", "https://buy.stripe.com/dRm3cvfdb3655831rX1RC00")
APP_URL            = os.environ.get("APP_URL",            "")
RESEND_API_KEY     = os.environ.get("RESEND_API_KEY",     "")
FROM_EMAIL         = os.environ.get("FROM_EMAIL",         "The Builder <noreply@yourdomain.com>")

# ── Styles ─────────────────────────────────────────────────────────────────────
from builder_styles import BUILDER_CSS, FORGE_HEADER_HTML
st.markdown(BUILDER_CSS, unsafe_allow_html=True)

# ── Enhanced Visual Layer (app.py only — class-based selectors for reliability) ─
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Black+Ops+One&family=Rajdhani:wght@400;600;700&family=Share+Tech+Mono&display=swap');

/* ── GLOBAL ATMOSPHERE ─────────────────────────────────────────── */
html, body, .stApp, .main, section.main {
    background-color: #080C12 !important;
}

/* ── GRID + SCANLINES ──────────────────────────────────────────── */
.stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    background-image:
        linear-gradient(rgba(255,107,0,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,107,0,0.03) 1px, transparent 1px);
    background-size: 48px 48px;
    pointer-events: none;
    z-index: 0;
}

/* ── SIDEBAR ───────────────────────────────────────────────────── */
section[data-testid="stSidebar"],
.css-1d391kg, .css-6qob1r {
    background: linear-gradient(180deg, #0A0F18 0%, #080C12 100%) !important;
    border-right: 1px solid rgba(255,107,0,0.18) !important;
    box-shadow: 4px 0 32px rgba(0,0,0,0.7) !important;
}

/* ── TABS ──────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(8,12,18,0.95) !important;
    border-bottom: 1px solid rgba(255,107,0,0.2) !important;
    gap: 0 !important;
    padding: 0 8px !important;
}

.stTabs [data-baseweb="tab"] {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.72rem !important;
    letter-spacing: 2.5px !important;
    text-transform: uppercase !important;
    color: #3A5068 !important;
    background: transparent !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    padding: 14px 22px !important;
    transition: all 0.2s ease !important;
}

.stTabs [data-baseweb="tab"]:hover {
    color: #FF8C00 !important;
    background: rgba(255,107,0,0.04) !important;
}

.stTabs [aria-selected="true"] {
    color: #FF6B00 !important;
    border-bottom: 2px solid #FF6B00 !important;
    background: rgba(255,107,0,0.07) !important;
    text-shadow: 0 0 14px rgba(255,107,0,0.5) !important;
}

.stTabs [data-baseweb="tab-panel"] {
    padding-top: 8px !important;
    background: transparent !important;
}

/* ── BUTTONS ───────────────────────────────────────────────────── */
.stButton > button {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.73rem !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    border-radius: 2px !important;
    border: 1px solid rgba(255,107,0,0.35) !important;
    background: rgba(255,107,0,0.06) !important;
    color: #FF8C00 !important;
    transition: all 0.18s ease !important;
    padding: 10px 16px !important;
}

.stButton > button:hover {
    border-color: #FF6B00 !important;
    background: rgba(255,107,0,0.13) !important;
    color: #FFB04E !important;
    box-shadow: 0 0 18px rgba(255,107,0,0.22), inset 0 0 8px rgba(255,107,0,0.06) !important;
    transform: translateY(-1px) !important;
}

.stButton > button:active {
    transform: translateY(0) !important;
}

/* Primary / FORGE IT */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #B84400 0%, #FF6B00 55%, #FF9040 100%) !important;
    border: none !important;
    color: #fff !important;
    font-size: 0.9rem !important;
    letter-spacing: 3px !important;
    font-weight: 700 !important;
    text-shadow: 0 1px 6px rgba(0,0,0,0.6) !important;
    animation: forge-pulse 2.8s ease-in-out infinite !important;
    min-height: 88px !important;
    padding: 16px 12px !important;
}

.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #C85000 0%, #FF7B10 55%, #FFA060 100%) !important;
    box-shadow: 0 0 32px rgba(255,107,0,0.6), 0 4px 20px rgba(0,0,0,0.4) !important;
    transform: translateY(-2px) !important;
    animation: none !important;
}

@keyframes forge-pulse {
    0%, 100% { box-shadow: 0 0 8px rgba(255,107,0,0.35), 0 2px 14px rgba(0,0,0,0.35); }
    50%       { box-shadow: 0 0 26px rgba(255,107,0,0.6),  0 2px 18px rgba(0,0,0,0.4); }
}

/* Download */
.stDownloadButton > button {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.72rem !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    border-radius: 2px !important;
    border: 1px solid rgba(100,200,100,0.3) !important;
    background: rgba(60,140,60,0.08) !important;
    color: #7EC87E !important;
    transition: all 0.2s ease !important;
}

.stDownloadButton > button:hover {
    border-color: #7EC87E !important;
    background: rgba(60,140,60,0.16) !important;
    box-shadow: 0 0 16px rgba(100,200,100,0.22) !important;
    transform: translateY(-1px) !important;
}

/* ── INPUTS ────────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input {
    background: #0D1320 !important;
    border: 1px solid rgba(255,107,0,0.18) !important;
    border-radius: 2px !important;
    color: #C8D4E8 !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-size: 1rem !important;
    letter-spacing: 0.5px !important;
    caret-color: #FF6B00 !important;
    box-shadow: inset 0 2px 8px rgba(0,0,0,0.35) !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: rgba(255,107,0,0.5) !important;
    box-shadow: 0 0 0 2px rgba(255,107,0,0.12), inset 0 2px 8px rgba(0,0,0,0.3) !important;
    outline: none !important;
}

/* Input / select labels */
.stTextInput label,
.stTextArea label,
.stSelectbox label,
.stFileUploader label,
.stNumberInput label,
.stRadio label {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.68rem !important;
    letter-spacing: 2.5px !important;
    text-transform: uppercase !important;
    color: #50606E !important;
}

/* ── SELECTBOX ─────────────────────────────────────────────────── */
.stSelectbox > div > div {
    background: #0D1320 !important;
    border: 1px solid rgba(255,107,0,0.18) !important;
    border-radius: 2px !important;
    color: #C8D4E8 !important;
    font-family: 'Rajdhani', sans-serif !important;
}

.stSelectbox > div > div:hover {
    border-color: rgba(255,107,0,0.4) !important;
}

/* ── FILE UPLOADER ─────────────────────────────────────────────── */
.stFileUploader > section,
.stFileUploaderDropzone {
    background: rgba(13,19,32,0.7) !important;
    border: 1px dashed rgba(255,107,0,0.22) !important;
    border-radius: 3px !important;
    transition: all 0.2s !important;
}

.stFileUploader > section:hover {
    background: rgba(255,107,0,0.04) !important;
    border-color: rgba(255,107,0,0.45) !important;
}

/* ── EXPANDERS ─────────────────────────────────────────────────── */
.streamlit-expanderHeader {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.76rem !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    color: #6A7A8A !important;
    background: #0D1320 !important;
    border: 1px solid rgba(255,107,0,0.12) !important;
    border-radius: 2px !important;
    transition: all 0.2s !important;
}

.streamlit-expanderHeader:hover {
    color: #FF8C00 !important;
    border-color: rgba(255,107,0,0.3) !important;
    background: rgba(255,107,0,0.04) !important;
}

.streamlit-expanderContent {
    background: rgba(10,15,25,0.8) !important;
    border: 1px solid rgba(255,107,0,0.1) !important;
    border-top: none !important;
    border-radius: 0 0 2px 2px !important;
}

/* ── CODE & MARKDOWN ───────────────────────────────────────────── */
.stMarkdown strong {
    color: #FF8C00 !important;
}

.stMarkdown code, code {
    background: rgba(255,107,0,0.09) !important;
    border: 1px solid rgba(255,107,0,0.18) !important;
    color: #FFB060 !important;
    border-radius: 2px !important;
    font-family: 'Share Tech Mono', monospace !important;
    padding: 1px 6px !important;
}

pre {
    background: #080E1A !important;
    border: 1px solid rgba(255,107,0,0.22) !important;
    border-left: 3px solid #FF6B00 !important;
    border-radius: 0 3px 3px 0 !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.45) !important;
}

pre code {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    color: #9BCFFF !important;
}

/* ── ALERTS ────────────────────────────────────────────────────── */
.stAlert, .stSuccess, .stWarning, .stError, .stInfo {
    border-radius: 2px !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.4px !important;
    border-left-width: 3px !important;
}

/* ── DIVIDER ───────────────────────────────────────────────────── */
hr {
    border-color: rgba(255,107,0,0.12) !important;
    margin: 1.5rem 0 !important;
}

/* ── SCROLLBAR ─────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #080C12; }
::-webkit-scrollbar-thumb { background: rgba(255,107,0,0.28); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,107,0,0.55); }

/* ── CAPTION ───────────────────────────────────────────────────── */
.stCaptionContainer, .stCaption {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.64rem !important;
    letter-spacing: 3px !important;
    color: rgba(58,74,92,0.6) !important;
    text-align: center !important;
    text-transform: uppercase !important;
    border-top: 1px solid rgba(255,107,0,0.07) !important;
    padding-top: 12px !important;
    margin-top: 20px !important;
}

/* ── MAIN BLOCK PADDING ────────────────────────────────────────── */
.block-container {
    padding-top: 1rem !important;
    max-width: 1400px !important;
}

/* ── KEY BOX (post-payment + admin) ────────────────────────────── */
.key-box {
    background: linear-gradient(135deg, #0D1320, #111928) !important;
    border: 1px solid rgba(255,107,0,0.45) !important;
    border-radius: 3px !important;
    padding: 16px 24px !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 1.2rem !important;
    letter-spacing: 4px !important;
    color: #FF8C00 !important;
    text-align: center !important;
    box-shadow: 0 0 28px rgba(255,107,0,0.15), inset 0 2px 8px rgba(0,0,0,0.3) !important;
    margin: 12px 0 !important;
    user-select: all !important;
    cursor: text !important;
}

/* ── POST-PAYMENT KEY REVEAL BANNER ───────────────────────────── */
.new-key-banner {
    background: linear-gradient(135deg, rgba(255,107,0,0.12), rgba(200,68,0,0.08));
    border: 2px solid rgba(255,107,0,0.6);
    border-radius: 4px;
    padding: 28px 32px;
    margin: 0 0 24px 0;
    text-align: center;
    animation: key-reveal 0.5s ease-out, key-glow 3s ease-in-out 0.5s infinite;
    box-shadow: 0 0 40px rgba(255,107,0,0.2);
}

@keyframes key-reveal {
    from { opacity: 0; transform: translateY(-12px); }
    to   { opacity: 1; transform: translateY(0); }
}

@keyframes key-glow {
    0%, 100% { box-shadow: 0 0 20px rgba(255,107,0,0.15); }
    50%       { box-shadow: 0 0 45px rgba(255,107,0,0.35); }
}

/* ── ADMIN ROW ─────────────────────────────────────────────────── */
.admin-row {
    background: rgba(13,19,32,0.7);
    border: 1px solid rgba(255,107,0,0.1);
    border-radius: 2px;
    padding: 12px 16px;
    margin-bottom: 6px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.8rem;
    transition: all 0.18s ease;
    line-height: 1.8;
}

.admin-row:hover {
    border-color: rgba(255,107,0,0.26);
    background: rgba(255,107,0,0.03);
}

/* ── WARNING / DANGER BANNERS ──────────────────────────────────── */
.warning-banner {
    background: linear-gradient(135deg, rgba(255,107,0,0.08), rgba(255,107,0,0.04));
    border: 1px solid rgba(255,107,0,0.38);
    border-left: 4px solid #FF6B00;
    border-radius: 0 3px 3px 0;
    padding: 14px 20px;
    margin-bottom: 16px;
    font-family: 'Rajdhani', sans-serif;
    color: #FFB060;
    font-size: 0.95rem;
    letter-spacing: 0.5px;
    box-shadow: 0 2px 12px rgba(255,107,0,0.1);
}

.danger-banner {
    background: linear-gradient(135deg, rgba(255,75,75,0.1), rgba(255,75,75,0.05));
    border: 1px solid rgba(255,75,75,0.4);
    border-left: 4px solid #FF4B4B;
    border-radius: 0 3px 3px 0;
    padding: 14px 20px;
    margin-bottom: 16px;
    font-family: 'Rajdhani', sans-serif;
    color: #FF9090;
    font-size: 0.95rem;
    letter-spacing: 0.5px;
    animation: danger-flash 2s ease-in-out infinite;
}

@keyframes danger-flash {
    0%, 100% { box-shadow: 0 2px 12px rgba(255,75,75,0.1); }
    50%       { box-shadow: 0 2px 22px rgba(255,75,75,0.28); }
}

/* ── STRIPE BUTTON ─────────────────────────────────────────────── */
.stripe-btn {
    display: block;
    background: linear-gradient(135deg, #B84400, #FF6B00);
    color: #fff;
    text-align: center;
    padding: 13px 20px;
    border-radius: 2px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.78rem;
    letter-spacing: 2.5px;
    text-decoration: none;
    text-transform: uppercase;
    margin-top: 10px;
    transition: all 0.2s ease;
    box-shadow: 0 4px 16px rgba(255,107,0,0.28);
}

.stripe-btn:hover {
    background: linear-gradient(135deg, #C85200, #FF7B10);
    box-shadow: 0 6px 24px rgba(255,107,0,0.48);
    transform: translateY(-1px);
    text-decoration: none;
    color: #fff;
}

</style>
""", unsafe_allow_html=True)

# ── Key manager ────────────────────────────────────────────────────────────────
from key_manager import (
    init_db, create_license, validate_key, revoke_license,
    extend_license, get_all_licenses, save_build_entry,
    get_build_history, delete_user_data,
    run_daily_lifecycle
)


# ── Email via Resend (HTTP — works on Render free tier) ───────────────────────
def send_welcome_email(to_email: str, name: str, license_key: str) -> bool:
    """Send license key email using Resend API (no SMTP needed)."""
    if not RESEND_API_KEY:
        return False
    body_html = f"""
    <div style="font-family:monospace;background:#0D1117;color:#C8D4E8;
                padding:32px;border-radius:8px;max-width:560px;margin:auto;">
        <h2 style="color:#FF6B00;letter-spacing:3px;margin-top:0;">
            🔨 THE BUILDER — LICENSE KEY
        </h2>
        <p>Hey {name or 'Boss'},</p>
        <p>Your license key is ready. Paste it into the sidebar to unlock The Builder.</p>
        <div style="background:#1C2333;border:1px solid #FF6B00;border-radius:4px;
                    padding:18px;font-size:1.3rem;letter-spacing:4px;color:#FF8C00;
                    text-align:center;margin:24px 0;">
            {license_key}
        </div>
        <p style="color:#7A8BA0;font-size:0.85rem;line-height:1.7;">
            Subscription renews monthly at $29.99.<br/>
            Reply to this email with any questions.
        </p>
        <p style="color:#FF6B00;margin-bottom:0;">Anthony, what's next boss?</p>
    </div>
    """
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "from":    FROM_EMAIL,
                "to":      [to_email],
                "subject": "🔨 Your Builder License Key",
                "html":    body_html,
            },
            timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


# ── Background lifecycle scheduler ────────────────────────────────────────────
def _start_scheduler():
    import time
    while True:
        try:
            run_daily_lifecycle(STRIPE_PAYMENT_URL)
        except Exception as e:
            print(f"[SCHEDULER ERROR] {e}")
        time.sleep(86400)

if "scheduler_started" not in st.session_state:
    threading.Thread(target=_start_scheduler, daemon=True).start()
    st.session_state.scheduler_started = True

init_db()


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
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
defaults = {
    "authenticated": False,
    "is_admin":      False,
    "license_info":  None,
    "active_key":    None,
    "current_parts": [],
    "last_result":   None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
#  POST-PAYMENT KEY REVEAL
#  Stripe webhook redirects to: APP_URL?key=BLDR-XXXX-XXXX-XXXX
#  The app detects it here and shows a hard-to-miss banner.
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
    st.sidebar.markdown("""
**Get full access for $29.99/month.**

Your license key is emailed to you instantly after payment.
""")
    st.sidebar.markdown(
        f'<a href="{STRIPE_PAYMENT_URL}" target="_blank" class="stripe-btn">'
        f'🔨 &nbsp; SUBSCRIBE — $29.99/MO</a>',
        unsafe_allow_html=True
    )
else:
    access_input = st.sidebar.text_input(
        "License key or master key",
        type="password",
        placeholder="BLDR-XXXX-XXXX-XXXX"
    )
    if st.sidebar.button("⚡ UNLOCK THE BUILDER", use_container_width=True):
        if access_input == MASTER_KEY:
            st.session_state.authenticated = True
            st.session_state.is_admin      = True
            st.sidebar.success("✅ Admin access granted.")
        else:
            result = validate_key(access_input)
            if result["valid"]:
                st.session_state.authenticated = True
                st.session_state.is_admin      = False
                st.session_state.license_info  = result
                st.session_state.active_key    = access_input
                name_str = f", {result['name']}" if result.get("name") else ""
                st.sidebar.success(
                    f"✅ Welcome back{name_str}!\n{result['days_remaining']} days remaining."
                )
            else:
                msgs = {
                    "not_found": "Key not found. Check your email.",
                    "expired":   "License expired. Please renew.",
                    "revoked":   "Key revoked. Contact Anthony."
                }
                st.sidebar.error(msgs.get(result["status"], "Invalid key."))
                st.sidebar.markdown(
                    f'<a href="{STRIPE_PAYMENT_URL}" target="_blank" class="stripe-btn">'
                    f'🔨 RENEW — $29.99/MO</a>',
                    unsafe_allow_html=True
                )

    # Show current user info if logged in
    if st.session_state.authenticated and not st.session_state.is_admin and st.session_state.license_info:
        info  = st.session_state.license_info
        d     = info.get("days_remaining", 0)
        color = "#4CAF50" if d > 10 else "#FF6B00" if d > 0 else "#FF4B4B"
        st.sidebar.markdown(f"""
<div style="background:rgba(255,107,0,0.05);border:1px solid rgba(255,107,0,0.2);
            border-radius:3px;padding:12px;margin-top:16px;
            font-family:'Rajdhani',sans-serif;">
    <div style="color:#888;font-size:0.75rem;letter-spacing:2px;text-transform:uppercase;">
        Active License
    </div>
    <div style="color:#C8D4E8;font-size:0.9rem;margin-top:4px;">{info.get('email','')}</div>
    <div style="color:{color};font-weight:700;font-size:1.1rem;margin-top:4px;">
        {d} DAYS REMAINING
    </div>
</div>
""", unsafe_allow_html=True)

    if st.session_state.is_admin:
        st.sidebar.markdown("""
<div style="background:rgba(255,107,0,0.08);border:1px solid rgba(255,107,0,0.3);
            border-radius:3px;padding:10px;margin-top:12px;
            font-family:'Share Tech Mono',monospace;color:#FF6B00;
            font-size:0.8rem;text-align:center;letter-spacing:2px;">
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
            border-top:3px solid #FF6B00;border-radius:4px;padding:40px;
            text-align:center;font-family:'Rajdhani',sans-serif;">
    <div style="font-family:'Black Ops One',cursive;color:#FF6B00;font-size:2rem;
                letter-spacing:4px;margin-bottom:12px;">🔒 ACCESS LOCKED</div>
    <div style="color:#7A8BA0;font-size:1rem;letter-spacing:1px;line-height:1.8;">
        This forge is private.<br/>
        Enter your license key in the sidebar,<br/>
        or subscribe for instant access.
    </div>
</div>
""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<a href="{STRIPE_PAYMENT_URL}" target="_blank" class="stripe-btn">'
            f'🔨 &nbsp; SUBSCRIBE NOW — $29.99/MO</a>',
            unsafe_allow_html=True
        )
        st.markdown("""
<p style="text-align:center;color:rgba(122,139,160,0.5);
          font-family:'Share Tech Mono',monospace;font-size:0.75rem;
          letter-spacing:2px;margin-top:12px;">
    KEY DELIVERED INSTANTLY TO YOUR EMAIL AFTER PAYMENT
</p>
""", unsafe_allow_html=True)
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
#  LICENSE WARNING BANNERS
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.is_admin and st.session_state.license_info:
    info      = st.session_state.license_info
    days_left = info.get("days_remaining", 999)
    status    = info.get("status", "active")

    if status == "warned_40" or days_left < 0:
        days_over   = abs(days_left)
        days_to_del = max(0, 15 - days_over)
        st.markdown(f"""
<div class="danger-banner">
    🚨 <strong>FINAL WARNING:</strong> License expired {days_over} day(s) ago.
    Build history deleted in <strong>{days_to_del} day(s)</strong> if not renewed. &nbsp;
    <a href="{STRIPE_PAYMENT_URL}" style="color:#FF4B4B;font-weight:700;text-decoration:none;">
        → RENEW NOW — $29.99/MO
    </a>
</div>
""", unsafe_allow_html=True)
    elif status == "warned_30" or (0 <= days_left <= 10):
        st.markdown(f"""
<div class="warning-banner">
    ⚠ <strong>LICENSE EXPIRES IN {days_left} DAY(S).</strong>
    Renew to keep your build history. &nbsp;
    <a href="{STRIPE_PAYMENT_URL}" style="color:#FF6B00;font-weight:700;text-decoration:none;">
        → RENEW — $29.99/MO
    </a>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  GROQ FUNCTION
# ══════════════════════════════════════════════════════════════════════════════
def ask_the_builder(junk_desc, project_type, image_desc="", history_entries=None):
    history_str = (
        "\n".join([e["entry"] for e in (history_entries or [])][-10:])
        or "No previous builds yet."
    )
    system_prompt = f"""
You are The Builder — Anthony's gritty, no-BS self-taught garage AI that turns junk into real functional battlefield robots.

Write everything in natural, complete flowing paragraphs. Never use bullet points or short lines. Use **bold** for section headers only.

Always include these sections in order:
**PARTS ANALYSIS** — full paragraph.
**ROBOT PROJECT IDEAS** — three detailed ideas in full paragraphs.
**BEST ROBOT BUILD** — the strongest idea in flowing paragraphs.
**BLUEPRINT** — clean ASCII diagram in a markdown code block.
**CONTROL CODE** — professional class-based Python using gpiozero with detailed comments.
**ADDITIONAL PARTS NEEDED** — paragraph listing cheap Home Depot parts.
**SAFETY NOTES** — practical garage safety warnings.

Past projects: {history_str}
User junk: {junk_desc}
Project focus: {project_type}
Image: {image_desc}

End every response with: "Anthony, what's next boss?"
"""
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type":  "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": junk_desc}
                ],
                "temperature": 0.72,
                "max_tokens":  1800
            }
        ).json()
        if "error" in resp:
            return f"🚨 GROQ ERROR: {resp['error']}"
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        return f"🚨 Groq error: {str(e)}"


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
            image_desc = st.text_input(
                "PHOTO DESCRIPTION",
                placeholder="Rusty lawnmower engine with 4 wheels attached"
            )

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
            font-family:'Share Tech Mono',monospace;color:#FF8C00;font-size:0.85rem;
            letter-spacing:2px;">
    ◆ &nbsp; {len(st.session_state.current_parts)} PART(S) LOADED INTO CURRENT PROJECT
</div>
""", unsafe_allow_html=True)

    with col_forge:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("FORGE IT\n🔥", use_container_width=True, type="primary"):
            if junk.strip():
                if not st.session_state.is_admin and st.session_state.license_info:
                    if st.session_state.license_info.get("days_remaining", 1) < 0:
                        st.error("License expired. Renew to keep forging.")
                        st.stop()

                with st.spinner("⚡ SPARKS FLYING... THE BUILDER IS IN THE GARAGE"):
                    history = []
                    if st.session_state.active_key:
                        history = get_build_history(st.session_state.active_key, limit=10)
                    result = ask_the_builder(junk, project_type, image_desc, history)
                    st.session_state.last_result = result
                    if st.session_state.active_key:
                        ts = datetime.now().strftime("%b %d %H:%M")
                        save_build_entry(
                            st.session_state.active_key,
                            f"[{ts}] {project_type}: {junk[:80]}"
                        )
            else:
                st.warning("Need some junk to work with, boss.")

    # ── Full-width output ──────────────────────────────────────────────────────
    if st.session_state.last_result:
        st.markdown("""
<div style="display:flex;align-items:center;gap:16px;margin:32px 0 16px;">
    <div style="flex:1;height:1px;background:linear-gradient(90deg,transparent,rgba(255,107,0,0.5));"></div>
    <div style="font-family:'Black Ops One',cursive;color:#FF6B00;letter-spacing:4px;font-size:0.9rem;">
        BUILD REPORT
    </div>
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
        entries = get_build_history(st.session_state.active_key, limit=30)
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


# ── TAB 3: EXAMPLES ───────────────────────────────────────────────────────────
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
<div style="background:var(--forge-steel,#1C2333);border:1px solid rgba(255,107,0,0.15);
            border-left:3px solid rgba(255,107,0,0.4);border-radius:0 4px 4px 0;
            padding:14px 20px;margin-bottom:8px;font-family:'Rajdhani',sans-serif;">
    <span style="color:#FF8C00;font-weight:700;">{ex_junk}</span>
    <span style="color:#3A4A5C;margin:0 10px;">→</span>
    <span style="color:#C8D4E8;">{ex_idea}</span>
</div>
""", unsafe_allow_html=True)


# ── TAB 4: SAFETY ─────────────────────────────────────────────────────────────
with tab4:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### PRO TIPS & SAFETY")
    tips = [
        ("👁️ EYE PROTECTION",  "Always wear safety glasses when cutting, grinding, or running motors. Metal shards travel fast."),
        ("🔋 BATTERY SAFETY",  "Never run bare lithium cells without a BMS. Ryobi tool packs are ideal — BMS is built in. Never charge unattended."),
        ("⚡ MOTOR TESTING",   "Test all repurposed motors at 20% power first. Unknown coil resistance means unknown current draw."),
        ("🖥️ COMPUTE CHOICE",  "Orange Pi 5 Plus or Radxa Rock 5C for real robotics — they handle GPIO, PWM, and real-time control properly."),
        ("🔩 FRAME INTEGRITY", "Measure twice, cut outside. PVC and 2x4 frames need gussets at stress points or they'll flex under load."),
        ("🌡️ HEAT MANAGEMENT", "High-current motor controllers get hot. Mount a heatsink and always run a thermal shutoff relay."),
        ("🛡️ FAILSAFE FIRST",  "Wire a physical kill switch before anything else. Software fails; a relay doesn't."),
    ]
    for icon_title, body in tips:
        st.markdown(f"""
<div style="background:#1C2333;border:1px solid rgba(255,107,0,0.12);
            border-left:3px solid rgba(255,107,0,0.5);border-radius:0 4px 4px 0;
            padding:16px 20px;margin-bottom:10px;font-family:'Rajdhani',sans-serif;">
    <div style="color:#FF8C00;font-weight:700;font-size:0.8rem;letter-spacing:3px;
                text-transform:uppercase;margin-bottom:4px;">{icon_title}</div>
    <div style="color:#C8D4E8;font-size:1rem;line-height:1.6;">{body}</div>
</div>
""", unsafe_allow_html=True)


# ── TAB 5: ADMIN ──────────────────────────────────────────────────────────────
if st.session_state.is_admin and tab_admin is not None:
    with tab_admin:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### ⚙️ ADMIN PANEL")

        # ── Generate key ──────────────────────────────────────────────────────
        st.markdown("""
<div style="font-family:'Share Tech Mono',monospace;color:#FF6B00;
            letter-spacing:3px;font-size:0.8rem;margin-bottom:12px;">
    ── GENERATE LICENSE KEY ──────────────────────────
</div>
""", unsafe_allow_html=True)

        col_n, col_e = st.columns(2)
        with col_n:
            new_name  = st.text_input("CUSTOMER NAME")
        with col_e:
            new_email = st.text_input("CUSTOMER EMAIL")

        if st.button("⚡ GENERATE & EMAIL KEY"):
            if new_email.strip():
                new_key = create_license(new_email.strip(), new_name.strip())

                # Always show the key on screen first
                st.markdown(f"<div class='key-box'>{new_key}</div>", unsafe_allow_html=True)

                # Try Resend — works on free Render tier
                try:
                    ok = send_welcome_email(new_email.strip(), new_name.strip(), new_key)
                    if ok:
                        st.success(f"✅ Key generated and emailed to {new_email}")
                    else:
                        st.warning(
                            "⚠️ Key generated — copy it above. "
                            "Email failed: check RESEND_API_KEY env var."
                        )
                except Exception as ex:
                    st.warning(f"⚠️ Key generated — copy it above. Email error: {ex}")
            else:
                st.warning("Enter a customer email.")

        st.divider()

        # ── Manage key ────────────────────────────────────────────────────────
        st.markdown("""
<div style="font-family:'Share Tech Mono',monospace;color:#FF6B00;
            letter-spacing:3px;font-size:0.8rem;margin-bottom:12px;">
    ── MANAGE A KEY ──────────────────────────────────
</div>
""", unsafe_allow_html=True)

        manage_key = st.text_input("LICENSE KEY TO MANAGE")
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            ext_days = st.number_input("EXTEND BY (DAYS)", min_value=1, max_value=365, value=30)
            if st.button("✅ EXTEND LICENSE", use_container_width=True):
                if manage_key.strip():
                    ok = extend_license(manage_key.strip(), int(ext_days))
                    st.success("Extended!") if ok else st.error("Key not found.")
                else:
                    st.warning("Enter a key.")
        with col_m2:
            rev_reason = st.text_input("REVOKE REASON")
            if st.button("🚫 REVOKE LICENSE", use_container_width=True):
                if manage_key.strip():
                    ok = revoke_license(manage_key.strip(), rev_reason)
                    st.success("Revoked.") if ok else st.error("Key not found.")
                else:
                    st.warning("Enter a key.")
        with col_m3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️ DELETE USER DATA", use_container_width=True):
                if manage_key.strip():
                    delete_user_data(manage_key.strip())
                    st.success("User data deleted.")
                else:
                    st.warning("Enter a key.")

        st.divider()

        # ── All license holders ───────────────────────────────────────────────
        st.markdown("""
<div style="font-family:'Share Tech Mono',monospace;color:#FF6B00;
            letter-spacing:3px;font-size:0.8rem;margin-bottom:12px;">
    ── ALL LICENSE HOLDERS ───────────────────────────
</div>
""", unsafe_allow_html=True)

        all_licenses = get_all_licenses()
        now = datetime.utcnow()
        if all_licenses:
            for lic in all_licenses:
                exp_dt    = datetime.fromisoformat(lic["expires_at"])
                days_left = (exp_dt - now).days
                color     = "#4CAF50" if days_left > 10 else "#FF8C00" if days_left > 0 else "#FF4B4B"
                st.markdown(f"""
<div class='admin-row'>
    <strong style="color:#C8D4E8;">{lic['name'] or '(no name)'}</strong>
    <span style="color:#3A4A5C;"> — </span>
    <span style="color:#7A8BA0;">{lic['email']}</span><br/>
    <span style="color:#3A4A5C;font-size:0.8rem;font-family:'Share Tech Mono',monospace;">KEY: </span>
    <code>{lic['key_plain']}</code>
    <span style="color:#3A4A5C;"> &nbsp;|&nbsp; </span>
    <span style="color:{color};font-weight:700;font-size:0.85rem;letter-spacing:1px;">
        {lic['status'].upper()}
    </span>
    <span style="color:#3A4A5C;"> &nbsp;|&nbsp; </span>
    <span style="color:#7A8BA0;">Expires {lic['expires_at'][:10]} ({days_left}d)</span>
    <span style="color:#3A4A5C;"> &nbsp;|&nbsp; </span>
    <span style="color:#3A4A5C;font-size:0.85rem;">Created {lic['created_at'][:10]}</span>
    {f'<br/><em style="color:#5A6A7C;">{lic["notes"]}</em>' if lic['notes'] else ''}
</div>
""", unsafe_allow_html=True)
        else:
            st.info("No license holders yet.")

        st.divider()

        # ── Lifecycle ─────────────────────────────────────────────────────────
        st.markdown("""
<div style="font-family:'Share Tech Mono',monospace;color:#FF6B00;
            letter-spacing:3px;font-size:0.8rem;margin-bottom:12px;">
    ── LIFECYCLE ─────────────────────────────────────
</div>
""", unsafe_allow_html=True)
        st.write("Normally runs every 24h. Force it now:")
        if st.button("🔄 RUN LIFECYCLE CHECK NOW"):
            with st.spinner("Checking all licenses..."):
                run_daily_lifecycle(STRIPE_PAYMENT_URL)
            st.success("Done. Warning emails sent where needed.")

        st.divider()

        # ── Stripe webhook ────────────────────────────────────────────────────
        st.markdown("""
<div style="font-family:'Share Tech Mono',monospace;color:#FF6B00;
            letter-spacing:3px;font-size:0.8rem;margin-bottom:12px;">
    ── STRIPE WEBHOOK ────────────────────────────────
</div>
""", unsafe_allow_html=True)
        st.code(f"POST {APP_URL}/stripe-webhook", language="")
        st.markdown("""
Set this URL in **Stripe → Developers → Webhooks → Add endpoint**.
Listen for `checkout.session.completed`.
Set `STRIPE_WEBHOOK_SEC` env variable to the signing secret.
""")


st.caption("PRIVATE FOR ANTHONY  ·  SUBSCRIPTION REQUIRED  ·  $29.99/MO  ·  FEB 2026")
