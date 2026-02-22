import streamlit as st
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
MASTER_KEY = os.getenv("MASTER_KEY")

st.set_page_config(page_title="THE BUILDER — AI Engineering Forge", page_icon="⚙️", layout="wide")

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
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important; border: 1px solid #2a1500 !important;
    color: #664400 !important; font-size: 10px !important; padding: 8px 16px !important;
    clip-path: none !important; letter-spacing: 2px !important;
    margin: 8px 16px !important; width: calc(100% - 32px) !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    border-color: #ff6600 !important; color: #ff6600 !important;
    box-shadow: none !important; background: rgba(255,100,0,0.04) !important;
}

/* ── INPUTS ── */
.stTextArea textarea, .stTextInput input {
    background: #0c0c0c !important; border: 1px solid #2a1500 !important;
    border-radius: 0 !important; color: #e8d5b0 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 13px !important; padding: 16px !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: #ff6600 !important;
    box-shadow: 0 0 0 1px rgba(255,100,0,0.15) !important;
}
.stTextArea label, .stTextInput label, .stSelectbox label {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 9px !important; letter-spacing: 3px !important;
    color: #664400 !important; text-transform: uppercase !important;
}
.stSelectbox > div > div {
    background: #0c0c0c !important; border: 1px solid #2a1500 !important;
    border-radius: 0 !important; color: #e8d5b0 !important;
    font-family: 'Share Tech Mono', monospace !important;
}

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
    background: #060606 !important; border-bottom: 1px solid #151515 !important;
    padding: 0 40px !important; gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important; color: #333 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 10px !important; letter-spacing: 3px !important;
    text-transform: uppercase !important; padding: 16px 24px !important;
    border: none !important; border-bottom: 2px solid transparent !important;
}
.stTabs [aria-selected="true"] {
    color: #ff6600 !important; border-bottom: 2px solid #ff6600 !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 40px !important; background: #060606 !important; }

/* ── ALERTS ── */
.stAlert {
    background: #0c0800 !important; border: 1px solid #2a1500 !important;
    border-radius: 0 !important; color: #c8a060 !important;
    font-family: 'Share Tech Mono', monospace !important; font-size: 11px !important;
}

/* ── MARKDOWN ── */
.stMarkdown h1,.stMarkdown h2,.stMarkdown h3 {
    font-family: 'Bebas Neue', sans-serif !important; letter-spacing: 3px !important; color: #ff8833 !important;
}
.stMarkdown p,.stMarkdown li {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 13px !important; color: #c8b890 !important; line-height: 1.8 !important;
}
.stMarkdown strong { color: #ffaa00 !important; }
.stMarkdown code {
    background: #111 !important; color: #ff8833 !important;
    border: 1px solid #222 !important; border-radius: 0 !important;
    padding: 2px 6px !important; font-family: 'Share Tech Mono', monospace !important;
}

/* ── SECTION HEADERS ── */
.sec-head { display:flex; align-items:center; gap:16px; margin-bottom:28px; }
.sec-num { font-family:'Bebas Neue',sans-serif; font-size:48px; color:#1a1a1a; line-height:1; }
.sec-title { font-family:'Bebas Neue',sans-serif; font-size:30px; color:#e8d5b0; letter-spacing:4px; }
.sec-line { flex:1; height:1px; background:linear-gradient(90deg,#2a1500,transparent); }

/* ── RIVET ── */
.rivet {
    width:9px; height:9px; border-radius:50%;
    background:radial-gradient(circle at 35% 35%, #777, #222);
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.9), 0 1px 1px rgba(255,255,255,0.07);
    display:inline-block;
}
</style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# ════════════════════════════════════════════════════════════
#   LANDING PAGE
# ════════════════════════════════════════════════════════════
def login():

    st.markdown("""
    <!-- ╔══════════════════════════════════════╗
         ║   HERO — RIVETED METAL PLATE         ║
         ╚══════════════════════════════════════╝ -->
    <div style="
        min-height:100vh;
        background:
            repeating-linear-gradient(90deg,  rgba(255,255,255,0.010) 0,rgba(255,255,255,0.010) 1px, transparent 1px,transparent 64px),
            repeating-linear-gradient(180deg, rgba(255,255,255,0.010) 0,rgba(255,255,255,0.010) 1px, transparent 1px,transparent 64px),
            linear-gradient(160deg, #100900 0%, #060606 45%, #080a04 100%);
        position:relative; overflow:hidden;
        display:flex; flex-direction:column; align-items:center;
        padding-bottom:60px;
    ">

    <!-- TOP CHROME BAR -->
    <div style="
        position:absolute;top:0;left:0;right:0;
        height:4px;
        background:linear-gradient(90deg,
            #111 0%, #555 8%, #999 15%, #ccc 20%,
            #ff6600 30%, #ffaa00 50%, #ff6600 70%,
            #ccc 80%, #999 85%, #555 92%, #111 100%);
        box-shadow:0 0 20px rgba(255,100,0,0.5), 0 2px 8px rgba(0,0,0,0.8);
    "></div>

    <!-- BOTTOM CHROME BAR -->
    <div style="
        position:absolute;bottom:0;left:0;right:0;height:3px;
        background:linear-gradient(90deg,transparent,#662200,#ff6600,#662200,transparent);
    "></div>

    <!-- LEFT EDGE PLATE -->
    <div style="
        position:absolute;left:0;top:0;bottom:0;width:28px;
        background:linear-gradient(90deg,#111,#1a1a1a,#0a0a0a);
        border-right:1px solid #2a2a2a;
    ">
        <div style="position:absolute;top:30px;left:50%;transform:translateX(-50%);width:10px;height:10px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#888,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,0.9);"></div>
        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:10px;height:10px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#888,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,0.9);"></div>
        <div style="position:absolute;bottom:30px;left:50%;transform:translateX(-50%);width:10px;height:10px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#888,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,0.9);"></div>
    </div>

    <!-- RIGHT EDGE PLATE -->
    <div style="
        position:absolute;right:0;top:0;bottom:0;width:28px;
        background:linear-gradient(270deg,#111,#1a1a1a,#0a0a0a);
        border-left:1px solid #2a2a2a;
    ">
        <div style="position:absolute;top:30px;left:50%;transform:translateX(-50%);width:10px;height:10px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#888,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,0.9);"></div>
        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:10px;height:10px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#888,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,0.9);"></div>
        <div style="position:absolute;bottom:30px;left:50%;transform:translateX(-50%);width:10px;height:10px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#888,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,0.9);"></div>
    </div>

    <!-- BIG BACKGROUND GEARS -->
    <div style="position:absolute;right:-160px;top:-160px;font-size:560px;opacity:0.022;line-height:1;
        animation:spin 80s linear infinite;pointer-events:none;">⚙</div>
    <div style="position:absolute;left:-100px;bottom:-100px;font-size:380px;opacity:0.018;line-height:1;
        animation:spin 55s linear infinite reverse;pointer-events:none;">⚙</div>
    <div style="position:absolute;left:15%;top:30%;font-size:80px;opacity:0.015;line-height:1;
        animation:spin 30s linear infinite;pointer-events:none;">⚙</div>

    <!-- AOC3P0 TAG BAR -->
    <div style="
        width:100%;
        background:linear-gradient(90deg,#0a0a0a,#111,#0a0a0a);
        border-bottom:1px solid #1a1a1a;
        padding:10px 48px; margin-top:4px;
        display:flex; justify-content:space-between; align-items:center;
        position:relative; z-index:10;
    ">
        <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#2a2a2a;letter-spacing:3px;">
            ▸ CLASSIFIED // ENGINEERING SYSTEM
        </div>
        <div style="
            font-family:'Orbitron',sans-serif;font-size:11px;font-weight:700;
            letter-spacing:4px;color:#664400;
            border:1px solid #2a1500;padding:5px 18px;
            background:rgba(255,100,0,0.04);
            animation:flicker 8s infinite;
        ">AoC3P0 SYSTEMS</div>
        <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#2a2a2a;letter-spacing:3px;">
            EST. 2024 // ALL RIGHTS RESERVED ◂
        </div>
    </div>

    <!-- MAIN HERO CONTENT -->
    <div style="text-align:center;position:relative;z-index:10;padding:50px 60px 20px;max-width:1200px;width:100%;">

        <!-- OVERLINE -->
        <div style="font-family:'Share Tech Mono',monospace;font-size:9px;letter-spacing:8px;
            color:#442200;text-transform:uppercase;margin-bottom:20px;">
            ── AI-POWERED · ROUND TABLE ENGINEERING ──
        </div>

        <!-- MAIN TITLE -->
        <div style="
            font-family:'Bebas Neue',sans-serif;
            font-size:clamp(80px,14vw,148px);
            line-height:0.85; letter-spacing:14px;
            background:linear-gradient(180deg,#ffdd99 0%,#ff8800 35%,#cc3300 80%,#880000 100%);
            -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
            filter:drop-shadow(0 0 50px rgba(255,100,0,0.35));
            animation:flicker 12s infinite;
        ">THE<br>BUILDER</div>

        <!-- MACHINED NAMEPLATE -->
        <div style="
            display:inline-block;margin-top:16px;
            background:linear-gradient(180deg,#2a2a2a 0%,#1a1a1a 40%,#222 60%,#1a1a1a 100%);
            border-top:2px solid #555; border-bottom:2px solid #0a0a0a;
            border-left:1px solid #333; border-right:1px solid #333;
            padding:12px 56px; position:relative;
            box-shadow:0 8px 32px rgba(0,0,0,0.9),inset 0 1px 0 rgba(255,255,255,0.07),inset 0 -1px 0 rgba(0,0,0,0.5);
        ">
            <div style="position:absolute;top:6px;left:8px;width:7px;height:7px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 3px rgba(0,0,0,0.9);"></div>
            <div style="position:absolute;top:6px;right:8px;width:7px;height:7px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 3px rgba(0,0,0,0.9);"></div>
            <div style="position:absolute;bottom:6px;left:8px;width:7px;height:7px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 3px rgba(0,0,0,0.9);"></div>
            <div style="position:absolute;bottom:6px;right:8px;width:7px;height:7px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 3px rgba(0,0,0,0.9);"></div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:9px;color:#888;text-shadow:0 1px 0 rgba(255,255,255,0.08);">
                AI-POWERED ENGINEERING FORGE
            </div>
        </div>

        <!-- TAGLINE -->
        <div style="
            margin-top:36px; font-family:'Rajdhani',sans-serif;
            font-size:clamp(18px,2.8vw,28px);font-weight:600;
            color:#c89050;letter-spacing:1px;font-style:italic;
            text-shadow:0 0 30px rgba(200,144,80,0.3);
        ">"Where AI logic meets heavy metal."</div>

        <!-- HORIZONTAL DIVIDER PLATE -->
        <div style="
            display:flex;align-items:center;gap:0;margin:36px auto;max-width:700px;
        ">
            <div style="height:1px;flex:1;background:linear-gradient(90deg,transparent,#2a1500);"></div>
            <div style="
                background:linear-gradient(135deg,#1a1a1a,#222,#1a1a1a);
                border:1px solid #333;border-top:1px solid #444;
                padding:6px 20px;
                font-family:'Share Tech Mono',monospace;font-size:9px;
                color:#444;letter-spacing:4px;
                box-shadow:inset 0 1px 0 rgba(255,255,255,0.05);
                position:relative;
            ">
                <span style="position:absolute;top:4px;left:5px;width:5px;height:5px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#666,#222);"></span>
                <span style="position:absolute;top:4px;right:5px;width:5px;height:5px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#666,#222);"></span>
                ROUND TABLE ACTIVE
            </div>
            <div style="height:1px;flex:1;background:linear-gradient(90deg,#2a1500,transparent);"></div>
        </div>

        <!-- MARKETING COPY PLATE -->
        <div style="
            margin:0 auto;max-width:900px;
            background:linear-gradient(160deg,#100900,#090806,#0c0900);
            border:1px solid #2a1500;
            border-top:2px solid #3a2000;border-bottom:1px solid #0a0500;
            padding:44px 56px;position:relative;
            box-shadow:0 24px 80px rgba(0,0,0,0.9),inset 0 1px 0 rgba(255,150,0,0.05);
        ">
            <!-- PLATE RIVETS -->
            <div style="position:absolute;top:10px;left:14px;width:9px;height:9px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,0.9);"></div>
            <div style="position:absolute;top:10px;right:14px;width:9px;height:9px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,0.9);"></div>
            <div style="position:absolute;bottom:10px;left:14px;width:9px;height:9px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,0.9);"></div>
            <div style="position:absolute;bottom:10px;right:14px;width:9px;height:9px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 4px rgba(0,0,0,0.9);"></div>
            <!-- MID RIVETS -->
            <div style="position:absolute;top:50%;left:14px;transform:translateY(-50%);width:7px;height:7px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#666,#1a1a1a);box-shadow:inset 0 2px 3px rgba(0,0,0,0.9);"></div>
            <div style="position:absolute;top:50%;right:14px;transform:translateY(-50%);width:7px;height:7px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#666,#1a1a1a);box-shadow:inset 0 2px 3px rgba(0,0,0,0.9);"></div>
            <!-- ACCENT BARS -->
            <div style="position:absolute;left:0;top:15%;bottom:15%;width:3px;background:linear-gradient(180deg,transparent,#ff6600,transparent);"></div>
            <div style="position:absolute;right:0;top:15%;bottom:15%;width:3px;background:linear-gradient(180deg,transparent,#ff6600,transparent);"></div>

            <p style="font-family:'Rajdhani',sans-serif;font-size:clamp(15px,1.8vw,19px);
                font-weight:500;color:#b08050;line-height:2;letter-spacing:0.5px;text-align:center;">
                Why settle for <span style='color:#ff8833;font-weight:700;'>one AI</span> when you can have a
                <span style='color:#ff8833;font-weight:700;'>Board of Directors?</span><br>
                The Builder puts <span style='color:#ffaa00;font-weight:700;'>Gemini, Grok, and Claude</span>
                in the same room to tackle your toughest design challenges.<br><br>
                Whether we're repurposing
                <span style='color:#ff8833;'>medical X-ray tech for armor plating</span>
                or engineering <span style='color:#ff8833;'>off-road chassis for 500hp builds</span>,
                our <strong style='color:#ffcc00;'>'Round Table' logic</strong>
                ensures every bolt and wire is accounted for.<br><br>
                <span style='font-family:Share Tech Mono,monospace;font-size:13px;
                    color:#ff6600;letter-spacing:2px;'>
                    It's not just a program — it's an automated engineering department.
                </span>
            </p>
        </div>

        <!-- THREE AI BADGES -->
        <div style="display:flex;justify-content:center;gap:3px;margin-top:36px;flex-wrap:wrap;">

            <div style="
                background:linear-gradient(160deg,#131313,#1c1c1c,#111);
                border:1px solid #2a2a2a;border-top:1px solid #3a3a3a;
                padding:18px 32px;text-align:center;
                clip-path:polygon(12px 0%,100% 0%,calc(100% - 12px) 100%,0% 100%);
                box-shadow:inset 0 1px 0 rgba(255,255,255,0.04),0 8px 24px rgba(0,0,0,0.6);
                position:relative;min-width:180px;
            ">
                <div style="position:absolute;top:6px;left:16px;width:5px;height:5px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#555,#111);"></div>
                <div style="position:absolute;top:6px;right:16px;width:5px;height:5px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#555,#111);"></div>
                <div style="font-size:22px;margin-bottom:6px;">🔵</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:22px;letter-spacing:4px;color:#6699ff;">GEMINI</div>
                <div style="font-family:'Share Tech Mono',monospace;font-size:8px;letter-spacing:2px;color:#333;margin-top:3px;">THE GENERAL CONTRACTOR</div>
            </div>

            <div style="
                background:linear-gradient(160deg,#131313,#1c1c1c,#111);
                border:1px solid #2a2a2a;border-top:1px solid #3a3a3a;
                padding:18px 32px;text-align:center;
                clip-path:polygon(12px 0%,100% 0%,calc(100% - 12px) 100%,0% 100%);
                box-shadow:inset 0 1px 0 rgba(255,255,255,0.04),0 8px 24px rgba(0,0,0,0.6);
                position:relative;min-width:180px;
            ">
                <div style="position:absolute;top:6px;left:16px;width:5px;height:5px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#555,#111);"></div>
                <div style="position:absolute;top:6px;right:16px;width:5px;height:5px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#555,#111);"></div>
                <div style="font-size:22px;margin-bottom:6px;">⚡</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:22px;letter-spacing:4px;color:#ff6600;">GROK</div>
                <div style="font-family:'Share Tech Mono',monospace;font-size:8px;letter-spacing:2px;color:#333;margin-top:3px;">THE SHOP FOREMAN</div>
            </div>

            <div style="
                background:linear-gradient(160deg,#131313,#1c1c1c,#111);
                border:1px solid #2a2a2a;border-top:1px solid #3a3a3a;
                padding:18px 32px;text-align:center;
                clip-path:polygon(12px 0%,100% 0%,calc(100% - 12px) 100%,0% 100%);
                box-shadow:inset 0 1px 0 rgba(255,255,255,0.04),0 8px 24px rgba(0,0,0,0.6);
                position:relative;min-width:180px;
            ">
                <div style="position:absolute;top:6px;left:16px;width:5px;height:5px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#555,#111);"></div>
                <div style="position:absolute;top:6px;right:16px;width:5px;height:5px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#555,#111);"></div>
                <div style="font-size:22px;margin-bottom:6px;">🤖</div>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:22px;letter-spacing:4px;color:#cc88ff;">CLAUDE</div>
                <div style="font-family:'Share Tech Mono',monospace;font-size:8px;letter-spacing:2px;color:#333;margin-top:3px;">THE PRECISION ENGINEER</div>
            </div>

        </div>

        <!-- BOTTOM SPEC STRIP -->
        <div style="
            display:flex;justify-content:center;gap:32px;margin-top:40px;flex-wrap:wrap;
            font-family:'Share Tech Mono',monospace;font-size:9px;letter-spacing:3px;color:#2a2a2a;
            text-transform:uppercase;
        ">
            <span>⚙ TRIPLE REDUNDANT AI</span>
            <span>//</span>
            <span>🛡 ENCRYPTED ACCESS</span>
            <span>//</span>
            <span>🗄 POSTGRESQL LOGBOOK</span>
            <span>//</span>
            <span>🔩 INDUSTRIAL GRADE</span>
        </div>

    </div>
    </div>
    """, unsafe_allow_html=True)

    # ── LOGIN BOX ──
    st.markdown("<div style='height:4px;background:#060606'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.0, 1])
    with col2:
        st.markdown("""
        <div style="
            border:1px solid #2a1500;border-top:3px solid #ff6600;
            background:linear-gradient(160deg,#0f0900,#090909);
            padding:32px 32px 8px;position:relative;
            box-shadow:0 20px 60px rgba(0,0,0,0.95),0 0 60px rgba(255,100,0,0.04);
        ">
            <div style='position:absolute;top:8px;left:10px;width:7px;height:7px;border-radius:50%;
                background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 3px rgba(0,0,0,0.9);'></div>
            <div style='position:absolute;top:8px;right:10px;width:7px;height:7px;border-radius:50%;
                background:radial-gradient(circle at 35% 35%,#777,#222);box-shadow:inset 0 2px 3px rgba(0,0,0,0.9);'></div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:9px;
                letter-spacing:4px;color:#664400;text-transform:uppercase;margin-bottom:20px;">
                // GARAGE ACCESS REQUIRED
            </div>
        </div>
        """, unsafe_allow_html=True)

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
                        headers=headers, timeout=10.0
                    )
                    if response.status_code == 200:
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.error("⛔  ACCESS DENIED — KEY NOT RECOGNIZED")
                except Exception as e:
                    st.error(f"⛔  AUTH SERVICE OFFLINE: {e}")

        st.markdown("""
        <div style="text-align:center;padding:14px 0 4px;
            font-family:'Share Tech Mono',monospace;font-size:8px;
            color:#2a1500;letter-spacing:2px;">
            NO LICENSE? CONTACT AoC3P0 SYSTEMS TO ACQUIRE ACCESS
        </div>
        """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#   MAIN DASHBOARD
# ════════════════════════════════════════════════════════════
def main_dashboard():

    with st.sidebar:
        st.markdown("""
        <div class="sidebar-header">
            <div class="sidebar-title">ANTHONY'S<br>GARAGE</div>
            <div class="sidebar-sub">AoC3P0 Builder Command Center</div>
            <div class="status-row"><div class="pulse"></div>ALL SYSTEMS OPERATIONAL</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown("""<div style='padding:8px 20px;font-family:Share Tech Mono,monospace;font-size:8px;
            letter-spacing:2px;color:#222;text-transform:uppercase;border-bottom:1px solid #0f0f0f;'>
            ACTIVE SERVICES</div>""", unsafe_allow_html=True)
        for icon, name, status in [("⚙","FORGE ENGINE","ONLINE"),("🛡","AUTH GUARD","ONLINE"),("🗄","LOGBOOK DB","ONLINE")]:
            st.markdown(f"""<div class="srv-row"><span>{icon} {name}</span><span class="srv-on">{status}</span></div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        if st.button("⏻  LOCK GARAGE"):
            st.session_state.authenticated = False
            st.rerun()

    st.markdown("""
    <div style="
        background:linear-gradient(90deg,#0a0500,#060606,#050a00);
        border-bottom:1px solid #151515;padding:20px 40px;
        display:flex;align-items:center;justify-content:space-between;
        position:relative;overflow:hidden;
    ">
        <div style="position:absolute;bottom:0;left:0;right:0;height:1px;
            background:linear-gradient(90deg,transparent,#ff6600,#ffaa00,#ff6600,transparent);"></div>
        <div>
            <div style="font-family:'Bebas Neue',sans-serif;font-size:48px;letter-spacing:8px;
                color:#ff6600;text-shadow:0 0 30px rgba(255,100,0,0.5);line-height:1;">THE FORGE</div>
            <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#442200;
                letter-spacing:4px;text-transform:uppercase;margin-top:2px;">
                AoC3P0 Systems · Round Table AI · v2.0
            </div>
        </div>
        <div style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#ff6600;
            border:1px solid #2a1500;padding:10px 18px;letter-spacing:2px;
            background:rgba(255,100,0,0.04);text-align:center;
            box-shadow:0 0 20px rgba(255,100,0,0.05);">
            🔥 GEMINI &nbsp;·&nbsp; GROK &nbsp;·&nbsp; CLAUDE<br>
            <span style='color:#333;font-size:8px;letter-spacing:1px;'>ROUND TABLE ONLINE</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["⚡  NEW BUILD", "📜  BLUEPRINT HISTORY"])

    with tab1:
        st.markdown("""<div class="sec-head"><div class="sec-num">01</div>
            <div class="sec-title">LOAD THE WORKBENCH</div><div class="sec-line"></div></div>""",
            unsafe_allow_html=True)
        junk_input = st.text_area("PARTS ON THE WORKBENCH",
            placeholder="Example: GE Aestiva 5 Anesthesia Machine, hydraulic rams, titanium plate, servo motors...",
            height=160)
        st.markdown("""<div class="sec-head" style="margin-top:28px;"><div class="sec-num">02</div>
            <div class="sec-title">SELECT BUILD TYPE</div><div class="sec-line"></div></div>""",
            unsafe_allow_html=True)
        project_type = st.selectbox("BUILD CLASSIFICATION",
            ["Combat Robot", "Shop Tool", "Hydraulic Lift", "Custom Vehicle Mod", "Industrial Machine", "Defense System"])
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
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
                            headers=headers, timeout=100.0)
                        if ai_response.status_code == 200:
                            st.markdown("""<div style='font-family:Share Tech Mono,monospace;font-size:8px;
                                letter-spacing:3px;color:#ff6600;margin-bottom:16px;
                                border-bottom:1px solid #1a1a1a;padding-bottom:10px;'>
                                ⚙ BLUEPRINT FORGED — ROUND TABLE CONSENSUS REACHED</div>""",
                                unsafe_allow_html=True)
                            st.markdown(ai_response.json()["content"])
                        else:
                            st.error(f"⛔  FORGE ERROR: {ai_response.status_code}")
                    except Exception as e:
                        st.error(f"⛔  AI ENGINE OFFLINE: {e}")

    with tab2:
        st.markdown("""<div class="sec-head"><div class="sec-num">02</div>
            <div class="sec-title">PREVIOUS BLUEPRINTS</div><div class="sec-line"></div></div>
            <div style="border:1px solid #1a0a00;border-left:3px solid #442200;padding:24px 32px;
                font-family:Share Tech Mono,monospace;font-size:11px;color:#442200;
                letter-spacing:1px;line-height:2;">
                <div style='font-size:8px;letter-spacing:3px;margin-bottom:8px;color:#222;'>LOGBOOK STATUS</div>
                DATABASE SYNC IN PROGRESS...<br>
                BUILD HISTORY WILL APPEAR HERE ONCE CONNECTED.<br>
                <span style='color:#ff6600;'>ALL BUILDS ARE BEING RECORDED TO POSTGRESQL.</span>
            </div>""", unsafe_allow_html=True)


# ── ROUTING ──
if not st.session_state.authenticated:
    login()
else:
    main_dashboard()
