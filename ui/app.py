"""
app.py — Streamlit Frontend for AI Incident Root Cause Analyzer
Run: streamlit run app.py
"""

import os
import sys

# ✅ FIX FOR RENDER DEPLOYMENT
PORT = int(os.environ.get("PORT", 8501))
os.environ["STREAMLIT_SERVER_PORT"] = str(PORT)
os.environ["STREAMLIT_SERVER_ADDRESS"] = "0.0.0.0"

import json
import time
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from pathlib import Path

def hex_to_rgba(hex_color, alpha=0.05):
    if not isinstance(hex_color, str):
        return hex_color

    if hex_color.startswith("#") and len(hex_color) == 7:
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    return hex_color


st.set_page_config(
    page_title="ARCA — Incident Analyzer",
    page_icon="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>◈</text></svg>",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 🔥 IMPORTANT: make API configurable for deployment
API_URL = os.getenv("API_URL", "http://localhost:8000")

# ── (ALL YOUR EXISTING CODE CONTINUES UNCHANGED BELOW) ──

# ── DESIGN SYSTEM ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── RESET & BASE ── */
*, *::before, *::after { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: #04060d !important;
    color: #c9d1e0 !important;
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stSidebar"] {
    background: #070b14 !important;
    border-right: 1px solid #0f1929 !important;
}

[data-testid="stSidebar"] * { font-family: 'Inter', sans-serif !important; }

/* Hide default streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
.block-container { padding: 1.5rem 2rem 3rem !important; max-width: 100% !important; }

/* ── ANIMATED GRID BACKGROUND ── */
[data-testid="stAppViewContainer"]::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
        linear-gradient(rgba(0, 212, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 212, 255, 0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
    animation: gridPulse 8s ease-in-out infinite;
}

@keyframes gridPulse {
    0%, 100% { opacity: 0.6; }
    50%       { opacity: 1.0; }
}

/* ── SIDEBAR STYLING ── */
.sidebar-logo {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #00d4ff;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    padding: 0.5rem 0 1.5rem;
    border-bottom: 1px solid #0f1929;
    margin-bottom: 1.5rem;
}
.sidebar-logo .brand {
    font-size: 1.1rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.05em;
    display: block;
    margin-bottom: 0.2rem;
}
.sidebar-logo .tagline { color: #82c8ff; }

.sidebar-section {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: #7aa8c8;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    padding: 1rem 0 0.4rem;
}

.data-pill {
    background: #080e1c;
    border: 1px solid #0f1929;
    border-radius: 6px;
    padding: 0.4rem 0.7rem;
    margin-bottom: 0.3rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: #a0cfff;
    display: flex;
    justify-content: space-between;
}
.data-pill span { color: #00d4ff; }

/* ── PAGE HEADER ── */
.page-header {
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #0a1628;
    position: relative;
}
.page-header::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    width: 60px;
    height: 1px;
    background: #00d4ff;
}
.page-eyebrow {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    letter-spacing: 0.3em;
    color: #00d4ff;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.page-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.02em;
    margin: 0;
    line-height: 1.2;
}
.page-subtitle {
    font-size: 0.8rem;
    color: #b8dcff;
    margin-top: 0.3rem;
    font-family: 'JetBrains Mono', monospace;
}

/* ── STAT CARDS ── */
.stat-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 1rem; margin-bottom: 1.5rem; }

.stat-card {
    background: #070b14;
    border: 1px solid #0d1a2e;
    border-radius: 10px;
    padding: 1.1rem 1.2rem;
    position: relative;
    overflow: hidden;
    transition: border-color 0.3s;
}
.stat-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent, #00d4ff);
    opacity: 0.6;
}
.stat-card:hover { border-color: var(--accent, #00d4ff); }

.stat-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    letter-spacing: 0.2em;
    color: #2a4060;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}
.stat-value {
    font-size: 2.2rem;
    font-weight: 700;
    color: var(--accent, #ffffff);
    line-height: 1;
    font-variant-numeric: tabular-nums;
}
.stat-meta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #1e3a5f;
    margin-top: 0.4rem;
}

/* ── SIGNAL CARDS ── */
.signal-list { display: flex; flex-direction: column; gap: 0.4rem; }
.signal-item {
    background: #070b14;
    border: 1px solid #0d1a2e;
    border-left: 2px solid #00d4ff;
    border-radius: 0 6px 6px 0;
    padding: 0.55rem 0.8rem;
    font-size: 0.78rem;
    color: #b8dcff;
    font-family: 'JetBrains Mono', monospace;
    animation: slideIn 0.4s ease forwards;
    opacity: 0;
}
@keyframes slideIn {
    from { transform: translateX(-8px); opacity: 0; }
    to   { transform: translateX(0);   opacity: 1; }
}
.signal-item:nth-child(1) { animation-delay: 0.05s; }
.signal-item:nth-child(2) { animation-delay: 0.10s; }
.signal-item:nth-child(3) { animation-delay: 0.15s; }
.signal-item:nth-child(4) { animation-delay: 0.20s; }
.signal-item:nth-child(5) { animation-delay: 0.25s; }
.signal-item:nth-child(6) { animation-delay: 0.30s; }

/* ── RUN ANALYSIS SECTION ── */
.run-panel {
    background: linear-gradient(135deg, #070b14 0%, #060d1f 100%);
    border: 1px solid #0d1a2e;
    border-radius: 12px;
    padding: 1.5rem;
    margin-top: 1rem;
    position: relative;
    overflow: hidden;
}
.run-panel::before {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 120px; height: 120px;
    background: radial-gradient(circle, rgba(0,212,255,0.06) 0%, transparent 70%);
    border-radius: 50%;
}
.run-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: #ffffff;
    margin-bottom: 0.3rem;
}
.run-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #b8dcff;
}

/* ── HYPOTHESIS CARDS ── */
.hyp-primary {
    background: #050d18;
    border: 1px solid #0a2040;
    border-left: 3px solid #00d4ff;
    border-radius: 0 10px 10px 0;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
    position: relative;
    animation: fadeUp 0.5s ease forwards;
}
.hyp-alt {
    background: #050d18;
    border: 1px solid #0d1a2e;
    border-left: 3px solid #1a3a6e;
    border-radius: 0 10px 10px 0;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
}
@keyframes fadeUp {
    from { transform: translateY(10px); opacity: 0; }
    to   { transform: translateY(0);   opacity: 1; }
}
.hyp-cause {
    font-size: 0.95rem;
    font-weight: 600;
    color: #e8f4ff;
    margin-bottom: 0.5rem;
}
.hyp-conf-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #00d4ff;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.conf-track {
    background: #0a1628;
    border-radius: 2px;
    height: 4px;
    margin-bottom: 0.8rem;
    overflow: hidden;
}
.conf-fill {
    height: 4px;
    border-radius: 2px;
    background: linear-gradient(90deg, #00d4ff, #3a7bd5);
    animation: fillBar 1s ease forwards;
    width: 0%;
}
.conf-fill-alt {
    height: 4px;
    border-radius: 2px;
    background: linear-gradient(90deg, #1a3a6e, #3a7bd5);
    animation: fillBar 1s ease 0.2s forwards;
    width: 0%;
}
@keyframes fillBar {
    to { width: var(--w, 0%); }
}
.hyp-body {
    font-size: 0.78rem;
    color: #4a6a8a;
    line-height: 1.6;
}

/* ── EVIDENCE LIST ── */
.evidence-item {
    display: flex;
    gap: 0.6rem;
    padding: 0.4rem 0;
    font-size: 0.78rem;
    color: #5a7a9a;
    border-bottom: 1px solid #070e1a;
    font-family: 'JetBrains Mono', monospace;
}
.evidence-item::before {
    content: '//';
    color: #00d4ff;
    flex-shrink: 0;
    opacity: 0.5;
}

/* ── INCIDENT SUMMARY BANNER ── */
.incident-banner {
    background: #040a14;
    border: 1px solid #0d1a2e;
    border-top: 2px solid #00d4ff;
    border-radius: 0 0 10px 10px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1.5rem;
    font-size: 0.82rem;
    color: #6a8aaa;
    line-height: 1.7;
    position: relative;
}
.incident-banner .meta-row {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: #1a3a5f;
    margin-top: 0.8rem;
    display: flex;
    gap: 1.5rem;
}
.incident-banner .meta-val { color: #2a5080; }

/* ── TIMELINE ── */
.tl-container { position: relative; padding-left: 1.5rem; }
.tl-container::before {
    content: '';
    position: absolute;
    left: 6px; top: 0; bottom: 0;
    width: 1px;
    background: linear-gradient(to bottom, #00d4ff22, #00d4ff08, transparent);
}
.tl-row {
    display: flex;
    gap: 1rem;
    padding: 0.55rem 0;
    border-bottom: 1px solid #070e1a;
    position: relative;
    animation: slideIn 0.3s ease forwards;
    opacity: 0;
}
.tl-row::before {
    content: '';
    position: absolute;
    left: -1.2rem;
    top: 50%;
    transform: translateY(-50%);
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--dot-color, #1a3a5f);
    border: 1px solid var(--dot-color, #1a3a5f);
}
.tl-ts {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #1e3a5f;
    min-width: 140px;
    padding-top: 2px;
}
.tl-bar { width: 2px; background: var(--bar-color, #0d1a2e); border-radius: 1px; flex-shrink: 0; }
.tl-title { font-size: 0.8rem; color: #8aaac8; font-weight: 500; }
.tl-detail { font-size: 0.7rem; color: #2a4060; font-family: 'JetBrains Mono', monospace; margin-top: 1px; }

/* ── PHASE INDICATORS ── */
.phase-strip {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
    padding: 0.8rem 1rem;
    background: #040a14;
    border: 1px solid #0a1628;
    border-radius: 8px;
}
.phase-item {
    flex: 1;
    padding: 0.5rem 0.7rem;
    border-radius: 6px;
    border-left: 2px solid var(--pc, #1a3a5f);
    background: #060d1c;
}
.phase-name {
    font-size: 0.65rem;
    font-weight: 600;
    color: #9fb8d9;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-family: 'JetBrains Mono', monospace;
}
.phase-ts {
    font-size: 0.6rem;
    color: #9ec4e6;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 2px;
}

/* ── ACTION CARD ── */
.action-card {
    background: #040a14;
    border: 1px solid #0d1a2e;
    border-radius: 10px;
    padding: 1.3rem 1.5rem;
    margin-bottom: 1rem;
}
.action-type-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    letter-spacing: 0.2em;
    color: #00d4ff;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.action-name {
    font-size: 1.2rem;
    font-weight: 700;
    color: #e8f4ff;
    margin-bottom: 0.5rem;
}
.action-meta {
    display: flex;
    gap: 1.5rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #b8dcff;
}
.action-meta .av { color: #82c8ff; }

.step-row {
    display: flex;
    gap: 0.8rem;
    padding: 0.45rem 0;
    border-bottom: 1px solid #070e1a;
    font-size: 0.78rem;
    color: #b0c9e5;
    align-items: flex-start;
}
.step-idx {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: #00d4ff;
    min-width: 20px;
    padding-top: 2px;
    opacity: 0.6;
}

/* ── APPROVE BUTTON ZONE ── */
.approve-zone {
    background: #040a14;
    border: 1px solid #0a1628;
    border-radius: 10px;
    padding: 1.2rem 1.5rem;
    margin: 1rem 0;
    display: flex;
    gap: 1rem;
    align-items: center;
}
.approve-notice {
    font-size: 0.75rem;
    color: #1e3a5f;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1.6;
}

/* ── RECOVERY SUCCESS ── */
.recovery-banner {
    background: #020e0a;
    border: 1px solid #0a2a1a;
    border-left: 3px solid #00ff94;
    border-radius: 0 8px 8px 0;
    padding: 0.8rem 1.1rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: #00a060;
    margin-bottom: 1rem;
}

/* ── CHAT ── */
.chat-wrap {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    margin-bottom: 1rem;
}
.chat-msg-user {
    align-self: flex-end;
    background: #060d1f;
    border: 1px solid #0d1a2e;
    border-radius: 12px 12px 0 12px;
    padding: 0.65rem 1rem;
    max-width: 75%;
    font-size: 0.8rem;
    color: #8aaac8;
}
.chat-msg-ai {
    align-self: flex-start;
    background: #040a14;
    border: 1px solid #0a1628;
    border-left: 2px solid #00d4ff;
    border-radius: 0 12px 12px 12px;
    padding: 0.65rem 1rem;
    max-width: 85%;
    font-size: 0.8rem;
    color: #6a8aaa;
    line-height: 1.7;
}
.chat-sender {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.55rem;
    color: #00d4ff;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}

/* ── QUICK QUESTION BUTTONS ── */
.stButton > button {
    background: #060d1c !important;
    border: 1px solid #0d1a2e !important;
    color: #3a5a7a !important;
    border-radius: 6px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.68rem !important;
    transition: all 0.2s !important;
    padding: 0.4rem 0.8rem !important;
}
.stButton > button:hover {
    background: #080e1e !important;
    border-color: #00d4ff !important;
    color: #00d4ff !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #001a2e, #003050) !important;
    border: 1px solid #00d4ff !important;
    color: #00d4ff !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #002040, #004070) !important;
    box-shadow: 0 0 20px rgba(0,212,255,0.15) !important;
}

/* ── SECTION DIVIDER ── */
.sec-divider {
    height: 1px;
    background: linear-gradient(90deg, #0d1a2e, transparent);
    margin: 1.5rem 0;
}

/* ── SIDEBAR RADIO ── */
[data-testid="stSidebar"] .stRadio label {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.72rem !important;
    color: #2a4a6a !important;
    letter-spacing: 0.05em !important;
}
[data-testid="stSidebar"] .stRadio label:hover { color: #00d4ff !important; }

/* ── SELECTBOX / MULTISELECT ── */
[data-testid="stSelectbox"] > div,
[data-testid="stMultiSelect"] > div {
    background: #060d1c !important;
    border-color: #0d1a2e !important;
    border-radius: 6px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.75rem !important;
}

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #0a1628 !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.65rem !important;
    letter-spacing: 0.1em !important;
    color: #1e3a5f !important;
    text-transform: uppercase !important;
    background: transparent !important;
    border: none !important;
    padding: 0.5rem 1rem !important;
}
.stTabs [aria-selected="true"] {
    color: #00d4ff !important;
    border-bottom: 1px solid #00d4ff !important;
}

/* ── DATAFRAME ── */
[data-testid="stDataFrame"] { border: 1px solid #0a1628; border-radius: 8px; overflow: hidden; }

/* ── SPINNER ── */
[data-testid="stSpinner"] { color: #00d4ff !important; }

/* ── ALERTS ── */
.stAlert { border-radius: 6px !important; font-family: 'JetBrains Mono', monospace !important; font-size: 0.72rem !important; }

/* ── SECTION LABEL ── */
.sec-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    letter-spacing: 0.25em;
    color: #1a3050;
    text-transform: uppercase;
    margin-bottom: 0.7rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.sec-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #0a1628;
}
</style>
""", unsafe_allow_html=True)


# ── Session State ─────────────────────────────────────────────────────────────
if "rca_result"    not in st.session_state: st.session_state.rca_result    = None
if "action_plan"   not in st.session_state: st.session_state.action_plan   = None
if "simulation"    not in st.session_state: st.session_state.simulation    = None
if "overview"      not in st.session_state: st.session_state.overview      = None
if "chat_history"  not in st.session_state: st.session_state.chat_history  = []
if "analysis_done" not in st.session_state: st.session_state.analysis_done = False


# ── API Helpers ───────────────────────────────────────────────────────────────
def api_get(path):
    try:
        r = requests.get(f"{API_URL}{path}", timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error ({path}): {e}")
        return None

def api_post(path, payload):
    try:
        r = requests.post(f"{API_URL}{path}", json=payload, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error ({path}): {e}")
        return None


# ── PLOTLY THEME ──────────────────────────────────────────────────────────────
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono", color="#2a4a6a", size=10),
    margin=dict(l=10, r=10, t=35, b=10),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#0a1628", borderwidth=1, font=dict(size=9)),
)
SVC_COLORS = {"api-gateway": "#00d4ff", "order-service": "#ff6b35", "db-primary": "#00ff94", "payment-service": "#a78bfa"}


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <span class="brand">ARCA</span>
        <span class="tagline">AI Root Cause Analyzer</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">Configuration</div>', unsafe_allow_html=True)
    llm_provider = st.selectbox(
        "LLM Engine",
        options=["mock", "claude", "openai"],
        help="mock = no API key required",
        label_visibility="collapsed",
    )
    api_key = ""
    if llm_provider != "mock":
        api_key = st.text_input(
            f"{'Anthropic' if llm_provider == 'claude' else 'OpenAI'} API Key",
            type="password",
            placeholder="sk-...",
        )

    st.markdown('<div class="sidebar-section">Data Sources</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="data-pill">logs.json <span>24 entries</span></div>
    <div class="data-pill">metrics.csv <span>42 rows</span></div>
    <div class="data-pill">events.json <span>10 events</span></div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">Navigation</div>', unsafe_allow_html=True)
    page = st.radio(
        "nav",
        ["Dashboard", "Metrics + Anomalies", "Log Explorer",
         "Timeline", "AI Analysis", "Action + Recovery", "Chat"],
        label_visibility="collapsed",
    )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Reload Data", use_container_width=True):
        st.session_state.overview = api_get("/data/overview")
        st.rerun()


# ── Load overview on first run ────────────────────────────────────────────────
if st.session_state.overview is None:
    with st.spinner("Initializing data pipeline..."):
        st.session_state.overview = api_get("/data/overview")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.markdown("""
    <div class="page-header">
        <div class="page-eyebrow">Incident Overview</div>
        <div class="page-title">System Intelligence Dashboard</div>
        <div class="page-subtitle">Simulated Production Incident · 2024-01-15 · P1 Severity</div>
    </div>
    """, unsafe_allow_html=True)

    overview = st.session_state.overview
    if overview:
        log_s  = overview.get("log_summary", {})
        anom_s = overview.get("anomaly_summary", {})
        affected = log_s.get("affected_services", [])
        iw = log_s.get("incident_window", ["", ""])

        st.markdown(f"""
        <div class="stat-grid">
            <div class="stat-card" style="--accent:#00d4ff">
                <div class="stat-label">Log Entries</div>
                <div class="stat-value">{log_s.get('total_entries', 0)}</div>
                <div class="stat-meta">{log_s.get('error_count',0)} errors / {log_s.get('critical_count',0)} critical</div>
            </div>
            <div class="stat-card" style="--accent:#ff4444">
                <div class="stat-label">Anomalies</div>
                <div class="stat-value" style="color:#ff4444">{anom_s.get('total',0)}</div>
                <div class="stat-meta">peak @ {str(anom_s.get('peak_time','—'))[:16]}</div>
            </div>
            <div class="stat-card" style="--accent:#ff6b35">
                <div class="stat-label">Affected Services</div>
                <div class="stat-value" style="color:#ff6b35">{len(affected)}</div>
                <div class="stat-meta">{', '.join(affected[:3])}</div>
            </div>
            <div class="stat-card" style="--accent:#00ff94">
                <div class="stat-label">Incident Duration</div>
                <div class="stat-value" style="color:#00ff94">~5m</div>
                <div class="stat-meta">14:02 — 14:07 UTC</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.markdown('<div class="sec-label">Key Signals</div>', unsafe_allow_html=True)
            signals = log_s.get("key_signals", [])
            items = "".join(f'<div class="signal-item">{s}</div>' for s in signals)
            st.markdown(f'<div class="signal-list">{items}</div>', unsafe_allow_html=True)

        with col_right:
            st.markdown('<div class="sec-label">Anomalies by Severity</div>', unsafe_allow_html=True)
            by_sev = anom_s.get("by_severity", {})
            if by_sev:
                sev_colors = {"critical": "#ff4444", "high": "#ff6b35", "medium": "#ffaa00", "low": "#00ff94"}
                fig = go.Figure(go.Bar(
                    x=list(by_sev.keys()),
                    y=list(by_sev.values()),
                    marker_color=[sev_colors.get(k, "#2a4a6a") for k in by_sev.keys()],
                    marker_line_width=0,
                ))
                fig.update_layout(**PLOT_LAYOUT, height=200, showlegend=False)
                fig.update_xaxes(showgrid=False, tickfont=dict(family="JetBrains Mono", size=9))
                fig.update_yaxes(showgrid=True, gridcolor="#0a1628", tickfont=dict(family="JetBrains Mono", size=9))
                st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="sec-divider"></div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="run-panel">
        <div class="run-title">Run AI Root Cause Analysis</div>
        <div class="run-sub">Agent will correlate logs, metrics, and events — then generate a ranked hypothesis report.</div>
    </div>
    """, unsafe_allow_html=True)

    col_btn, col_status = st.columns([1, 2])
    with col_btn:
        if st.button("Run Analysis", type="primary", use_container_width=True):
            with st.spinner("Agent processing..."):
                result = api_post("/analyze", {"llm_provider": llm_provider, "api_key": api_key})
                if result:
                    st.session_state.rca_result  = result.get("rca")
                    st.session_state.action_plan = result.get("action_plan")
                    st.session_state.analysis_done = True
                    st.success("Analysis complete — navigate to AI Analysis")
    with col_status:
        if st.session_state.analysis_done:
            st.success("Analysis ready — navigate to AI Analysis or Action + Recovery")
        else:
            st.info("Select LLM engine and click Run Analysis to begin")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: METRICS + ANOMALIES
# ════════════════════════════════════════════════════════════════════════════
elif page == "Metrics + Anomalies":
    st.markdown("""
    <div class="page-header">
        <div class="page-eyebrow">Observability</div>
        <div class="page-title">Metrics + Anomaly Detection</div>
    </div>
    """, unsafe_allow_html=True)

    metrics_data = api_get("/data/metrics")
    if not metrics_data:
        st.stop()

    df = pd.DataFrame(metrics_data["metrics"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    services = df["service"].unique().tolist()
    sel_svc  = st.multiselect("Services", services, default=services)
    df_f     = df[df["service"].isin(sel_svc)]

    tab1, tab2, tab3 = st.tabs(["CPU + Memory", "Latency + Error Rate", "DB Connections"])

    with tab1:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            subplot_titles=["CPU %", "Memory %"],
                            vertical_spacing=0.08)
        for svc in sel_svc:
            d = df_f[df_f["service"] == svc]
            c = SVC_COLORS.get(svc, "#2a4a6a")
            fig.add_trace(go.Scatter(
                x=d["timestamp"],
                y=d["cpu_percent"],
                name=svc,
                line=dict(color=c, width=1.5),
                legendgroup=svc,
                fill="tozeroy",
                fillcolor=hex_to_rgba(c, alpha=0.05),
            ), row=1, col=1)
            fig.add_trace(go.Scatter(x=d["timestamp"], y=d["memory_percent"], name=svc, line=dict(color=c, width=1.5), legendgroup=svc, showlegend=False), row=2, col=1)
        fig.add_hline(y=90, line_dash="dot", line_color="#ff4444", line_width=1, row=1, col=1)
        fig.add_hline(y=90, line_dash="dot", line_color="#ff4444", line_width=1, row=2, col=1)
        fig.update_layout(**PLOT_LAYOUT, height=420)
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="#080e1a")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            subplot_titles=["Latency (ms)", "Error Rate (%)"],
                            vertical_spacing=0.08)
        for svc in sel_svc:
            d = df_f[df_f["service"] == svc]
            c = SVC_COLORS.get(svc, "#2a4a6a")
            fig.add_trace(go.Scatter(x=d["timestamp"], y=d["latency_ms"],         name=svc, line=dict(color=c, width=1.5), legendgroup=svc), row=1, col=1)
            fig.add_trace(go.Scatter(x=d["timestamp"], y=d["error_rate_percent"], name=svc, line=dict(color=c, width=1.5), legendgroup=svc, showlegend=False), row=2, col=1)
        fig.add_hline(y=2000, line_dash="dot", line_color="#ff4444", line_width=1, row=1, col=1)
        fig.add_hline(y=20,   line_dash="dot", line_color="#ff4444", line_width=1, row=2, col=1)
        fig.update_layout(**PLOT_LAYOUT, height=420)
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="#080e1a")
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        db_df = df_f[df_f["service"] == "order-service"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=db_df["timestamp"], y=db_df["db_connections"],
            fill="tozeroy", fillcolor="rgba(0,212,255,0.04)",
            line=dict(color="#00d4ff", width=1.5),
            name="DB Connections"
        ))
        fig.add_hline(y=480, line_dash="dot", line_color="#ff4444",  line_width=1, annotation_text="CRITICAL 480", annotation_font_color="#ff4444")
        fig.add_hline(y=350, line_dash="dot", line_color="#ffaa00", line_width=1, annotation_text="WARN 350",     annotation_font_color="#ffaa00")
        fig.update_layout(**PLOT_LAYOUT, height=280, title="DB Connection Count — order-service")
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="#080e1a")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="sec-label">Detected Anomalies</div>', unsafe_allow_html=True)
    overview = st.session_state.overview or api_get("/data/overview")
    anomalies = (overview or {}).get("anomalies", [])
    if anomalies:
        anom_df = pd.DataFrame(anomalies)
        sev_filter = st.multiselect("Severity Filter", ["critical","high","medium","low"], default=["critical","high"])
        filtered   = anom_df[anom_df["severity"].isin(sev_filter)] if not anom_df.empty else anom_df
        st.dataframe(
            filtered[["timestamp","service","metric","value","baseline","z_score","severity","description"]],
            use_container_width=True, height=280,
        )


# ════════════════════════════════════════════════════════════════════════════
# PAGE: LOG EXPLORER
# ════════════════════════════════════════════════════════════════════════════
elif page == "Log Explorer":
    st.markdown("""
    <div class="page-header">
        <div class="page-eyebrow">Observability</div>
        <div class="page-title">Log Explorer</div>
    </div>
    """, unsafe_allow_html=True)

    logs_data = api_get("/data/logs")
    if not logs_data:
        st.stop()

    logs_df = pd.DataFrame(logs_data["logs"])
    logs_df["timestamp"] = pd.to_datetime(logs_df["timestamp"])

    col1, col2 = st.columns(2)
    with col1:
        level_filter = st.multiselect("Level", ["INFO","WARN","ERROR","CRITICAL"], default=["ERROR","CRITICAL","WARN"])
    with col2:
        svc_filter = st.multiselect("Service", sorted(logs_df["service"].unique()), default=sorted(logs_df["service"].unique()))

    filtered = logs_df[logs_df["level"].isin(level_filter) & logs_df["service"].isin(svc_filter)]
    st.dataframe(
        filtered[["timestamp","level","service","message"]].sort_values("timestamp"),
        use_container_width=True, height=480,
    )

    st.markdown('<div class="sec-label">Level Distribution</div>', unsafe_allow_html=True)
    level_counts = logs_df["level"].value_counts()
    lc_map = {"CRITICAL":"#ff4444","ERROR":"#ff6b35","WARN":"#ffaa00","INFO":"#00d4ff"}
    fig = go.Figure(go.Pie(
        values=level_counts.values,
        labels=level_counts.index,
        marker_colors=[lc_map.get(l,"#2a4a6a") for l in level_counts.index],
        hole=0.6,
        textfont=dict(family="JetBrains Mono", size=9),
    ))
    fig.update_layout(**PLOT_LAYOUT, height=240, margin=dict(l=0,r=0,t=10,b=0))
    st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: TIMELINE
# ════════════════════════════════════════════════════════════════════════════
elif page == "Timeline":
    st.markdown("""
    <div class="page-header">
        <div class="page-eyebrow">Incident Reconstruction</div>
        <div class="page-title">Event Timeline</div>
    </div>
    """, unsafe_allow_html=True)

    overview = st.session_state.overview or api_get("/data/overview")
    if not overview:
        st.stop()

    timeline = overview.get("timeline", [])
    phases   = overview.get("phases", {})
    phase_list = phases.get("phases", [])

    if phase_list:
        pc_map = {"yellow": "#ffaa00", "orange": "#ff6b35", "red": "#ff4444", "green": "#00ff94"}
        phase_items = "".join(
            f'<div class="phase-item" style="--pc:{pc_map.get(p["color"],"#00d4ff")}">'
            f'<div class="phase-name">{p["phase"]}</div>'
            f'<div class="phase-ts">{p["timestamp"][:19]}</div></div>'
            for p in phase_list
        )
        st.markdown(f'<div class="phase-strip">{phase_items}</div>', unsafe_allow_html=True)

    sev_filter = st.multiselect("Severity", ["critical","high","medium","info"], default=["critical","high","medium"])
    filtered_tl = [e for e in timeline if e.get("severity") in sev_filter]

    sev_color = {"critical":"#ff4444","high":"#ff6b35","medium":"#ffaa00","info":"#00d4ff"}
    rows_html = ""
    for i, event in enumerate(filtered_tl):
        color = sev_color.get(event.get("severity","info"), "#2a4a6a")
        ts    = str(event.get("timestamp",""))[:19].replace("T"," ")
        title = event.get("title","").replace(event.get("icon",""),"").strip()
        detail = event.get("detail","")[:130]
        delay  = min(i * 0.02, 0.6)
        rows_html += (
            f'<div class="tl-row" style="--dot-color:{color};--bar-color:{color};animation-delay:{delay}s">'
            f'<div class="tl-ts">{ts}</div>'
            f'<div class="tl-bar" style="background:{color};opacity:0.5"></div>'
            f'<div><div class="tl-title">{title}</div>'
            f'<div class="tl-detail">{detail}</div></div></div>'
        )
    st.markdown(f'<div class="tl-container">{rows_html}</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: AI ANALYSIS
# ════════════════════════════════════════════════════════════════════════════
elif page == "AI Analysis":
    st.markdown("""
    <div class="page-header">
        <div class="page-eyebrow">Agentic Reasoning</div>
        <div class="page-title">Root Cause Analysis</div>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.analysis_done:
        st.info("Run Analysis from the Dashboard first, or trigger it here.")
        if st.button("Run Analysis Now", type="primary"):
            with st.spinner("Agent analyzing..."):
                result = api_post("/analyze", {"llm_provider": llm_provider, "api_key": api_key})
                if result:
                    st.session_state.rca_result  = result.get("rca")
                    st.session_state.action_plan = result.get("action_plan")
                    st.session_state.analysis_done = True
                    st.rerun()
        st.stop()

    rca = st.session_state.rca_result
    if not rca:
        st.error("No analysis available. Re-run from Dashboard.")
        st.stop()

    primary  = rca.get("primary_hypothesis", {})
    conf     = primary.get("confidence", 0)
    conf_pct = int(conf * 100)

    st.markdown(f"""
    <div class="incident-banner">
        {rca.get('incident_summary','')}
        <div class="meta-row">
            <span>MODEL <span class="meta-val">{rca.get('model_used','')}</span></span>
            <span>LATENCY <span class="meta-val">{rca.get('analysis_duration_ms',0)}ms</span></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sec-label">Primary Hypothesis</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="hyp-primary">
        <div class="hyp-conf-label">Confidence — {conf_pct}%</div>
        <div class="conf-track"><div class="conf-fill" style="--w:{conf_pct}%"></div></div>
        <div class="hyp-cause">{primary.get('root_cause','')}</div>
        <div class="hyp-body">{primary.get('explanation','')}</div>
    </div>
    """, unsafe_allow_html=True)

    col_ev, col_fx = st.columns([1,1])
    with col_ev:
        st.markdown('<div class="sec-label">Evidence</div>', unsafe_allow_html=True)
        items = "".join(f'<div class="evidence-item">{e}</div>' for e in primary.get("evidence",[]))
        st.markdown(items, unsafe_allow_html=True)
    with col_fx:
        st.markdown('<div class="sec-label">Suggested Fix</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="hyp-body" style="margin-bottom:0.8rem">{primary.get("suggested_fix","")}</div>', unsafe_allow_html=True)
        action = primary.get("recommended_action","").replace("_"," ").upper()
        target = primary.get("action_target","")
        st.markdown(f'<div class="action-type-label">{action} &rarr; {target}</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec-divider"></div>', unsafe_allow_html=True)

    alts = rca.get("alternative_hypotheses", [])
    if alts:
        st.markdown('<div class="sec-label">Alternative Hypotheses</div>', unsafe_allow_html=True)
        for hyp in alts:
            c2 = int(hyp.get("confidence",0)*100)
            with st.expander(f"Hypothesis #{hyp.get('rank','')} — {c2}% confidence"):
                st.markdown(f"""
                <div class="conf-track"><div class="conf-fill-alt" style="--w:{c2}%"></div></div>
                <div class="hyp-body">{hyp.get('explanation','')}</div>
                """, unsafe_allow_html=True)
                st.markdown('<div class="sec-label" style="margin-top:0.8rem">Evidence</div>', unsafe_allow_html=True)
                for e in hyp.get("evidence",[]):
                    st.markdown(f'<div class="evidence-item">{e}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="hyp-body" style="margin-top:0.6rem"><strong style="color:#2a5080">Fix:</strong> {hyp.get("suggested_fix","")}</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec-divider"></div>', unsafe_allow_html=True)
    col_tl, col_im = st.columns([1,1])
    with col_tl:
        st.markdown('<div class="sec-label">Timeline Correlation</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="hyp-body">{rca.get("timeline_correlation","")}</div>', unsafe_allow_html=True)
    with col_im:
        st.markdown('<div class="sec-label">Impact Assessment</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="hyp-body">{rca.get("impact_assessment","")}</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec-divider"></div>', unsafe_allow_html=True)
    col_imm, col_prev = st.columns([1,1])
    with col_imm:
        st.markdown('<div class="sec-label">Immediate Steps</div>', unsafe_allow_html=True)
        for i, s in enumerate(rca.get("immediate_steps",[])):
            st.markdown(f'<div class="step-row"><span class="step-idx">{i+1:02d}</span>{s}</div>', unsafe_allow_html=True)
    with col_prev:
        st.markdown('<div class="sec-label">Prevention</div>', unsafe_allow_html=True)
        for s in rca.get("prevention_steps",[]):
            st.markdown(f'<div class="evidence-item">{s}</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: ACTION + RECOVERY
# ════════════════════════════════════════════════════════════════════════════
elif page == "Action + Recovery":
    st.markdown("""
    <div class="page-header">
        <div class="page-eyebrow">Remediation</div>
        <div class="page-title">Action Plan + Recovery Simulation</div>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.analysis_done:
        st.info("Run AI Analysis first from the Dashboard.")
        st.stop()

    plan = st.session_state.action_plan
    rca  = st.session_state.rca_result
    if not plan:
        st.error("No action plan available.")
        st.stop()

    risk_color = {"low":"#00ff94","medium":"#ffaa00","high":"#ff4444"}.get(plan.get("risk_level","medium"),"#2a4a6a")
    action_label = plan.get("action_type","").replace("_"," ").upper()

    st.markdown(f"""
    <div class="action-card">
        <div class="action-type-label">{action_label}</div>
        <div class="action-name">{plan.get('action_type','').replace('_',' ').title()}</div>
        <div class="action-meta">
            <span>TARGET <span class="av">{plan.get('target_service','')}</span></span>
            <span>PRIORITY <span class="av">{plan.get('priority','').upper()}</span></span>
            <span>RISK <span style="color:{risk_color}">{plan.get('risk_level','').upper()}</span></span>
            <span>EST DOWNTIME <span class="av">{plan.get('estimated_downtime_mins',0)} min</span></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_steps, col_meta = st.columns([1,1])
    with col_steps:
        st.markdown('<div class="sec-label">Execution Steps</div>', unsafe_allow_html=True)
        for i, step in enumerate(plan.get("steps",[])):
            st.markdown(f'<div class="step-row"><span class="step-idx">{i+1:02d}</span>{step}</div>', unsafe_allow_html=True)
    with col_meta:
        st.markdown('<div class="sec-label">Success Metrics</div>', unsafe_allow_html=True)
        for m in plan.get("success_metrics",[]):
            st.markdown(f'<div class="evidence-item">{m}</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec-label" style="margin-top:0.8rem">Rollback Plan</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="hyp-body">{plan.get("rollback_plan","")}</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sec-label">Approve + Execute</div>', unsafe_allow_html=True)

    col_approve, col_warn = st.columns([1,2])
    with col_approve:
        approved = st.button(
            f"Approve: {plan.get('action_type','').replace('_',' ').title()}",
            type="primary",
            use_container_width=True,
        )
    with col_warn:
        st.markdown(
            f'<div class="approve-notice">Simulates applying the action to the production environment.<br>'
            f'Expected: {plan.get("expected_outcome","")}</div>',
            unsafe_allow_html=True
        )

    if approved:
        with st.spinner(f"Executing {plan.get('action_type','')}..."):
            sim = api_post("/simulate", {
                "action_type":    plan.get("action_type","restart_service"),
                "target_service": plan.get("target_service",""),
            })
            if sim:
                st.session_state.simulation = sim
                time.sleep(0.5)

    sim = st.session_state.simulation
    if sim:
        st.markdown(f'<div class="recovery-banner">{sim.get("message","")}</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec-label">Recovery Simulation</div>', unsafe_allow_html=True)

        tl = sim.get("recovery_timeline", [])
        if tl:
            services_to_show = ["order-service", "db-primary", "api-gateway"]
            metrics_to_show  = [
                ("error_rate_percent", "Error Rate (%)"),
                ("latency_ms",         "Latency (ms)"),
                ("db_connections",     "DB Connections"),
            ]
            for metric_key, label in metrics_to_show:
                fig = go.Figure()
                for svc in services_to_show:
                    x_vals = [s["t_seconds"] for s in tl]
                    y_vals = [s["metrics"].get(svc,{}).get(metric_key,0) for s in tl]
                    c = SVC_COLORS.get(svc, "#2a4a6a")
                    fig.add_trace(go.Scatter(
                        x=x_vals, y=y_vals, name=svc,
                        line=dict(color=c, width=1.5),
                        mode="lines+markers",
                        marker=dict(size=4),
                    ))
                fig.update_layout(**PLOT_LAYOUT, height=240, title=label)
                fig.update_xaxes(showgrid=False, title_text="seconds after action", title_font=dict(size=9))
                fig.update_yaxes(showgrid=True, gridcolor="#080e1a")
                st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: CHAT
# ════════════════════════════════════════════════════════════════════════════
elif page == "Chat":
    st.markdown("""
    <div class="page-header">
        <div class="page-eyebrow">Conversational AI</div>
        <div class="page-title">Ask the Incident Agent</div>
        <div class="page-subtitle">Context-aware Q&amp;A about this incident</div>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.analysis_done:
        st.info("Run analysis first for context-aware answers. General questions still work.")

    chat_wrap_html = '<div class="chat-wrap">'
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            chat_wrap_html += (
                f'<div style="display:flex;justify-content:flex-end">'
                f'<div class="chat-msg-user"><div class="chat-sender">You</div>{msg["content"]}</div></div>'
            )
        else:
            chat_wrap_html += (
                f'<div style="display:flex;justify-content:flex-start">'
                f'<div class="chat-msg-ai"><div class="chat-sender">ARCA Agent</div>{msg["content"]}</div></div>'
            )
    chat_wrap_html += '</div>'
    st.markdown(chat_wrap_html, unsafe_allow_html=True)

    st.markdown('<div class="sec-label">Quick Questions</div>', unsafe_allow_html=True)
    qcols = st.columns(3)
    quick_qs = [
        "Why did this incident happen?",
        "What is the recommended fix?",
        "How do we prevent this next time?",
        "Walk me through the timeline",
        "Which services were affected?",
        "How confident is the analysis?",
    ]
    for i, q in enumerate(quick_qs):
        with qcols[i % 3]:
            if st.button(q, key=f"quick_{i}", use_container_width=True):
                st.session_state._pending_question = q

    user_input = st.chat_input("Ask anything about this incident...")
    pending    = getattr(st.session_state, "_pending_question", None)
    question   = user_input or pending
    if pending:
        st.session_state._pending_question = None

    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.spinner("Reasoning..."):
            resp = api_post("/chat", {
                "message":      question,
                "history":      st.session_state.chat_history[:-1],
                "llm_provider": llm_provider,
                "api_key":      api_key,
            })
        if resp:
            answer = resp.get("response", "Unable to generate a response.")
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun()

    if st.session_state.chat_history:
        if st.button("Clear Chat", use_container_width=False):
            st.session_state.chat_history = []
            st.rerun()
