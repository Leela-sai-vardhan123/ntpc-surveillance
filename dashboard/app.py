"""
NTPC Smart Surveillance System
Modern SaaS Dashboard — Full Redesign v3
"""

import os, time, tempfile
import cv2, numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

def root_path(rel):
    return os.path.join(ROOT, rel)

from core.pipeline import TrafficPipeline
from utils.logger import ViolationLogger
from utils.alert import AlertSystem
from utils.stolen_vehicle_db import StolenVehicleDB
try:
    from utils.pdf_report import generate_report
    _PDF_OK = True
except Exception:
    _PDF_OK = False
try:
    from utils.excel_export import export_to_excel
    _EXCEL_OK = True
except Exception:
    _EXCEL_OK = False

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NTPC Smart Surveillance System",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
# ── Session state ─────────────────────────────────────────────────────────────
for k, v in [
    ("running", False), ("violations", []), ("frames", 0),
    ("fps_live", 0.0), ("page", "🏠 Dashboard"), ("last_violation", None),
    ("dark_mode", True),
    ("seek_frame", 0),
    ("total_frames", 0),
    ("paused", False),
    ("seek_frame", 0),
    ("total_frames", 1),
    ("video_path_cache", ""),
    ("telegram_token", ""),
    ("telegram_chat_id", ""),
    ("night_vision", "auto"),
    ("rtsp_url", ""),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Dynamic theme variables ──────────────────────────────────────────────────
if st.session_state.dark_mode:
    BG        = "#050911"
    BG2       = "#070d1e"
    BG3       = "#0a1628"
    CARD_BG   = "linear-gradient(135deg,#0a1628,#0d1e38)"
    BORDER    = "#1a3a6a30"
    BORDER2   = "#1a3a6a50"
    TEXT_PRI  = "#4db8ff"
    TEXT_SEC  = "#6688aa"
    TEXT_DIM  = "#334466"
    TEXT_BODY = "#8899bb"
    SIDEBAR   = "linear-gradient(180deg,#070d1e,#0a1228)"
    SIDEBAR_B = "#ffffff0a"
    NAV_ACT   = "linear-gradient(90deg,#0d2d6020,#1a4a9020)"
    HERO_BG   = "linear-gradient(135deg,#070e20,#0c1a38 50%,#071428)"
    BTN_BG    = "linear-gradient(135deg,#0a2d60,#0d3d80)"
    BTN_HOV   = "linear-gradient(135deg,#0d3870,#1050a0)"
    PROG_BG   = "#0a1628"
    FOOT_BOR  = "#1a3a6a20"
    INPUT_BG  = "#0a1628"
    METRIC_BG = "#0a1628"
    PILL_LIVE_BG = "#0a2a1a"; PILL_LIVE_C = "#22dd88"; PILL_LIVE_B = "#22dd8840"
    PILL_STOP_BG = "#2a0a0a"; PILL_STOP_C = "#ff6644"; PILL_STOP_B = "#ff664440"
    PILL_IDLE_BG = "#0a1020"; PILL_IDLE_C = "#4466aa"; PILL_IDLE_B = "#2244aa30"
    PILL_DONE_BG = "#0a1a2a"; PILL_DONE_C = "#4db8ff"; PILL_DONE_B = "#2266aa40"
    VBANNER_BG = "linear-gradient(90deg,#2a050820,#1a000540)"
    VBANNER_B  = "#ff224430"
    VBANNER_C  = "#ff8899"
    KPI_CARD   = "linear-gradient(135deg,#0a1628,#0d1e38)"
    SCROLLBAR  = "#1a3a6a"
    DOT_ANIM   = "pulse"
else:
    BG        = "#f0f4f8"
    BG2       = "#ffffff"
    BG3       = "#e8edf5"
    CARD_BG   = "linear-gradient(135deg,#ffffff,#f5f8ff)"
    BORDER    = "#c8d8ea60"
    BORDER2   = "#c8d8ea90"
    TEXT_PRI  = "#1a6abf"
    TEXT_SEC  = "#4466aa"
    TEXT_DIM  = "#889aaa"
    TEXT_BODY = "#334455"
    SIDEBAR   = "linear-gradient(180deg,#e8eef8,#dce6f4)"
    SIDEBAR_B = "#c8d8ea40"
    NAV_ACT   = "linear-gradient(90deg,#dbeafe80,#bfdbfe80)"
    HERO_BG   = "linear-gradient(135deg,#dbeafe,#eff6ff 50%,#dbeafe)"
    BTN_BG    = "linear-gradient(135deg,#1a6abf,#2277cc)"
    BTN_HOV   = "linear-gradient(135deg,#1558a8,#1a6abf)"
    PROG_BG   = "#dce6f4"
    FOOT_BOR  = "#c8d8ea40"
    INPUT_BG  = "#ffffff"
    METRIC_BG = "#ffffff"
    PILL_LIVE_BG = "#dcfce7"; PILL_LIVE_C = "#16a34a"; PILL_LIVE_B = "#16a34a40"
    PILL_STOP_BG = "#fee2e2"; PILL_STOP_C = "#dc2626"; PILL_STOP_B = "#dc262640"
    PILL_IDLE_BG = "#f1f5f9"; PILL_IDLE_C = "#64748b"; PILL_IDLE_B = "#64748b30"
    PILL_DONE_BG = "#dbeafe"; PILL_DONE_C = "#1a6abf"; PILL_DONE_B = "#1a6abf40"
    VBANNER_BG = "linear-gradient(90deg,#fee2e280,#fecaca50)"
    VBANNER_B  = "#f8717140"
    VBANNER_C  = "#991b1b"
    KPI_CARD   = "linear-gradient(135deg,#ffffff,#f5f8ff)"
    SCROLLBAR  = "#c8d8ea"
    DOT_ANIM   = "pulse"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Inter:wght@300;400;500;600&display=swap');

/* ── Base ── */
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: {BG}; }}
.block-container {{ padding: 1.5rem 2rem 2rem; }}
p, div, span, label {{ color: {TEXT_BODY}; }}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {{
    background: {SIDEBAR};
    border-right: 1px solid {SIDEBAR_B};
}}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stSlider label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] small {{ color: {TEXT_SEC} !important; }}

/* ── Nav buttons ── */
.nav-btn {{
    display:block; width:100%; padding:10px 16px;
    margin:3px 0; border-radius:8px; cursor:pointer;
    font-size:.88rem; font-weight:500; letter-spacing:.5px;
    border:none; text-align:left; transition:all .2s;
    background:transparent; color:{TEXT_SEC};
}}
.nav-btn:hover  {{ background:{SIDEBAR_B}; color:{TEXT_PRI}; }}
.nav-btn.active {{ background:{NAV_ACT}; color:{TEXT_PRI}; border-left:3px solid {TEXT_PRI}; }}

