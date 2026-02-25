"""
builder_styles.py
=================
ALTERNATIVE style sheet for The Builder UI.
Contains a different visual theme (Black Ops One fonts, scanlines, etc.)

CURRENTLY UNUSED — app.py has its own inline CSS.

To use this instead, add to app.py after imports:
    from builder_styles import BUILDER_CSS, FORGE_HEADER_HTML
    st.markdown(BUILDER_CSS, unsafe_allow_html=True)
    st.markdown(FORGE_HEADER_HTML, unsafe_allow_html=True)

No external JS dependencies beyond Google Fonts.
"""

BUILDER_CSS = """
<style>
/* ═══════════════════════════════════════════════════════
   FONTS
═══════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Black+Ops+One&family=Rajdhani:wght@400;500;600;700&family=Share+Tech+Mono&display=swap');

/* ═══════════════════════════════════════════════════════
   ROOT VARIABLES
═══════════════════════════════════════════════════════ */
:root {
    --forge-black:    #060810;
    --forge-deep:     #0D1117;
    --forge-steel:    #141922;
    --forge-plate:    #1C2333;
    --molten-core:    #FF4500;
    --molten-bright:  #FF6B00;
    --molten-hot:     #FF8C00;
    --molten-glow:    #FFB347;
    --ember:          #FF2200;
    --spark-white:    #FFF5E0;
    --steel-text:     #C8D4E8;
    --steel-dim:      #7A8BA0;
    --weld-blue:      #00B4FF;
    --plasma-teal:    #00FFD4;
    --rivet:          #3A4A5C;
    --chrome:         #8899BB;
}

/* ═══════════════════════════════════════════════════════
   GLOBAL RESET & BASE
═══════════════════════════════════════════════════════ */
* { box-sizing: border-box; }

.stApp {
    background: var(--forge-black) !important;
    background-image:
        repeating-linear-gradient(
            0deg,
            transparent,
            transparent 39px,
            rgba(255,107,0,0.03) 39px,
            rgba(255,107,0,0.03) 40px
        ),
        repeating-linear-gradient(
            90deg,
            transparent,
            transparent 39px,
            rgba(255,107,0,0.02) 39px,
            rgba(255,107,0,0.02) 40px
        ) !important;
    font-family: 'Rajdhani', sans-serif !important;
}

/* Scanline overlay */
.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    background: repeating-linear-gradient(
        0deg,
        rgba(0,0,0,0.15) 0px,
        rgba(0,0,0,0.15) 1px,
        transparent 1px,
        transparent 3px
    );
    pointer-events: none;
    z-index: 9999;
    opacity: 0.4;
}

.block-container {
    max-width: 98% !important;
    padding: 0 3rem 3rem 3rem !important;
}

/* ═══════════════════════════════════════════════════════
   HEADER — THE BIG FORGE TITLE
═══════════════════════════════════════════════════════ */
.forge-header {
    position: relative;
    padding: 40px 0 30px;
    text-align: center;
    overflow: hidden;
}

.forge-title {
    font-family: 'Black Ops One', cursive !important;
    font-size: clamp(3rem, 8vw, 7rem) !important;
    color: transparent !important;
    background: linear-gradient(
        180deg,
        #FFF5E0 0%,
        #FFB347 20%,
        #FF6B00 50%,
        #FF2200 80%,
        #8B1A00 100%
    ) !important;
    -webkit-background-clip: text !important;
    background-clip: text !important;
    text-shadow: none !important;
    letter-spacing: 8px !important;
    margin: 0 !important;
    line-height: 1 !important;
    animation: forge-pulse 3s ease-in-out infinite;
    display: block;
}

@keyframes forge-pulse {
    0%, 100% { filter: brightness(1) drop-shadow(0 0 20px #FF6B0080); }
    50%       { filter: brightness(1.2) drop-shadow(0 0 40px #FF6B00CC); }
}

.forge-subtitle {
    font-family: 'Share Tech Mono', monospace;
    color: var(--steel-dim);
    font-size: 0.85rem;
    letter-spacing: 4px;
    text-transform: uppercase;
    margin-top: 8px;
}

.forge-divider {
    height: 2px;
    background: linear-gradient(90deg,
        transparent 0%,
        var(--molten-core) 20%,
        var(--molten-bright) 50%,
        var(--molten-core) 80%,
        transparent 100%
    );
    margin: 16px 0;
    position: relative;
    animation: divider-flow 2s linear infinite;
    background-size: 200% 100%;
}

@keyframes divider-flow {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* Corner rivets */
.forge-header::before,
.forge-header::after {
    content: '◆';
    position: absolute;
    color: var(--molten-bright);
    font-size: 0.7rem;
    top: 50%;
    opacity: 0.6;
}
.forge-header::before { left: 0; }
.forge-header::after  { right: 0; }

/* ═══════════════════════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════════════════════ */
section[data-testid="stSidebar"] {
    background: var(--forge-deep) !important;
    border-right: 1px solid rgba(255,107,0,0.2) !important;
}

section[data-testid="stSidebar"]::before {
    content: '';
    display: block;
    height: 3px;
    background: linear-gradient(90deg, var(--ember), var(--molten-bright), var(--molten-hot));
    margin-bottom: 16px;
}

section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stRadio label {
    font-family: 'Rajdhani', sans-serif !important;
    color: var(--steel-text) !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.5px;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    font-family: 'Black Ops One', cursive !important;
    color: var(--molten-bright) !important;
    letter-spacing: 2px !important;
    font-size: 1.1rem !important;
}

/* ═══════════════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    background: var(--forge-steel) !important;
    border-radius: 0 !important;
    border-bottom: 2px solid rgba(255,107,0,0.3) !important;
    gap: 0 !important;
    padding: 0 !important;
}

.stTabs [data-baseweb="tab"] {
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.9rem !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    color: var(--steel-dim) !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    padding: 14px 24px !important;
    transition: all 0.2s !important;
    position: relative;
}

.stTabs [data-baseweb="tab"]:hover {
    color: var(--molten-bright) !important;
    background: rgba(255,107,0,0.05) !important;
}

.stTabs [aria-selected="true"] {
    color: var(--molten-bright) !important;
    border-bottom: 3px solid var(--molten-bright) !important;
    background: rgba(255,107,0,0.08) !important;
}

/* ═══════════════════════════════════════════════════════
   INPUT FIELDS
═══════════════════════════════════════════════════════ */
.stTextArea textarea,
.stTextInput input,
.stSelectbox select,
div[data-baseweb="select"] > div {
    background: var(--forge-steel) !important;
    color: var(--steel-text) !important;
    border: 1px solid rgba(255,107,0,0.25) !important;
    border-radius: 4px !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.95rem !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}

.stTextArea textarea:focus,
.stTextInput input:focus {
    border-color: var(--molten-bright) !important;
    box-shadow: 0 0 0 1px var(--molten-bright),
                0 0 20px rgba(255,107,0,0.15) !important;
    outline: none !important;
}

/* Select dropdown */
div[data-baseweb="select"] > div:first-child {
    background: var(--forge-steel) !important;
    border: 1px solid rgba(255,107,0,0.25) !important;
}

div[data-baseweb="select"] svg { color: var(--molten-bright) !important; }

/* Labels */
.stTextArea label,
.stTextInput label,
.stSelectbox label,
.stFileUploader label,
div[data-testid="stWidgetLabel"] p {
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.8rem !important;
    letter-spacing: 3px !important;
    text-transform: uppercase !important;
    color: var(--molten-hot) !important;
    margin-bottom: 6px !important;
}

/* ═══════════════════════════════════════════════════════
   BUTTONS
═══════════════════════════════════════════════════════ */
.stButton > button {
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.9rem !important;
    letter-spacing: 3px !important;
    text-transform: uppercase !important;
    background: var(--forge-plate) !important;
    color: var(--molten-bright) !important;
    border: 1px solid rgba(255,107,0,0.4) !important;
    border-radius: 3px !important;
    padding: 10px 20px !important;
    transition: all 0.2s !important;
    position: relative;
    overflow: hidden;
}

.stButton > button::before {
    content: '';
    position: absolute;
    left: -100%;
    top: 0;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,107,0,0.15), transparent);
    transition: left 0.4s;
}

.stButton > button:hover {
    background: rgba(255,107,0,0.12) !important;
    border-color: var(--molten-bright) !important;
    color: var(--spark-white) !important;
    box-shadow: 0 0 20px rgba(255,107,0,0.3),
                inset 0 0 20px rgba(255,107,0,0.05) !important;
    transform: translateY(-1px) !important;
}

.stButton > button:hover::before { left: 100%; }

/* PRIMARY — FORGE IT button */
.stButton > button[kind="primary"],
.stButton > button[data-testid*="primary"] {
    background: linear-gradient(135deg, #8B1A00 0%, #CC3300 40%, #FF4500 70%, #FF6B00 100%) !important;
    color: #FFF5E0 !important;
    border: 1px solid var(--molten-hot) !important;
    font-size: 1rem !important;
    letter-spacing: 5px !important;
    padding: 14px 20px !important;
    box-shadow:
        0 0 30px rgba(255,69,0,0.5),
        0 4px 15px rgba(0,0,0,0.5),
        inset 0 1px 0 rgba(255,255,255,0.1) !important;
    animation: forge-btn-pulse 2s ease-in-out infinite;
}

@keyframes forge-btn-pulse {
    0%, 100% { box-shadow: 0 0 30px rgba(255,69,0,0.5), 0 4px 15px rgba(0,0,0,0.5); }
    50%       { box-shadow: 0 0 50px rgba(255,107,0,0.8), 0 4px 20px rgba(0,0,0,0.5), 0 0 80px rgba(255,69,0,0.3); }
}

.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) scale(1.02) !important;
    box-shadow: 0 0 60px rgba(255,69,0,0.9), 0 8px 25px rgba(0,0,0,0.6) !important;
}

/* ═══════════════════════════════════════════════════════
   FILE UPLOADER
═══════════════════════════════════════════════════════ */
[data-testid="stFileUploader"] > div {
    background: var(--forge-steel) !important;
    border: 1px dashed rgba(255,107,0,0.3) !important;
    border-radius: 4px !important;
    transition: all 0.2s !important;
}

[data-testid="stFileUploader"] > div:hover {
    border-color: var(--molten-bright) !important;
    background: rgba(255,107,0,0.04) !important;
}

[data-testid="stFileUploader"] p {
    font-family: 'Share Tech Mono', monospace !important;
    color: var(--steel-dim) !important;
    font-size: 0.85rem !important;
}

/* ═══════════════════════════════════════════════════════
   OUTPUT / MARKDOWN — THE BUILD RESULT
═══════════════════════════════════════════════════════ */
.stMarkdown {
    max-width: 100% !important;
}

.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    font-family: 'Black Ops One', cursive !important;
    color: var(--molten-bright) !important;
    letter-spacing: 3px !important;
}

.stMarkdown p {
    font-family: 'Rajdhani', sans-serif !important;
    font-size: 1.15rem !important;
    line-height: 1.85 !important;
    color: var(--steel-text) !important;
    margin-bottom: 1.5em !important;
}

.stMarkdown strong {
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important;
    color: var(--molten-hot) !important;
    letter-spacing: 2px !important;
    font-size: 0.85em !important;
    text-transform: uppercase !important;
}

.stMarkdown pre {
    background: #0A0D12 !important;
    border: 1px solid rgba(255,107,0,0.3) !important;
    border-left: 3px solid var(--molten-bright) !important;
    border-radius: 0 4px 4px 0 !important;
    padding: 28px 32px !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.9rem !important;
    color: #C8FFE0 !important;
    max-width: 100% !important;
    white-space: pre-wrap !important;
    overflow-x: auto !important;
    position: relative;
    box-shadow: inset 0 0 40px rgba(0,0,0,0.5), 0 0 20px rgba(255,107,0,0.05) !important;
}

.stMarkdown pre::before {
    content: '// BLUEPRINT';
    position: absolute;
    top: 8px;
    right: 16px;
    font-size: 0.7rem;
    color: rgba(255,107,0,0.4);
    letter-spacing: 2px;
}

.stMarkdown code {
    font-family: 'Share Tech Mono', monospace !important;
    background: rgba(255,107,0,0.1) !important;
    color: var(--molten-hot) !important;
    padding: 2px 6px !important;
    border-radius: 2px !important;
    font-size: 0.9em !important;
}

/* ═══════════════════════════════════════════════════════
   SUCCESS / INFO / WARNING ALERTS
═══════════════════════════════════════════════════════ */
[data-testid="stAlert"] {
    border-radius: 3px !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 1px !important;
}

/* Success */
div[data-testid="stAlert"][data-baseweb="notification"] {
    background: rgba(0,30,15,0.8) !important;
    border: 1px solid rgba(0,200,100,0.4) !important;
    border-left: 3px solid #00C864 !important;
}

/* ═══════════════════════════════════════════════════════
   STATUS / WARNING BANNERS (custom HTML)
═══════════════════════════════════════════════════════ */
.warning-banner {
    background: linear-gradient(135deg, rgba(40,20,0,0.9), rgba(60,30,0,0.9));
    border: 1px solid rgba(255,107,0,0.5);
    border-left: 3px solid var(--molten-bright);
    border-radius: 3px;
    padding: 16px 24px;
    color: var(--molten-glow);
    font-family: 'Rajdhani', sans-serif;
    font-size: 1rem;
    letter-spacing: 0.5px;
    margin-bottom: 16px;
    position: relative;
    overflow: hidden;
}

.warning-banner::before {
    content: '⚡';
    position: absolute;
    right: 20px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 2rem;
    opacity: 0.15;
}

.danger-banner {
    background: linear-gradient(135deg, rgba(40,0,0,0.9), rgba(60,5,5,0.9));
    border: 1px solid rgba(255,75,75,0.5);
    border-left: 3px solid #FF4B4B;
    border-radius: 3px;
    padding: 16px 24px;
    color: #FF8888;
    font-family: 'Rajdhani', sans-serif;
    font-size: 1rem;
    letter-spacing: 0.5px;
    margin-bottom: 16px;
    animation: danger-pulse 1.5s ease-in-out infinite;
}

@keyframes danger-pulse {
    0%, 100% { border-left-color: #FF4B4B; box-shadow: none; }
    50%       { border-left-color: #FF0000; box-shadow: -4px 0 20px rgba(255,0,0,0.4); }
}

/* ═══════════════════════════════════════════════════════
   KEY BOX
═══════════════════════════════════════════════════════ */
.key-box {
    background: var(--forge-black);
    border: 2px solid var(--molten-bright);
    border-radius: 4px;
    padding: 24px;
    text-align: center;
    font-family: 'Share Tech Mono', monospace;
    font-size: 1.8rem;
    letter-spacing: 6px;
    color: var(--molten-bright);
    margin: 16px 0;
    position: relative;
    box-shadow:
        0 0 40px rgba(255,107,0,0.2),
        inset 0 0 40px rgba(255,107,0,0.05);
    animation: key-glow 2s ease-in-out infinite;
}

@keyframes key-glow {
    0%, 100% { box-shadow: 0 0 40px rgba(255,107,0,0.2), inset 0 0 40px rgba(255,107,0,0.05); }
    50%       { box-shadow: 0 0 60px rgba(255,107,0,0.4), inset 0 0 60px rgba(255,107,0,0.1); }
}

/* ═══════════════════════════════════════════════════════
   ADMIN ROW
═══════════════════════════════════════════════════════ */
.admin-row {
    background: var(--forge-steel);
    border: 1px solid rgba(255,107,0,0.15);
    border-left: 3px solid rgba(255,107,0,0.4);
    border-radius: 0 4px 4px 0;
    padding: 14px 20px;
    margin-bottom: 8px;
    font-family: 'Rajdhani', sans-serif;
    color: var(--steel-text);
    transition: border-left-color 0.2s;
}

.admin-row:hover { border-left-color: var(--molten-bright); }

.admin-row code {
    font-family: 'Share Tech Mono', monospace;
    background: var(--forge-black);
    color: var(--molten-hot);
    padding: 2px 8px;
    border-radius: 2px;
    font-size: 0.85rem;
    letter-spacing: 2px;
}

/* ═══════════════════════════════════════════════════════
   EXPANDER (build history)
═══════════════════════════════════════════════════════ */
details {
    background: var(--forge-steel) !important;
    border: 1px solid rgba(255,107,0,0.2) !important;
    border-radius: 3px !important;
    margin-bottom: 6px !important;
}

details summary {
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 1px !important;
    color: var(--molten-hot) !important;
    padding: 12px 16px !important;
    cursor: pointer;
}

details[open] {
    border-color: rgba(255,107,0,0.4) !important;
}

/* ═══════════════════════════════════════════════════════
   SPINNER
═══════════════════════════════════════════════════════ */
[data-testid="stSpinner"] p {
    font-family: 'Share Tech Mono', monospace !important;
    color: var(--molten-bright) !important;
    letter-spacing: 2px !important;
}

/* ═══════════════════════════════════════════════════════
   DIVIDER
═══════════════════════════════════════════════════════ */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg,
        transparent, rgba(255,107,0,0.3), rgba(255,107,0,0.6),
        rgba(255,107,0,0.3), transparent) !important;
    margin: 2rem 0 !important;
}

/* ═══════════════════════════════════════════════════════
   CAPTION / FOOTER
═══════════════════════════════════════════════════════ */
.stCaption p {
    font-family: 'Share Tech Mono', monospace !important;
    color: rgba(122,139,160,0.5) !important;
    font-size: 0.75rem !important;
    letter-spacing: 2px !important;
    text-align: center;
}

footer { visibility: hidden; }
#MainMenu { visibility: hidden; }

/* ═══════════════════════════════════════════════════════
   SECTION LABELS / H2 H3 inside app
═══════════════════════════════════════════════════════ */
h2, h3 {
    font-family: 'Black Ops One', cursive !important;
    color: var(--molten-bright) !important;
    letter-spacing: 3px !important;
}

/* ═══════════════════════════════════════════════════════
   SCROLLBAR
═══════════════════════════════════════════════════════ */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--forge-black); }
::-webkit-scrollbar-thumb {
    background: linear-gradient(var(--molten-core), var(--molten-bright));
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: var(--molten-bright); }

/* ═══════════════════════════════════════════════════════
   SPARK ANIMATION (decorative, injected via HTML)
═══════════════════════════════════════════════════════ */
@keyframes spark-fly {
    0%   { transform: translate(0,0) scale(1); opacity: 1; }
    100% { transform: translate(var(--dx), var(--dy)) scale(0); opacity: 0; }
}

.spark {
    position: absolute;
    width: 3px;
    height: 3px;
    border-radius: 50%;
    background: var(--molten-bright);
    animation: spark-fly 0.8s ease-out forwards;
}

/* ═══════════════════════════════════════════════════════
   RADIO BUTTONS (sidebar)
═══════════════════════════════════════════════════════ */
.stRadio label {
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 600 !important;
    color: var(--steel-text) !important;
    letter-spacing: 1px !important;
}

[data-testid="stRadio"] [data-baseweb="radio"] div:first-child {
    border-color: rgba(255,107,0,0.4) !important;
}

[data-testid="stRadio"] [aria-checked="true"] [data-baseweb="radio"] div:first-child {
    background: var(--molten-bright) !important;
    border-color: var(--molten-bright) !important;
}

/* ═══════════════════════════════════════════════════════
   NUMBER INPUT
═══════════════════════════════════════════════════════ */
[data-testid="stNumberInput"] input {
    background: var(--forge-steel) !important;
    color: var(--steel-text) !important;
    border-color: rgba(255,107,0,0.25) !important;
    font-family: 'Share Tech Mono', monospace !important;
}

/* ═══════════════════════════════════════════════════════
   DOWNLOAD BUTTON
═══════════════════════════════════════════════════════ */
[data-testid="stDownloadButton"] button {
    background: var(--forge-deep) !important;
    border: 1px solid rgba(0,180,255,0.3) !important;
    color: var(--weld-blue) !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 2px !important;
    font-size: 0.85rem !important;
}

[data-testid="stDownloadButton"] button:hover {
    border-color: var(--weld-blue) !important;
    box-shadow: 0 0 20px rgba(0,180,255,0.25) !important;
    background: rgba(0,180,255,0.05) !important;
}

/* ═══════════════════════════════════════════════════════
   STRIPE LINK BUTTON (in sidebar)
═══════════════════════════════════════════════════════ */
.stripe-btn {
    display: block;
    background: linear-gradient(135deg, #8B1A00, #FF4500);
    color: #FFF5E0 !important;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 700;
    font-size: 1rem;
    letter-spacing: 3px;
    text-transform: uppercase;
    padding: 14px 20px;
    border-radius: 3px;
    text-align: center;
    text-decoration: none !important;
    margin-top: 16px;
    border: 1px solid var(--molten-hot);
    box-shadow: 0 0 30px rgba(255,69,0,0.4);
    transition: all 0.2s;
}

.stripe-btn:hover {
    box-shadow: 0 0 50px rgba(255,69,0,0.7);
    transform: translateY(-1px);
}
</style>
"""

FORGE_HEADER_HTML = """
<div class="forge-header">
    <div class="forge-title">THE BUILDER</div>
    <div class="forge-divider"></div>
    <div class="forge-subtitle">◆ &nbsp; JUNK IN &nbsp;·&nbsp; ROBOTS OUT &nbsp; ◆ &nbsp; BUILT BY ANTHONY &nbsp;·&nbsp; POWERED BY GROG THE ROG &nbsp;·&nbsp; 2026 &nbsp; ◆</div>
</div>
"""
