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

# ── Styles ─────────────────────────────────────────────────────────────────────
from builder_styles import BUILDER_CSS, FORGE_HEADER_HTML
st.markdown(BUILDER_CSS, unsafe_allow_html=True)

# ── Key manager ────────────────────────────────────────────────────────────────
from key_manager import (
    init_db, create_license, validate_key, revoke_license,
    extend_license, get_all_licenses, save_build_entry,
    get_build_history, delete_user_data, send_welcome_email,
    run_daily_lifecycle
)

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
        f'<a href="{STRIPE_PAYMENT_URL}" target="_blank" class="stripe-btn">🔨 &nbsp; SUBSCRIBE — $29.99/MO</a>',
        unsafe_allow_html=True
    )
else:
    access_input = st.sidebar.text_input("License key or master key", type="password",
                                          placeholder="BLDR-XXXX-XXXX-XXXX")
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
                st.sidebar.success(f"✅ Welcome back{name_str}!\n{result['days_remaining']} days remaining.")
            else:
                msgs = {
                    "not_found": "Key not found. Check your email.",
                    "expired":   "License expired. Please renew.",
                    "revoked":   "Key revoked. Contact Anthony."
                }
                st.sidebar.error(msgs.get(result["status"], "Invalid key."))
                st.sidebar.markdown(
                    f'<a href="{STRIPE_PAYMENT_URL}" target="_blank" class="stripe-btn">🔨 RENEW — $29.99/MO</a>',
                    unsafe_allow_html=True
                )

    # Show current user info if logged in
    if st.session_state.authenticated and not st.session_state.is_admin and st.session_state.license_info:
        info = st.session_state.license_info
        d    = info.get("days_remaining", 0)
        color = "#4CAF50" if d > 10 else "#FF6B00" if d > 0 else "#FF4B4B"
        st.sidebar.markdown(f"""
<div style="background:rgba(255,107,0,0.05);border:1px solid rgba(255,107,0,0.2);
            border-radius:3px;padding:12px;margin-top:16px;
            font-family:'Rajdhani',sans-serif;">
    <div style="color:#888;font-size:0.75rem;letter-spacing:2px;text-transform:uppercase;">Active License</div>
    <div style="color:#C8D4E8;font-size:0.9rem;margin-top:4px;">{info.get('email','')}</div>
    <div style="color:{color};font-weight:700;font-size:1.1rem;margin-top:4px;">{d} DAYS REMAINING</div>
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
    history_str = "\n".join([e["entry"] for e in (history_entries or [])][-10:]) or "No previous builds yet."
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
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": junk_desc}
                ],
                "temperature": 0.72,
                "max_tokens": 1800
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
        uploaded_file = st.file_uploader("UPLOAD PHOTO (OPTIONAL)", type=["png","jpg","jpeg"])
        image_desc = ""
        if uploaded_file:
            st.image(uploaded_file, width=300)
            image_desc = st.text_input("PHOTO DESCRIPTION",
                                        placeholder="Rusty lawnmower engine with 4 wheels attached")

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

        # Parts counter
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
                        ts    = datetime.now().strftime("%b %d %H:%M")
                        save_build_entry(st.session_state.active_key,
                                         f"[{ts}] {project_type}: {junk[:80]}")
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
        ("🔋 Old generator + wheels",          "Tracked power rover that charges your Orange Pi 5 Plus off-grid"),
        ("⚙️ Weed eater motor + PVC",           "Mini tracked scout bot with camera mount"),
        ("🔌 Ryobi 40V battery + old box fan",  "Portable high-power USB-C station for field robotics"),
        ("🌿 Lawnmower deck + wheelchair motors","Full-size outdoor robot platform with autonomous mowing"),
        ("🎛️ Old PC PSU + Arduino",             "Bench power supply with digital voltage/current display"),
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
        # Generate key
        st.markdown("""
<div style="font-family:'Share Tech Mono',monospace;color:#FF6B00;
            letter-spacing:3px;font-size:0.8rem;margin-bottom:12px;">
    ── GENERATE LICENSE KEY ──────────────────────────
</div>
""", unsafe_allow_html=True)
        col_n, col_e = st.columns(2)
        with col_n:
            new_name = st.text_input("CUSTOMER NAME")
        with col_e:
            new_email = st.text_input("CUSTOMER EMAIL")

        if st.button("⚡ GENERATE & EMAIL KEY"):
            if new_email.strip():
                new_key = create_license(new_email.strip(), new_name.strip())
                
                # ALWAYS show key on screen
                st.markdown(f"<div class='key-box'>{new_key}</div>", unsafe_allow_html=True)
                
                try:
                    ok = send_welcome_email(new_email.strip(), new_name.strip(), new_key)
                    if ok:
                        st.success(f"✅ Key generated and emailed to {new_email}")
                    else:
                        st.warning("⚠️ Key generated — copy it above (email blocked on free tier)")
                except:
                    st.warning("⚠️ Key generated — copy it above (email blocked on free tier)")
            else:
                st.warning("Enter a customer email.")

        st.divider()

        # Manage key
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

        # All users + lifecycle + webhook (unchanged)
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
                exp_dt = datetime.fromisoformat(lic["expires_at"])
                days_left = (exp_dt - now).days
                color = "#4CAF50" if days_left > 10 else "#FF8C00" if days_left > 0 else "#FF4B4B"
                st.markdown(f"""
<div class='admin-row'>
    <strong style="color:#C8D4E8;">{lic['name'] or '(no name)'}</strong>
    <span style="color:#3A4A5C;"> — </span>
    <span style="color:#7A8BA0;">{lic['email']}</span><br/>
    <span style="color:#3A4A5C;font-size:0.8rem;font-family:'Share Tech Mono',monospace;">
        KEY:
    </span>
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

        # Stripe info (fixed URL)
        st.markdown("""
<div style="font-family:'Share Tech Mono',monospace;color:#FF6B00;
            letter-spacing:3px;font-size:0.8rem;margin-bottom:12px;">
    ── STRIPE WEBHOOK ────────────────────────────────
</div>
""", unsafe_allow_html=True)
        st.code("POST https://thebuilder-webhook.onrender.com/stripe-webhook", language="")
        st.markdown("""
Set this URL in **Stripe → Developers → Webhooks → Add endpoint**.
Listen for `checkout.session.completed`.
Set `STRIPE_WEBHOOK_SEC` env variable to the signing secret.
""")

# ── TAB 4: SAFETY ─────────────────────────────────────────────────────────────
with tab4:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### PRO TIPS & SAFETY")
    tips = [
        ("👁️ EYE PROTECTION",    "Always wear safety glasses when cutting, grinding, or running motors. Metal shards travel fast."),
        ("🔋 BATTERY SAFETY",    "Never run bare lithium cells without a BMS. Ryobi tool packs are ideal — BMS is built in. Never charge unattended."),
        ("⚡ MOTOR TESTING",     "Test all repurposed motors at 20% power first. Unknown coil resistance means unknown current draw."),
        ("🖥️ COMPUTE CHOICE",    "Orange Pi 5 Plus or Radxa Rock 5C for real robotics — they handle GPIO, PWM, and real-time control properly."),
        ("🔩 FRAME INTEGRITY",   "Measure twice, cut outside. PVC and 2x4 frames need gussets at stress points or they'll flex under load."),
        ("🌡️ HEAT MANAGEMENT",   "High-current motor controllers get hot. Mount a heatsink and always run a thermal shutoff relay."),
        ("🛡️ FAILSAFE FIRST",    "Wire a physical kill switch before anything else. Software fails; a relay doesn't."),
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

      