/* ── Hero ── */
.hero {{
    background: {HERO_BG};
    border:1px solid {BORDER2}; border-radius:16px;
    padding:32px 40px; margin-bottom:24px;
    position:relative; overflow:hidden;
}}
.hero::before {{
    content:''; position:absolute; top:-50%; right:-10%;
    width:500px; height:500px; border-radius:50%;
    background:radial-gradient(circle,{TEXT_PRI}08 0%,transparent 70%);
    pointer-events:none;
}}
.hero-badge {{
    display:inline-block; background:{BG3};
    border:1px solid {BORDER2}; border-radius:20px;
    padding:4px 14px; font-size:.75rem; color:{TEXT_PRI};
    letter-spacing:1.5px; text-transform:uppercase; margin-bottom:14px;
}}
.hero h1 {{
    font-family:'Orbitron',monospace; font-size:2.2rem; font-weight:900;
    background:linear-gradient(90deg,{TEXT_PRI},{TEXT_SEC},{TEXT_PRI});
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    margin:0 0 10px; letter-spacing:2px; line-height:1.2;
}}
.hero-sub {{ color:{TEXT_SEC}; font-size:.95rem; letter-spacing:.5px; margin:0; }}
.hero-tags {{ margin-top:18px; display:flex; gap:8px; flex-wrap:wrap; }}
.tag {{
    background:{BG3}; border:1px solid {BORDER};
    border-radius:6px; padding:4px 12px;
    font-size:.75rem; color:{TEXT_SEC}; letter-spacing:.5px;
}}

/* ── KPI cards ── */
.kpi-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }}
.kpi-card {{
    background:{KPI_CARD};
    border:1px solid {BORDER}; border-radius:12px;
    padding:18px 16px; text-align:center; position:relative; overflow:hidden;
    transition:border-color .3s,box-shadow .3s;
}}
.kpi-card:hover {{ border-color:{BORDER2}; box-shadow:0 8px 32px {TEXT_PRI}12; }}
.kpi-card::after {{
    content:''; position:absolute; bottom:0; left:0; right:0;
    height:2px; border-radius:0 0 12px 12px;
}}
.kpi-card.blue::after  {{ background:linear-gradient(90deg,#0066ff,#00aaff); }}
.kpi-card.red::after   {{ background:linear-gradient(90deg,#ff2244,#ff6644); }}
.kpi-card.amber::after {{ background:linear-gradient(90deg,#ff8800,#ffcc00); }}
.kpi-card.green::after {{ background:linear-gradient(90deg,#00aa44,#00ff88); }}
.kpi-num {{
    font-family:'Orbitron',monospace; font-size:2.4rem; font-weight:700;
    line-height:1; margin-bottom:6px;
}}
.kpi-card.blue  .kpi-num {{ color:#4db8ff; }}
.kpi-card.red   .kpi-num {{ color:#ff4466; }}
.kpi-card.amber .kpi-num {{ color:#ffaa22; }}
.kpi-card.green .kpi-num {{ color:#22dd88; }}
.kpi-label {{ font-size:.72rem; color:{TEXT_SEC}; letter-spacing:1.5px; text-transform:uppercase; }}
.kpi-icon  {{ font-size:1.4rem; margin-bottom:8px; }}

/* ── Section headers ── */
.sec-hdr {{
    display:flex; align-items:center; gap:10px;
    font-family:'Orbitron',monospace; font-size:.78rem; font-weight:700;
    color:{TEXT_PRI}; letter-spacing:2.5px; text-transform:uppercase;
    border-bottom:1px solid {BORDER}; padding-bottom:10px; margin-bottom:14px;
}}
.sec-hdr .dot {{ width:8px; height:8px; border-radius:50%; background:{TEXT_PRI};
                box-shadow:0 0 8px {TEXT_PRI}; animation:pulse 2s infinite; }}
@keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.4}} }}

/* ── Status pills ── */
.pill {{ display:inline-flex; align-items:center; gap:6px;
         border-radius:20px; padding:5px 14px; font-size:.82rem; font-weight:500; }}
.pill-live {{ background:{PILL_LIVE_BG}; color:{PILL_LIVE_C}; border:1px solid {PILL_LIVE_B}; }}
.pill-stop {{ background:{PILL_STOP_BG}; color:{PILL_STOP_C}; border:1px solid {PILL_STOP_B}; }}
.pill-idle {{ background:{PILL_IDLE_BG}; color:{PILL_IDLE_C}; border:1px solid {PILL_IDLE_B}; }}
.pill-done {{ background:{PILL_DONE_BG}; color:{PILL_DONE_C}; border:1px solid {PILL_DONE_B}; }}

/* ── Violation banner ── */
.v-banner {{
    background:{VBANNER_BG}; border:1px solid {VBANNER_B}; border-radius:10px;
    padding:12px 18px; margin:8px 0;
    display:flex; align-items:center; gap:12px;
    animation:slideIn .4s ease;
}}
@keyframes slideIn {{ from{{transform:translateY(-8px);opacity:0}} to{{transform:translateY(0);opacity:1}} }}
.v-banner-icon {{ font-size:1.4rem; }}
.v-banner-text {{ color:{VBANNER_C}; font-size:.88rem; }}
.v-banner-text strong {{ color:#ff4466; }}

/* ── Glass card ── */
.glass {{
    background:{CARD_BG}; backdrop-filter:blur(10px);
    border:1px solid {BORDER}; border-radius:12px; padding:20px;
}}

/* ── Buttons ── */
.stButton > button {{
    background:{BTN_BG} !important; color:{BG2} !important;
    border:1px solid {BORDER2} !important; border-radius:8px !important;
    font-family:'Inter',sans-serif !important; font-weight:600 !important;
    letter-spacing:.5px !important; transition:all .2s !important;
    padding:8px 20px !important;
}}
.stButton > button:hover {{
    background:{BTN_HOV} !important;
    box-shadow:0 4px 20px {TEXT_PRI}20 !important;
    transform:translateY(-1px) !important;
}}

/* ── Progress bar ── */
.prog-wrap {{ background:{PROG_BG}; border-radius:6px; height:6px; overflow:hidden; margin:8px 0; }}
.prog-bar  {{ height:100%; border-radius:6px;
              background:linear-gradient(90deg,#0066ff,{TEXT_PRI});
              transition:width .5s ease; }}

/* ── Footer ── */
.footer {{
    text-align:center; padding:24px; margin-top:32px;
    border-top:1px solid {FOOT_BOR}; color:{TEXT_DIM};
    font-size:.8rem; letter-spacing:.5px;
}}
.footer a {{ color:{TEXT_SEC}; text-decoration:none; }}

/* ── Inputs ── */
.stTextInput input, .stNumberInput input {{
    background:{INPUT_BG} !important; color:{TEXT_BODY} !important;
    border-color:{BORDER2} !important;
}}

/* ── Dataframe ── */
div[data-testid="stDataFrame"] {{ border-radius:8px; overflow:hidden; }}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width:6px; height:6px; }}
::-webkit-scrollbar-track {{ background:{BG}; }}
::-webkit-scrollbar-thumb {{ background:{SCROLLBAR}; border-radius:3px; }}

/* ── Tech card ── */
.tech-card {{
    background:{BG3}; border:1px solid {BORDER};
    border-radius:10px; padding:16px 20px; margin:8px 0;
}}
.tech-card h4 {{ color:{TEXT_PRI}; font-family:'Orbitron',monospace;
                font-size:.8rem; letter-spacing:2px; margin:0 0 10px; }}
.tech-item {{ display:flex; justify-content:space-between; align-items:center;
              padding:6px 0; border-bottom:1px solid {BORDER}; color:{TEXT_SEC}; font-size:.85rem; }}
.tech-item:last-child {{ border:none; }}
.tech-badge {{ background:{BG3}; border:1px solid {BORDER2}; border-radius:4px;
               padding:2px 8px; font-size:.72rem; color:{TEXT_PRI}; }}
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:16px 0 20px; text-align:center;'>
      <div style='font-family:Orbitron,monospace; font-size:1rem; font-weight:700;
                  color:#4db8ff; letter-spacing:2px;'>🚦 NTPC SURVEILLANCE</div>
      <div style='color:#334466; font-size:.72rem; letter-spacing:1px; margin-top:4px;'>
        NTPC — SUMMER INTERNSHIP 2025</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Theme toggle
    theme_label = "🌙 Dark Mode ON" if st.session_state.dark_mode else "☀️ Light Mode ON"
    theme_color = "#4db8ff" if st.session_state.dark_mode else "#ff8c00"
    st.markdown(f"""
    <div style='margin-bottom:4px; color:{theme_color}; font-size:.75rem;
                letter-spacing:1.5px; font-weight:600;'>THEME</div>
    """, unsafe_allow_html=True)
    if st.toggle(theme_label, value=st.session_state.dark_mode, key="theme_toggle"):
        st.session_state.dark_mode = True
    else:
        st.session_state.dark_mode = False

    st.markdown("---")

    pages = ["🏠 Dashboard", "📡 Live Detection", "🎬 Upload Video", "📊 Analytics", "🚨 Stolen Vehicles", "📄 Reports", "🎯 Calibration", "ℹ️ About"]
    for p in pages:
        active = "active" if st.session_state.page == p else ""
        if st.button(p, key=f"nav_{p}", use_container_width=True):
            st.session_state.page = p

    st.markdown("---")
    st.markdown("<div style='color:#4db8ff; font-size:.75rem; letter-spacing:2px; font-weight:600; margin-bottom:10px'>⚙️ CONFIGURATION</div>", unsafe_allow_html=True)

    entry_y   = st.slider("Entry Line Y", 50, 530, 200)
    exit_y    = st.slider("Exit Line Y",  100, 535, 480)
    real_dist = st.number_input("Road Distance (m)", 1.0, 100.0, 5.0, 0.5)

    st.markdown("---")
    st.markdown("<div style='color:#4db8ff; font-size:.75rem; letter-spacing:2px; font-weight:600; margin-bottom:10px'>🧠 MODELS</div>", unsafe_allow_html=True)
    vehicle_model = st.text_input("Vehicle", root_path("models/yolov8n.pt"))
    plate_model   = st.text_input("Plate",   root_path("models/detect_license.pt"))
    helmet_model  = st.text_input("Helmet",  root_path("models/helmet_best.pt"))

    st.markdown("---")
    st.markdown("<div style='color:#4db8ff; font-size:.75rem; letter-spacing:2px; font-weight:600; margin-bottom:10px'>🔧 OPTIONS</div>", unsafe_allow_html=True)
    buzzer_on  = st.toggle("🔊 Buzzer Alert",      value=True)
    half_prec  = st.toggle("⚡ FP16 GPU",           value=False)
    night_mode = st.selectbox("🌙 Night Vision", ["auto", "always", "off"])
    camera_id  = st.text_input("Camera ID", "NTPC_CAM_01")
    st.markdown("---")
    st.markdown("<div style='color:#4db8ff;font-size:.75rem;letter-spacing:2px;font-weight:600;margin-bottom:8px'>📱 TELEGRAM</div>", unsafe_allow_html=True)
    tg_token   = st.text_input("Bot Token",  type="password", placeholder="123456:ABCdef...")
    tg_chat    = st.text_input("Chat ID",    placeholder="-100123456789")
    if st.button("Test Connection", use_container_width=True) and tg_token and tg_chat:
        try:
            from utils.telegram_alert import TelegramAlerter
            ok, msg = TelegramAlerter.test_connection(tg_token, tg_chat)
            if ok: st.success(f"✅ {msg}")
            else:  st.error(f"❌ {msg}")
        except Exception as e:
            st.error(f"Error: {e}")

    st.markdown("---")
    st.markdown("""
    <div style='color:#223344; font-size:.72rem; line-height:1.9; text-align:center;'>
      YOLOv8 · DeepSORT · EasyOCR<br>
      FastAPI · Streamlit · SQLite<br><br>
      <span style='color:#2a4466'>Built for NTPC — Summer Internship 2025</span>
    </div>
    """, unsafe_allow_html=True)

# ── Logger (shared) ───────────────────────────────────────────────────────────
logger = ViolationLogger()
TEMP_DIR = root_path("temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# ── Helper functions ──────────────────────────────────────────────────────────

def kpi_card(num, label, icon, color="blue"):
    return f"""
    <div class="kpi-card {color}">
      <div class="kpi-icon">{icon}</div>
      <div class="kpi-num">{num}</div>
      <div class="kpi-label">{label}</div>
    </div>"""

def render_kpi_row(violations, fps=0.0, total_vehicles=0):
    total    = len(violations)
    n_speed  = sum(1 for v in violations if v.get("violation_type") == "OVERSPEED")
    n_helmet = sum(1 for v in violations if v.get("violation_type") == "NO_HELMET")
    n_veh    = total_vehicles or max(total * 3, 1)
    compliance = max(0, int(100 - (n_helmet / max(n_veh, 1)) * 100))

    st.markdown(f"""
    <div class="kpi-grid">
      {kpi_card(total_vehicles or "—", "Total Vehicles", "🚗", "blue")}
      {kpi_card(total,    "Violations",        "🚨", "red"   if total   else "blue")}
      {kpi_card(n_speed,  "Overspeed",          "⚡", "amber" if n_speed else "blue")}
      {kpi_card(f"{compliance}%", "Helmet Compliance", "⛑️", "green" if compliance > 80 else "amber")}
    </div>
    """, unsafe_allow_html=True)

def render_violation_banner(v):
    vtype = v.get("violation_type", "")
    icon  = "🚨" if "SPEED" in vtype else "⛑️"
    plate = v.get("plate_text", "UNKNOWN")
    speed = f" · {v['speed']:.0f} km/h" if v.get("speed") else ""
    ts    = v.get("time", "")
    st.markdown(f"""
    <div class="v-banner">
      <div class="v-banner-icon">{icon}</div>
      <div class="v-banner-text">
        <strong>{vtype}</strong> detected ·
        Plate: <strong>{plate}</strong>{speed} · {ts}
      </div>
    </div>
    """, unsafe_allow_html=True)

def render_violations_table(violations, key="main"):
    if not violations:
        st.markdown("<div style='color:#334466; text-align:center; padding:20px; font-size:.85rem;'>No violations detected yet.</div>", unsafe_allow_html=True)
        return
    rows = []
    for v in violations[-30:][::-1]:
        vtype = v.get("violation_type", "")
        icon  = "🚨" if "SPEED" in vtype else "⛑️"
        rows.append({
            "#":         v.get("vehicle_id", ""),
            "Vehicle":   v.get("vehicle_type", "").upper(),
            "Plate":     v.get("plate_text", "UNKNOWN"),
            "Conf":      f"{v.get('plate_conf', 0):.0%}",
            "Speed":     f"{v['speed']:.0f} km/h" if v.get("speed") else "N/A",
            "Limit":     f"{v.get('speed_limit', 'N/A')} km/h",
            "Violation": f"{icon} {vtype}",
            "Date":      v.get("date", ""),
            "Time":      v.get("time", ""),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, key=f"df_{key}")

def render_charts(violations, key_suffix="x"):
    if not violations:
        st.markdown("<div style='color:#334466; text-align:center; padding:30px;'>No data yet — run detection first.</div>", unsafe_allow_html=True)
        return
    c1, c2 = st.columns(2)

    # Pie — violation types
    by_t = {}
    for v in violations:
        t = v.get("violation_type", "Other")
        by_t[t] = by_t.get(t, 0) + 1
    fig1 = go.Figure(go.Pie(
        labels=list(by_t.keys()), values=list(by_t.values()),
        hole=0.55, marker_colors=["#ff4466", "#ffaa22", "#4db8ff"],
        textfont_size=12,
    ))
    fig1.update_layout(
        title=dict(text="Violation Types", font=dict(color="#4db8ff", size=13)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#6688aa", height=280, margin=dict(t=40, b=10, l=10, r=10),
        legend=dict(font=dict(color="#6688aa")),
    )
    with c1:
        st.plotly_chart(fig1, use_container_width=True, key=f"pie_{key_suffix}")

    # Bar — vehicles per violation type
    by_veh = {}
    for v in violations:
        veh = v.get("vehicle_type", "unknown")
        by_veh[veh] = by_veh.get(veh, 0) + 1
    fig2 = go.Figure(go.Bar(
        x=list(by_veh.keys()), y=list(by_veh.values()),
        marker_color=["#4db8ff", "#ff4466", "#ffaa22", "#22dd88"][:len(by_veh)],
        text=list(by_veh.values()), textposition="outside",
        textfont=dict(color="#4db8ff"),
    ))
    fig2.update_layout(
        title=dict(text="Violations by Vehicle Type", font=dict(color="#4db8ff", size=13)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#6688aa", height=280, margin=dict(t=40, b=10, l=10, r=10),
        xaxis=dict(gridcolor="#0f2040"), yaxis=dict(gridcolor="#0f2040"),
    )
    with c2:
        st.plotly_chart(fig2, use_container_width=True, key=f"bar_{key_suffix}")

    # Speed histogram
    speeds = [v["speed"] for v in violations if v.get("speed")]
    if speeds:
        fig3 = go.Figure(go.Histogram(
            x=speeds, nbinsx=14,
            marker_color="#4db8ff", opacity=0.75,
        ))
        fig3.update_layout(
            title=dict(text="Speed Distribution (km/h)", font=dict(color="#4db8ff", size=13)),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#6688aa", height=260, margin=dict(t=40, b=10, l=10, r=10),
            xaxis=dict(gridcolor="#0f2040", title="Speed (km/h)"),
            yaxis=dict(gridcolor="#0f2040", title="Count"),
        )
        st.plotly_chart(fig3, use_container_width=True, key=f"hist_{key_suffix}")

def build_pipeline(video_path):
    hm = helmet_model if os.path.exists(helmet_model) else None
    return TrafficPipeline({
        "vehicle_model":    vehicle_model,
        "plate_model":      plate_model,
        "helmet_model":     hm,
        "entry_line_y":     entry_y,
        "exit_line_y":      exit_y,
        "real_distance_m":  real_dist,
        "camera_id":        camera_id,
        "buzzer_path":      None,
        "half_precision":   half_prec,
        "night_vision":     night_mode,
        "telegram_token":   tg_token  if tg_token  else None,
        "telegram_chat_id": tg_chat   if tg_chat   else None,
        "perspective":      1.2,
        "plate_conf":       0.20,   # lower threshold = more plate detections
    })

# ── Page: Dashboard ───────────────────────────────────────────────────────────

def page_dashboard():
    # Hero
    st.markdown("""
    <div class="hero">
      <div class="hero-badge">🔴 LIVE SYSTEM · NTPC — SUMMER INTERNSHIP 2025</div>
      <h1>NTPC SMART<br>SURVEILLANCE SYSTEM</h1>
      <p class="hero-sub">
        Real-time vehicle detection · Speed estimation · License plate OCR · Helmet violation detection · Automated evidence logging — NTPC Summer Internship 2025
      </p>
      <div class="hero-tags">
        <span class="tag">YOLOv8</span>
        <span class="tag">DeepSORT</span>
        <span class="tag">EasyOCR</span>
        <span class="tag">GPU Optimized</span>
        <span class="tag">FastAPI</span>
        <span class="tag">SQLite</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # KPI row from DB
    all_v = logger.get_all()
    try:
        all_veh = logger.get_all_vehicles()
        n_veh   = len(all_veh)
    except Exception:
        n_veh = 0
    render_kpi_row(all_v, total_vehicles=n_veh)

    # Recent violations
    st.markdown('<div class="sec-hdr"><div class="dot"></div>RECENT VIOLATIONS</div>', unsafe_allow_html=True)
    if all_v:
        for v in all_v[:3]:
            render_violation_banner(v)
        st.markdown("---")
    render_violations_table(all_v[:10], key="dash")

    # Quick charts
    st.markdown('<div class="sec-hdr" style="margin-top:24px"><div class="dot"></div>ANALYTICS OVERVIEW</div>', unsafe_allow_html=True)
    render_charts(all_v, key_suffix="dashboard")

    # Download
    if all_v:
        d1, d2, d3 = st.columns([1, 1, 2])
        with d1:
            st.download_button("⬇ Violations CSV",
                pd.DataFrame(all_v).to_csv(index=False).encode(),
                "violations.csv", "text/csv", use_container_width=True)
        try:
            all_veh_data = logger.get_all_vehicles()
            if all_veh_data:
                with d2:
                    st.download_button("⬇ All Vehicles CSV",
                        pd.DataFrame(all_veh_data).to_csv(index=False).encode(),
                        "all_vehicles.csv", "text/csv", use_container_width=True)
        except Exception:
            pass

# ── Page: Live Detection ──────────────────────────────────────────────────────

def page_live():
    st.markdown('<div class="sec-hdr"><div class="dot"></div>LIVE DETECTION — WEBCAM</div>', unsafe_allow_html=True)

    feed_col, info_col = st.columns([3, 2], gap="medium")

    with feed_col:
        feed_ph   = st.empty()
        status_ph = st.empty()

    with info_col:
        st.markdown('<div class="sec-hdr">📊 LIVE METRICS</div>', unsafe_allow_html=True)
        k1, k2 = st.columns(2)
        k3, k4 = st.columns(2)
        kpi_total_ph  = k1.empty()
        kpi_speed_ph  = k2.empty()
        kpi_helmet_ph = k3.empty()
        kpi_fps_ph    = k4.empty()
        st.markdown('<div class="sec-hdr" style="margin-top:16px">🚨 LIVE VIOLATIONS</div>', unsafe_allow_html=True)
        table_ph = st.empty()

    c1, c2, _ = st.columns([1, 1, 3])
    with c1: start_btn = st.button("▶ START WEBCAM", use_container_width=True)
    with c2: stop_btn  = st.button("⏹ STOP",         use_container_width=True)

    def upd_kpis(violations, fps):
        total   = len(violations)
        n_speed = sum(1 for v in violations if v.get("violation_type") == "OVERSPEED")
        n_helm  = sum(1 for v in violations if v.get("violation_type") == "NO_HELMET")
        for ph, val, lbl, col in [
            (kpi_total_ph,  total,         "VIOLATIONS", "red"   if total   else "blue"),
            (kpi_speed_ph,  n_speed,       "OVERSPEED",  "amber" if n_speed else "blue"),
            (kpi_helmet_ph, n_helm,        "NO HELMET",  "amber" if n_helm  else "blue"),
            (kpi_fps_ph,    f"{fps:.1f}",  "FPS",        "green" if fps > 10 else "amber"),
        ]:
            ph.markdown(kpi_card(val, lbl, "", col) .replace('class="kpi-card', 'style="margin:4px 0" class="kpi-card'),
                        unsafe_allow_html=True)

    IDLE = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(IDLE, "WEBCAM — PRESS START", (60, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (30, 100, 200), 2)
    feed_ph.image(IDLE, channels="BGR", use_container_width=True)

    if start_btn:
        st.session_state.running    = True
        st.session_state.violations = []
        st.session_state.frames     = 0

        pipeline = build_pipeline(0)
        cap      = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 15)
        fps = cap.get(cv2.CAP_PROP_FPS) or 15
        pipeline.init_speed_estimator(fps)
        t_last = time.time()

        while st.session_state.running:
            for _ in range(3): cap.grab()
            ret, frame = cap.read()
            if not ret: break

            frame = cv2.resize(frame, (960, 540))
            annotated, new_v = pipeline.process_frame(frame)
            st.session_state.violations.extend(new_v)
            st.session_state.frames += 1

            now = time.time()
            st.session_state.fps_live = 1.0 / max(now - t_last, 1e-6)
            t_last = now

            feed_ph.image(annotated, channels="BGR", use_container_width=True)

            if new_v:
                st.session_state.last_violation = new_v[-1]
                if buzzer_on:
                    AlertSystem().trigger(
                        new_v[-1].get("vehicle_id", 0),
                        new_v[-1].get("violation_type", ""),
                        new_v[-1].get("plate_text", ""),
                        new_v[-1].get("speed"),
                    )

            if st.session_state.frames % 8 == 0:
                upd_kpis(st.session_state.violations, st.session_state.fps_live)
                with table_ph.container():
                    render_violations_table(st.session_state.violations, key="live")

            status_ph.markdown(
                f'<span class="pill pill-live">● LIVE</span> &nbsp; '
                f'Frame <b>{st.session_state.frames}</b> &nbsp;|&nbsp; '
                f'Violations <b>{len(st.session_state.violations)}</b> &nbsp;|&nbsp; '
                f'FPS <b>{st.session_state.fps_live:.1f}</b>',
                unsafe_allow_html=True,
            )

        cap.release()
        st.session_state.running = False
        status_ph.markdown('<span class="pill pill-stop">⏹ STOPPED</span>', unsafe_allow_html=True)

    elif stop_btn:
        st.session_state.running = False

# ── Page: Upload Video ────────────────────────────────────────────────────────

def page_upload():
    st.markdown('<div class="sec-hdr"><div class="dot"></div>VIDEO PROCESSING</div>', unsafe_allow_html=True)

    # Upload area
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    input_mode = st.radio("Input Source", ["Upload Video File", "Sample Video from Project", "RTSP / IP Camera"],
                          horizontal=True, label_visibility="collapsed")

    video_path = None
    if input_mode == "Upload Video File":
        up = st.file_uploader("Drop your video here",
                              type=["mp4", "avi", "mov"],
                              help="MP4, AVI, MOV supported · Max 200MB")
        if up:
            save_path = os.path.join(TEMP_DIR, up.name)
            with open(save_path, "wb") as f:
                f.write(up.read())
            video_path = save_path
            st.success(f"✅ Loaded: {up.name} ({up.size // 1024} KB)")
    elif input_mode == "Sample Video from Project":
        vids = [f for f in os.listdir(ROOT) if f.endswith((".mp4", ".avi", ".mov"))]
        if vids:
            sel = st.selectbox("Select sample video", vids)
            video_path = os.path.join(ROOT, sel)
        else:
            st.warning("No video files found in project root folder.")
    else:
        rtsp = st.text_input("RTSP URL", placeholder="rtsp://username:password@192.168.1.100:554/stream")
        if rtsp:
            video_path = rtsp
            st.success(f"RTSP stream set: {rtsp[:40]}...")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    # Controls row
    c1, c2, c3, c4, _ = st.columns([1, 1, 1, 1, 2])
    with c1: start_btn  = st.button("▶ START",   use_container_width=True)
    with c2: stop_btn   = st.button("⏹ STOP",    use_container_width=True)
    with c3: pause_btn  = st.button("⏸ PAUSE" if not st.session_state.paused else "▶ RESUME",
                                     use_container_width=True)
    with c4: skip_btn   = st.button("⏭ +30s",   use_container_width=True)

    # Seek bar (YouTube-style)
    seek_ph = st.empty()
    if st.session_state.total_frames > 0:
        seek_val = st.slider(
            "⏩ Seek",
            0, int(st.session_state.total_frames),
            int(st.session_state.seek_frame),
            key="seek_slider",
            help="Drag to jump to any frame"
        )
        if abs(seek_val - st.session_state.seek_frame) > 5:
            st.session_state.seek_frame = seek_val

    feed_ph      = st.empty()
    status_ph    = st.empty()
    progress_ph  = st.empty()
    metrics_ph   = st.empty()
    table_ph     = st.empty()

    IDLE = np.zeros((540, 960, 3), dtype=np.uint8)
    cv2.putText(IDLE, "UPLOAD VIDEO AND PRESS START",
                (150, 270), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (30, 100, 200), 2)
    feed_ph.image(IDLE, channels="BGR", use_container_width=True)

    # ── YouTube-style seek bar ───────────────────────────────────────────────
    if video_path and str(video_path) != st.session_state.video_path_cache:
        # New video loaded — get total frames
        _cap_info = cv2.VideoCapture(str(video_path))
        st.session_state.total_frames   = int(_cap_info.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        st.session_state.video_path_cache = str(video_path)
        st.session_state.seek_frame     = 0
        _cap_info.release()

    total_frames = st.session_state.total_frames

    # Seek bar
    seek_col1, seek_col2, seek_col3 = st.columns([0.5, 8, 1.5])
    with seek_col1:
        st.markdown("<div style='color:#4db8ff;font-size:.75rem;padding-top:8px'>SEEK</div>",
                    unsafe_allow_html=True)
    with seek_col2:
        seek_val = st.slider("", 0, max(total_frames-1, 1),
                             st.session_state.seek_frame,
                             key=f"seek_slider_{st.session_state.video_path_cache[-20:].replace(chr(92),'_').replace('/','_')}",
                             label_visibility="collapsed")
    with seek_col3:
        fps_info = 25
        if video_path:
            _c = cv2.VideoCapture(str(video_path))
            fps_info = _c.get(cv2.CAP_PROP_FPS) or 25
            _c.release()
        elapsed = seek_val / fps_info
        mins, secs = int(elapsed // 60), int(elapsed % 60)
        total_secs = total_frames / fps_info
        tmins, tsecs = int(total_secs // 60), int(total_secs % 60)
        st.markdown(
            f"<div style='color:#4db8ff;font-size:.8rem;padding-top:8px'>"
            f"{mins:02d}:{secs:02d} / {tmins:02d}:{tsecs:02d}</div>",
            unsafe_allow_html=True
        )

    # Seek changed while not running — show preview frame
    if seek_val != st.session_state.seek_frame and not st.session_state.running:
        st.session_state.seek_frame = seek_val
        if video_path:
            _cap_seek = cv2.VideoCapture(str(video_path))
            _cap_seek.set(cv2.CAP_PROP_POS_FRAMES, seek_val)
            ret_s, frame_s = _cap_seek.read()
            _cap_seek.release()
            if ret_s:
                frame_s = cv2.resize(frame_s, (960, 540))
                # Draw seek position info
                cv2.putText(frame_s,
                    f"Seek: frame {seek_val}/{total_frames}  ({mins:02d}:{secs:02d})",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 255), 2)
                feed_ph.image(frame_s, channels="BGR", use_container_width=True)

    if start_btn and video_path:
        st.session_state.running    = True
        st.session_state.violations = []
        st.session_state.frames     = 0
        # Start from seek position
        start_frame = st.session_state.seek_frame

        pipeline = build_pipeline(video_path)
        cap      = cv2.VideoCapture(str(video_path))
        fps      = cap.get(cv2.CAP_PROP_FPS) or 25

        # Jump to seek position
        if start_frame > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        pipeline.init_speed_estimator(fps)
        t_last = time.time()

        while st.session_state.running:
            ret, frame = cap.read()
            if not ret:
                status_ph.markdown('<span class="pill pill-done">✅ COMPLETE</span>',
                                    unsafe_allow_html=True)
                break

            current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            st.session_state.seek_frame = current_frame

            frame = cv2.resize(frame, (960, 540))
            annotated, new_v = pipeline.process_frame(frame)
            st.session_state.violations.extend(new_v)
            st.session_state.frames += 1

            now = time.time()
            st.session_state.fps_live = 1.0 / max(now - t_last, 1e-6)
            t_last = now

            # Progress bar with time
            pct = min(current_frame / max(total_frames, 1), 1.0)
            elapsed_s = current_frame / fps
            em, es = int(elapsed_s//60), int(elapsed_s%60)
            tm, ts2 = int((total_frames/fps)//60), int((total_frames/fps)%60)

            progress_ph.markdown(f"""
            <div style="margin:6px 0 10px">
              <div style="display:flex;justify-content:space-between;
                          color:#446688;font-size:.78rem;margin-bottom:4px">
                <span>Frame {current_frame} / {total_frames}</span>
                <span>{em:02d}:{es:02d} / {tm:02d}:{ts2:02d} &nbsp; {pct:.0%}</span>
              </div>
              <div class="prog-wrap">
                <div class="prog-bar" style="width:{pct*100:.1f}%"></div>
              </div>
            </div>""", unsafe_allow_html=True)

            feed_ph.image(annotated, channels="BGR", use_container_width=True)

            if new_v and buzzer_on:
                AlertSystem().trigger(
                    new_v[-1].get("vehicle_id", 0),
                    new_v[-1].get("violation_type", ""),
                    new_v[-1].get("plate_text", ""),
                    new_v[-1].get("speed"),
                )

            if st.session_state.frames % 8 == 0:
                total_v = len(st.session_state.violations)
                n_speed = sum(1 for v in st.session_state.violations if v.get("violation_type") == "OVERSPEED")
                n_helm  = sum(1 for v in st.session_state.violations if v.get("violation_type") == "NO_HELMET")
                metrics_ph.markdown(f"""
                <div style="display:flex;gap:12px;margin:8px 0">
                  <div class="kpi-card red"   style="flex:1;padding:12px">
                    <div class="kpi-num" style="font-size:1.6rem">{total_v}</div>
                    <div class="kpi-label">VIOLATIONS</div></div>
                  <div class="kpi-card amber" style="flex:1;padding:12px">
                    <div class="kpi-num" style="font-size:1.6rem">{n_speed}</div>
                    <div class="kpi-label">OVERSPEED</div></div>
                  <div class="kpi-card amber" style="flex:1;padding:12px">
                    <div class="kpi-num" style="font-size:1.6rem">{n_helm}</div>
                    <div class="kpi-label">NO HELMET</div></div>
                  <div class="kpi-card green" style="flex:1;padding:12px">
                    <div class="kpi-num" style="font-size:1.6rem">{st.session_state.fps_live:.0f}</div>
                    <div class="kpi-label">FPS</div></div>
                </div>""", unsafe_allow_html=True)
                with table_ph.container():
                    render_violations_table(st.session_state.violations, key="upload")

            status_ph.markdown(
                f'<span class="pill pill-live">● PROCESSING</span> &nbsp; '
                f'Frame <b>{current_frame}</b> &nbsp;|&nbsp; '
                f'Violations <b>{len(st.session_state.violations)}</b> &nbsp;|&nbsp; '
                f'FPS <b>{st.session_state.fps_live:.1f}</b>',
                unsafe_allow_html=True,
            )

        cap.release()
        st.session_state.running = False
        render_charts(st.session_state.violations, key_suffix="upload_done")

    elif stop_btn:
        st.session_state.running = False

# ── Page: Analytics ───────────────────────────────────────────────────────────

def page_analytics():
    st.markdown('<div class="sec-hdr"><div class="dot"></div>TRAFFIC ANALYTICS</div>', unsafe_allow_html=True)

    all_v = logger.get_all()
    try:
        all_veh = logger.get_all_vehicles()
        n_veh   = len(all_veh)
    except Exception:
        all_veh, n_veh = [], 0

    render_kpi_row(all_v, total_vehicles=n_veh)

    if not all_v:
        st.info("No violation data yet — run detection first.")
        return

    # Stats row
    stats = logger.get_stats()
    avg_speed = stats.get("avg_speed", 0)
    max_speed = max((v.get("speed") or 0 for v in all_v), default=0)

    s1, s2, s3, s4 = st.columns(4)
    for col, val, lbl in [
        (s1, len(all_v),          "Total Violations"),
        (s2, n_veh,               "Vehicles Detected"),
        (s3, f"{avg_speed} km/h", "Avg Violation Speed"),
        (s4, f"{max_speed:.0f} km/h", "Max Speed Recorded"),
    ]:
        col.metric(lbl, val)

    st.markdown("---")
    render_charts(all_v, key_suffix="analytics")

    # Violation timeline
    if len(all_v) > 1:
        st.markdown('<div class="sec-hdr" style="margin-top:16px">⏱️ VIOLATION TIMELINE</div>', unsafe_allow_html=True)
        df = pd.DataFrame(all_v)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df_hourly = df.groupby(df["timestamp"].dt.hour).size().reset_index()
            df_hourly.columns = ["Hour", "Count"]
            fig_t = px.line(df_hourly, x="Hour", y="Count",
                            title="Violations by Hour",
                            markers=True, color_discrete_sequence=["#4db8ff"])
            fig_t.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#6688aa", height=280,
                xaxis=dict(gridcolor="#0f2040"),
                yaxis=dict(gridcolor="#0f2040"),
            )
            st.plotly_chart(fig_t, use_container_width=True, key="timeline_analytics")

    # Full table
    st.markdown('<div class="sec-hdr" style="margin-top:16px">📋 COMPLETE VIOLATION LOG</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["🚨 Violations", "🚗 All Vehicles"])
    with tab1:
        render_violations_table(all_v, key="analytics_v")
    with tab2:
        if all_veh:
            vrows = [{
                "#":      r.get("vehicle_id", ""),
                "Type":   r.get("vehicle_type", "").upper(),
                "Plate":  r.get("plate_text", "UNKNOWN"),
                "Conf":   f"{r.get('plate_conf', 0):.0%}",
                "Speed":  f"{r['speed']:.0f} km/h" if r.get("speed") else "N/A",
                "Date":   r.get("date", ""),
                "Time":   r.get("time", ""),
                "Camera": r.get("camera_id", ""),
            } for r in all_veh[:100]]
            st.dataframe(pd.DataFrame(vrows), use_container_width=True, hide_index=True)
        else:
            st.info("No vehicle data yet.")

# ── Page: About ───────────────────────────────────────────────────────────────

def page_about():
    st.markdown('<div class="sec-hdr"><div class="dot"></div>ABOUT THIS PROJECT</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="hero" style="margin-bottom:20px">
      <div class="hero-badge">NTPC — SUMMER INTERNSHIP 2025</div>
      <h1 style="font-size:1.6rem">NTPC Smart<br>Surveillance System</h1>
      <p class="hero-sub">
        A production-grade computer vision system built during Summer Internship 2025 at NTPC Ltd..
        Detects traffic violations in real time using deep learning, multi-object tracking,
        and optical character recognition.
      </p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("""
        <div class="tech-card">
          <h4>🧠 AI / ML STACK</h4>
          <div class="tech-item"><span>Vehicle Detection</span><span class="tech-badge">YOLOv8n</span></div>
          <div class="tech-item"><span>Multi-Object Tracking</span><span class="tech-badge">DeepSORT</span></div>
          <div class="tech-item"><span>Plate OCR</span><span class="tech-badge">EasyOCR</span></div>
          <div class="tech-item"><span>Helmet Detection</span><span class="tech-badge">YOLOv8n</span></div>
          <div class="tech-item"><span>GPU Inference</span><span class="tech-badge">CUDA + FP16</span></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="tech-card" style="margin-top:12px">
          <h4>🌐 BACKEND</h4>
          <div class="tech-item"><span>REST API</span><span class="tech-badge">FastAPI</span></div>
          <div class="tech-item"><span>Database</span><span class="tech-badge">SQLite</span></div>
          <div class="tech-item"><span>Evidence Storage</span><span class="tech-badge">JPEG / CSV</span></div>
          <div class="tech-item"><span>CI/CD</span><span class="tech-badge">GitHub Actions</span></div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="tech-card">
          <h4>🚀 FEATURES</h4>
          <div class="tech-item"><span>Vehicle Detection</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>Speed Estimation</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>License Plate OCR</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>Helmet Detection</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>Buzzer Alerts</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>Evidence Images</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>CSV + DB Logging</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>REST API</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>Telegram Alerts</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>PDF Reports</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>Excel Export</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>Stolen Vehicle DB</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>Night Vision</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>Speed Calibration</span><span class="tech-badge">✅ Active</span></div>
          <div class="tech-item"><span>RTSP Camera</span><span class="tech-badge">✅ Active</span></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="tech-card" style="margin-top:12px">
          <h4>📊 DASHBOARD</h4>
          <div class="tech-item"><span>Framework</span><span class="tech-badge">Streamlit</span></div>
          <div class="tech-item"><span>Charts</span><span class="tech-badge">Plotly</span></div>
          <div class="tech-item"><span>Theme</span><span class="tech-badge">Cyber Dark</span></div>
          <div class="tech-item"><span>Navigation</span><span class="tech-badge">Multi-page</span></div>
        </div>
        """, unsafe_allow_html=True)

    # Footer
    st.markdown("""
    <div class="footer">
      Built with ❤️ during <strong>NTPC — Summer Internship 2025</strong> &nbsp;·&nbsp;
      Python · YOLOv8 · DeepSORT · EasyOCR · Streamlit &nbsp;·&nbsp;
      <a href="https://github.com" target="_blank">GitHub</a>
    </div>
    """, unsafe_allow_html=True)

# ── Page: Stolen Vehicles ────────────────────────────────────────────────────

def page_stolen():
    st.markdown('<div class="sec-hdr"><div class="dot"></div>🚨 STOLEN VEHICLE DATABASE</div>', unsafe_allow_html=True)

    stolen_db = StolenVehicleDB()

    # Stats
    all_stolen  = stolen_db.get_all()
    all_alerts  = stolen_db.get_alerts()

    c1, c2 = st.columns(2)
    c1.metric("Plates in Database", len(all_stolen))
    c2.metric("Detections This Session", len(all_alerts))

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["📋 Stolen Plates List", "🚨 Detection Alerts", "➕ Add / Remove Plate"])

    with tab1:
        if all_stolen:
            df = [{
                "Plate":    r.get("plate", ""),
                "Owner":    r.get("owner_name", "Unknown"),
                "Type":     r.get("vehicle_type", ""),
                "Reason":   r.get("reason", ""),
                "Reported": r.get("reported_date", ""),
                "Added By": r.get("added_by", ""),
            } for r in all_stolen]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No plates in database.")

    with tab2:
        if all_alerts:
            for a in all_alerts[:20]:
                st.markdown(f"""
                <div class="v-banner">
                  <div class="v-banner-icon">🚨</div>
                  <div class="v-banner-text">
                    <strong>STOLEN VEHICLE DETECTED</strong> ·
                    Plate: <strong>{a.get('plate','')}</strong> ·
                    Camera: {a.get('camera_id','')} ·
                    Time: {a.get('timestamp','')}
                  </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No stolen vehicle detections yet.")

    with tab3:
        st.markdown("**Add Plate to Stolen Database**")
        a1, a2, a3 = st.columns(3)
        new_plate = a1.text_input("License Plate", placeholder="AP09AB1234")
        new_owner = a2.text_input("Owner Name",    placeholder="John Doe")
        new_vtype = a3.selectbox("Vehicle Type", ["car","motorcycle","truck","bus","auto"])
        a4, a5 = st.columns(2)
        new_reason  = a4.selectbox("Reason", ["Stolen", "Wanted", "Blacklisted", "Expired"])
        new_addedby = a5.text_input("Added By", placeholder="Officer Name")

        if st.button("➕ Add to Database", use_container_width=True):
            if new_plate:
                ok = stolen_db.add_plate(new_plate, new_owner, new_vtype, new_reason, new_addedby)
                if ok:
                    st.success(f"✅ Plate {new_plate} added to database!")
                    st.rerun()
            else:
                st.warning("Please enter a license plate number.")

        st.markdown("---")
        st.markdown("**Remove Plate**")
        remove_plate = st.text_input("Plate to Remove", placeholder="AP09AB1234", key="remove_plate")
        if st.button("🗑️ Remove Plate", use_container_width=True):
            if remove_plate:
                stolen_db.remove_plate(remove_plate)
                st.success(f"✅ Plate {remove_plate} removed.")
                st.rerun()


# ── Page: Reports ─────────────────────────────────────────────────────────────

def page_reports():
    st.markdown('<div class="sec-hdr"><div class="dot"></div>📄 REPORTS & EXPORTS</div>', unsafe_allow_html=True)

    period = st.selectbox("Report Period", ["Today (1 day)", "Last 7 days", "Last 30 days", "All time"])
    period_map = {"Today (1 day)": 1, "Last 7 days": 7, "Last 30 days": 30, "All time": 3650}
    days = period_map[period]

    c1, c2, c3 = st.columns(3)

    # PDF Report
    with c1:
        st.markdown("""
        <div class="tech-card" style="text-align:center; padding:24px">
          <div style="font-size:2rem">📄</div>
          <h4 style="margin:8px 0">PDF REPORT</h4>
          <p style="color:#6688aa; font-size:.82rem">
            Full report with charts,<br>evidence images & stats
          </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Generate PDF", use_container_width=True, key="gen_pdf"):
            if _PDF_OK:
                with st.spinner("Generating PDF..."):
                    try:
                        path = generate_report(period_days=days)
                        with open(path, "rb") as f:
                            st.download_button(
                                "⬇ Download PDF",
                                f.read(), "violation_report.pdf",
                                "application/pdf",
                                use_container_width=True
                            )
                        st.success("✅ PDF ready!")
                    except Exception as e:
                        st.error(f"PDF failed: {e}")
            else:
                st.error("fpdf2 not installed. Run: pip install fpdf2")

    # Excel Export
    with c2:
        st.markdown("""
        <div class="tech-card" style="text-align:center; padding:24px">
          <div style="font-size:2rem">📊</div>
          <h4 style="margin:8px 0">EXCEL EXPORT</h4>
          <p style="color:#6688aa; font-size:.82rem">
            Formatted .xlsx with<br>violations + vehicles sheets
          </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Generate Excel", use_container_width=True, key="gen_xlsx"):
            if _EXCEL_OK:
                with st.spinner("Generating Excel..."):
                    try:
                        path = export_to_excel()
                        with open(path, "rb") as f:
                            st.download_button(
                                "⬇ Download Excel",
                                f.read(), "violations.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                        st.success("✅ Excel ready!")
                    except Exception as e:
                        st.error(f"Excel failed: {e}")
            else:
                st.error("openpyxl not installed. Run: pip install openpyxl")

    # CSV Export
    with c3:
        st.markdown("""
        <div class="tech-card" style="text-align:center; padding:24px">
          <div style="font-size:2rem">📋</div>
          <h4 style="margin:8px 0">CSV EXPORT</h4>
          <p style="color:#6688aa; font-size:.82rem">
            Raw CSV data for<br>further analysis
          </p>
        </div>
        """, unsafe_allow_html=True)
        all_v = logger.get_all()
        if all_v:
            st.download_button(
                "⬇ Download CSV",
                pd.DataFrame(all_v).to_csv(index=False).encode(),
                "violations.csv", "text/csv",
                use_container_width=True, key="dl_csv_reports"
            )
            try:
                all_veh = logger.get_all_vehicles()
                if all_veh:
                    st.download_button(
                        "⬇ All Vehicles CSV",
                        pd.DataFrame(all_veh).to_csv(index=False).encode(),
                        "all_vehicles.csv", "text/csv",
                        use_container_width=True, key="dl_veh_reports"
                    )
            except Exception:
                pass
        else:
            st.info("No data to export yet.")

    # Install instructions
    st.markdown("---")
    st.markdown('<div class="sec-hdr">📦 INSTALL REPORT LIBRARIES</div>', unsafe_allow_html=True)
    st.code("pip install fpdf2 openpyxl", language="bash")


# ── Page: Speed Calibration Wizard ────────────────────────────────────────────

def page_calibration():
    st.markdown('<div class="sec-hdr"><div class="dot"></div>🎯 SPEED CALIBRATION WIZARD</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="glass" style="margin-bottom:20px">
      <h4 style="color:#4db8ff; font-family:Orbitron,monospace; font-size:.85rem; letter-spacing:2px">
        HOW SPEED ESTIMATION WORKS
      </h4>
      <p style="color:#6688aa; font-size:.88rem; line-height:1.8">
        The system draws two virtual lines across the road (Entry and Exit).
        When a vehicle crosses the Entry line, a timer starts.
        When it crosses the Exit line, the timer stops.
        Speed = Real Distance ÷ Time taken.
      </p>
    </div>
    """, unsafe_allow_html=True)

    # Upload reference frame
    st.markdown('<div class="sec-hdr">STEP 1 — Upload a frame from your camera</div>', unsafe_allow_html=True)
    ref_img = st.file_uploader("Upload a screenshot/frame from your camera",
                                type=["jpg","jpeg","png"],
                                help="Take a screenshot of your video and upload it here")

    if ref_img:
        import tempfile
        from PIL import Image as PILImage
        img = PILImage.open(ref_img)
        img_arr = np.array(img)
        if len(img_arr.shape) == 3 and img_arr.shape[2] == 3:
            img_bgr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = img_arr

        h, w = img_bgr.shape[:2]
        st.markdown(f'<div class="sec-hdr">STEP 2 — Set line positions (Image: {w}×{h}px)</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            cal_entry = st.slider("Entry Line Y position", 0, h-1, h//3,
                                   help="Drag to position the ENTRY line on the road")
        with col2:
            cal_exit  = st.slider("Exit Line Y position",  0, h-1, (h*2)//3,
                                   help="Drag to position the EXIT line on the road")

        # Draw lines on image
        preview = img_bgr.copy()
        cv2.line(preview, (0, cal_entry), (w, cal_entry), (0, 220, 255), 3)
        cv2.putText(preview, "ENTRY", (10, cal_entry-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,220,255), 2)
        cv2.line(preview, (0, cal_exit), (w, cal_exit), (0, 0, 255), 3)
        cv2.putText(preview, "EXIT", (10, cal_exit-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

        st.image(preview, channels="BGR", use_container_width=True,
                 caption="Preview — adjust sliders to align lines with road markings")

        st.markdown('<div class="sec-hdr">STEP 3 — Enter real-world distance</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        cal_dist   = c1.number_input("Actual road distance between lines (meters)",
                                      1.0, 200.0, 10.0, 0.5)
        pixel_dist = abs(cal_exit - cal_entry)
        px_per_m   = pixel_dist / cal_dist if cal_dist > 0 else 0
        c2.metric("Pixel distance", f"{pixel_dist} px")
        c3.metric("Scale factor",   f"{px_per_m:.2f} px/m")

        st.markdown('<div class="sec-hdr">STEP 4 — Apply these settings</div>', unsafe_allow_html=True)
        st.success(f"""
        ✅ Copy these values to the sidebar:
        • Entry Line Y = {cal_entry}
        • Exit Line Y  = {cal_exit}
        • Road Distance = {cal_dist} meters
        """)

        # Show estimated speeds for reference
        st.markdown('<div class="sec-hdr" style="margin-top:16px">SPEED REFERENCE TABLE</div>', unsafe_allow_html=True)
        fps_val = st.number_input("Your video FPS", 1, 120, 25)
        ref_data = []
        for speed_kmh in [10, 20, 30, 40, 50, 60, 80]:
            speed_mps  = speed_kmh / 3.6
            time_sec   = cal_dist / speed_mps if speed_mps > 0 else 0
            frames_needed = time_sec * fps_val
            ref_data.append({
                "Speed (km/h)": speed_kmh,
                "Time to cross (sec)": f"{time_sec:.2f}",
                "Frames needed": f"{frames_needed:.0f}",
            })
        st.dataframe(ref_data, use_container_width=True, hide_index=True)
    else:
        st.info("Upload a camera frame above to start the calibration wizard.")
        st.markdown("""
        <div class="tech-card">
          <h4>📷 HOW TO GET A REFERENCE FRAME</h4>
          <div class="tech-item"><span>1. Run detection on your video</span><span class="tech-badge">Step 1</span></div>
          <div class="tech-item"><span>2. Pause at a frame showing the full road</span><span class="tech-badge">Step 2</span></div>
          <div class="tech-item"><span>3. Take a screenshot (Windows: Win+Shift+S)</span><span class="tech-badge">Step 3</span></div>
          <div class="tech-item"><span>4. Upload it here and set your lines</span><span class="tech-badge">Step 4</span></div>
        </div>
        """, unsafe_allow_html=True)


# ── Router ────────────────────────────────────────────────────────────────────

page = st.session_state.page

if   page == "🏠 Dashboard":      page_dashboard()
elif page == "📡 Live Detection":  page_live()
elif page == "🎬 Upload Video":    page_upload()
elif page == "📊 Analytics":       page_analytics()
elif page == "🚨 Stolen Vehicles": page_stolen()
elif page == "📄 Reports":         page_reports()
elif page == "🎯 Calibration":     page_calibration()
elif page == "ℹ️ About":            page_about()
