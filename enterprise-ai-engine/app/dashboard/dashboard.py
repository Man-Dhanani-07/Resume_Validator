import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json, sys, os
from datetime import datetime
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(ROOT)

from app.db.database import SessionLocal
from app.db.models import WorkflowRun
from app.graph.workflow import workflow
from app.ingestion.pdf_parser import extract_text_from_pdf
from app.db.repository import save_workflow

# ═══════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="ResumeGuard · AI Risk Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════
# GLOBAL STYLES
# ═══════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Fonts ─────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@400;500;600;700;800&family=Inconsolata:wght@300;400;500&display=swap');

/* ── Tokens ─────────────────────────────────────────────── */
:root {
  --ink:        #0b0e17;
  --ink-mid:    #141824;
  --ink-light:  #1c2333;
  --ink-line:   #242d42;
  --slate:      #8899b4;
  --mist:       #b8c5d6;
  --snow:       #e8edf4;
  --blue:       #4f8ef7;
  --blue-dim:   #1a3060;
  --cyan:       #00d2c8;
  --green:      #27d98a;
  --green-dim:  #082e1c;
  --amber:      #ffb340;
  --amber-dim:  #2a1e00;
  --red:        #ff4f5e;
  --red-dim:    #2d0a10;
  --violet:     #b06cff;
  --violet-dim: #210e38;
  --r:          12px;
  --r-sm:       8px;
}

/* ── Base ───────────────────────────────────────────────── */
html, body, .stApp { background: var(--ink) !important; }
.main .block-container { padding: 0 2.5rem 3rem; max-width: 1440px; }
* { font-family: 'Bricolage Grotesque', sans-serif !important; }
code, pre, textarea { font-family: 'Inconsolata', monospace !important; }

/* ── Sidebar ─────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: var(--ink-mid) !important;
  border-right: 1px solid var(--ink-line) !important;
}
[data-testid="stSidebar"] section { padding-top: 0 !important; }

/* ── Metrics ─────────────────────────────────────────────── */
[data-testid="stMetric"] {
  background: var(--ink-mid);
  border: 1px solid var(--ink-line);
  border-radius: var(--r);
  padding: 1rem 1.25rem !important;
}
[data-testid="stMetricLabel"] p {
  font-size: 0.68rem !important;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--slate) !important;
  font-weight: 600 !important;
}
[data-testid="stMetricValue"] {
  font-size: 1.65rem !important;
  font-weight: 800 !important;
  color: var(--snow) !important;
}
[data-testid="stMetricDelta"] { font-size: 0.75rem !important; }

/* ── Buttons ─────────────────────────────────────────────── */
.stButton > button {
  background: var(--blue) !important;
  color: #fff !important;
  border: none !important;
  border-radius: var(--r-sm) !important;
  font-weight: 700 !important;
  font-size: 0.85rem !important;
  padding: 0.55rem 1.4rem !important;
  transition: filter .2s, transform .15s !important;
}
.stButton > button:hover {
  filter: brightness(1.12) !important;
  transform: translateY(-1px) !important;
}

/* ── Upload area ─────────────────────────────────────────── */
[data-testid="stFileUploader"] {
  background: var(--ink-mid) !important;
  border: 1.5px dashed var(--ink-line) !important;
  border-radius: var(--r) !important;
  transition: border-color .2s !important;
}
[data-testid="stFileUploader"]:focus-within,
[data-testid="stFileUploader"]:hover {
  border-color: var(--blue) !important;
}

/* ── Dataframe ────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--ink-line) !important;
  border-radius: var(--r) !important;
  overflow: hidden !important;
}
[data-testid="stDataFrame"] table {
  background: var(--ink-mid) !important;
}

/* ── Selectbox ───────────────────────────────────────────── */
[data-baseweb="select"] > div {
  background: var(--ink-mid) !important;
  border-color: var(--ink-line) !important;
  border-radius: var(--r-sm) !important;
  color: var(--snow) !important;
}

/* ── Text area ───────────────────────────────────────────── */
textarea {
  background: var(--ink-mid) !important;
  border-color: var(--ink-line) !important;
  color: var(--mist) !important;
  border-radius: var(--r-sm) !important;
  font-size: 0.8rem !important;
  line-height: 1.6 !important;
}

/* ── Tabs ────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {
  gap: 4px;
  border-bottom: 1px solid var(--ink-line);
  padding-bottom: 0;
}
[data-testid="stTabs"] [role="tab"] {
  background: transparent !important;
  border: none !important;
  color: var(--slate) !important;
  font-size: 0.8rem !important;
  font-weight: 600 !important;
  padding: 0.5rem 1rem !important;
  border-radius: var(--r-sm) var(--r-sm) 0 0 !important;
  transition: color .15s !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: var(--snow) !important;
  border-bottom: 2px solid var(--blue) !important;
  background: var(--ink-light) !important;
}

/* ── Info / warning / error / success ──────────────────── */
.stAlert {
  border-radius: var(--r-sm) !important;
  border-left-width: 3px !important;
  background: var(--ink-mid) !important;
}

/* ── Divider ─────────────────────────────────────────────── */
hr { border-color: var(--ink-line) !important; margin: 1.5rem 0 !important; }

/* ── Download button ─────────────────────────────────────── */
[data-testid="stDownloadButton"] button {
  background: var(--ink-light) !important;
  border: 1px solid var(--ink-line) !important;
  color: var(--mist) !important;
  border-radius: var(--r-sm) !important;
  font-size: 0.8rem !important;
}
[data-testid="stDownloadButton"] button:hover {
  border-color: var(--blue) !important;
  color: var(--blue) !important;
}

/* ── Spinner ─────────────────────────────────────────────── */
.stSpinner > div { border-top-color: var(--blue) !important; }

/* ── Progress bar ────────────────────────────────────────── */
.stProgress > div > div { background: var(--blue) !important; }

/* ── JSON viewer ─────────────────────────────────────────── */
[data-testid="stJson"] {
  background: var(--ink-mid) !important;
  border: 1px solid var(--ink-line) !important;
  border-radius: var(--r-sm) !important;
}

/* ── Radio ───────────────────────────────────────────────── */
[data-testid="stRadio"] label { color: var(--mist) !important; font-size: 0.85rem !important; }
[data-testid="stRadio"] [data-baseweb="radio"] div { border-color: var(--blue) !important; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# DESIGN PRIMITIVES
# ═══════════════════════════════════════════════════════════

def _pill(text: str, color: str, bg: str) -> str:
    return (
        f'<span style="display:inline-flex;align-items:center;gap:5px;'
        f'background:{bg};color:{color};border:1px solid {color}33;'
        f'border-radius:20px;padding:3px 11px;font-size:0.72rem;font-weight:700;'
        f'letter-spacing:0.06em;white-space:nowrap;">{text}</span>'
    )


DECISION_CFG = {
    "APPROVE": ("✅ APPROVE", "#27d98a", "#082e1c"),
    "REVIEW":  ("⚠️  REVIEW",  "#ffb340", "#2a1e00"),
    "REJECT":  ("❌ REJECT",  "#ff4f5e", "#2d0a10"),
}
RISK_CFG = {
    "LOW":      ("● LOW",      "#27d98a", "#082e1c"),
    "MEDIUM":   ("● MEDIUM",  "#ffb340", "#2a1e00"),
    "HIGH":     ("● HIGH",    "#ff4f5e", "#2d0a10"),
    "CRITICAL": ("⬡ CRITICAL","#b06cff", "#210e38"),
}


def decision_pill(d: str) -> str:
    d = (d or "").upper()
    t, c, bg = DECISION_CFG.get(d, (d or "—", "#8899b4", "#1c2333"))
    return _pill(t, c, bg)


def risk_pill(r: str) -> str:
    r = (r or "").upper()
    t, c, bg = RISK_CFG.get(r, (r or "—", "#8899b4", "#1c2333"))
    return _pill(t, c, bg)


def kpi_card(icon: str, value, label: str, accent: str = "#4f8ef7", delta: str = ""):
    st.markdown(f"""
    <div style="background:var(--ink-mid);border:1px solid var(--ink-line);
         border-top:3px solid {accent};border-radius:var(--r);
         padding:1.1rem 1.3rem;height:100%;">
      <div style="font-size:1.4rem;line-height:1;margin-bottom:.35rem;">{icon}</div>
      <div style="font-size:1.75rem;font-weight:800;color:var(--snow);
           letter-spacing:-0.03em;line-height:1;">{value}</div>
      <div style="font-size:0.68rem;font-weight:600;text-transform:uppercase;
           letter-spacing:.08em;color:var(--slate);margin-top:.3rem;">{label}</div>
      {"<div style='font-size:0.7rem;color:"+accent+";margin-top:3px;'>"+delta+"</div>" if delta else ""}
    </div>
    """, unsafe_allow_html=True)


def section_header(icon: str, title: str, sub: str = ""):
    st.markdown(f"""
    <div style="margin:2rem 0 1rem;">
      <div style="display:flex;align-items:center;gap:9px;">
        <span style="font-size:1rem;">{icon}</span>
        <span style="font-size:1rem;font-weight:700;color:var(--snow);">{title}</span>
      </div>
      {"<div style='font-size:.75rem;color:var(--slate);margin-top:2px;padding-left:26px;'>"+sub+"</div>" if sub else ""}
    </div>
    """, unsafe_allow_html=True)


def hbar(label: str, value: int, cap: int, color: str):
    pct = min(100, int(value / cap * 100)) if cap else 0
    st.markdown(f"""
    <div style="margin-bottom:.65rem;">
      <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
        <span style="font-size:.78rem;color:var(--mist);">{label}</span>
        <span style="font-size:.8rem;font-weight:700;color:var(--snow);">{value}
          <span style="color:var(--slate);font-weight:400;font-size:.68rem;">/ {cap}</span></span>
      </div>
      <div style="background:var(--ink-line);border-radius:3px;height:6px;overflow:hidden;">
        <div style="width:{pct}%;height:100%;background:linear-gradient(90deg,{color}88,{color});
             border-radius:3px;"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def risk_flag_row(idx: int, text: str):
    clean = "no significant" in text.lower()
    icon  = "✓" if clean else "✗"
    c     = "#27d98a" if clean else "#ff4f5e"
    bg    = "#082e1c" if clean else "#2d0a10"
    st.markdown(f"""
    <div style="display:flex;align-items:flex-start;gap:10px;
         background:{bg};border:1px solid {c}25;border-left:2.5px solid {c};
         border-radius:var(--r-sm);padding:.65rem 1rem;margin-bottom:.45rem;">
      <span style="background:{c}22;color:{c};border-radius:50%;
           width:20px;height:20px;display:flex;align-items:center;justify-content:center;
           font-size:.65rem;font-weight:800;flex-shrink:0;margin-top:1px;">{icon}</span>
      <span style="font-size:.82rem;color:#dce8f5;line-height:1.55;">{text}</span>
    </div>
    """, unsafe_allow_html=True)


def gauge_chart(value: int, label: str, color: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode    = "gauge+number",
        value   = value,
        title   = {"text": label, "font": {"size": 12, "color": "#8899b4",
                                           "family": "Bricolage Grotesque"}},
        number  = {"font": {"size": 28, "color": "#e8edf4",
                            "family": "Bricolage Grotesque"}, "suffix": ""},
        gauge   = {
            "axis":      {"range": [0, 100], "tickcolor": "#242d42",
                          "tickwidth": 1, "ticklen": 4, "nticks": 6,
                          "tickfont": {"size": 9, "color": "#8899b4"}},
            "bar":       {"color": color, "thickness": 0.22},
            "bgcolor":   "#141824",
            "bordercolor": "#242d42",
            "borderwidth": 1,
            "steps": [
                {"range": [0,  33],  "color": "#0f1422"},
                {"range": [33, 66],  "color": "#111929"},
                {"range": [66, 100], "color": "#0f1422"},
            ],
            "threshold": {
                "line":      {"color": color, "width": 2},
                "thickness": 0.75,
                "value":     value,
            },
        },
    ))
    fig.update_layout(
        height=190,
        margin=dict(l=18, r=18, t=36, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor ="rgba(0,0,0,0)",
        font={"color": "#8899b4", "family": "Bricolage Grotesque"},
    )
    return fig


def radar_chart(components: dict) -> go.Figure:
    keys   = list(components.keys())
    values = list(components.values())
    maxes  = {"section_score": 30, "density_score": 20,
               "garbage_score": 10, "contact_score": 15, "structure_score": 25}
    norm   = [min(100, int(v / maxes.get(k, 30) * 100))
               for k, v in zip(keys, values)]
    labels = [k.replace("_score", "").replace("_", " ").title() for k in keys]
    norm  += norm[:1]
    labels += labels[:1]

    fig = go.Figure(go.Scatterpolar(
        r=norm, theta=labels,
        fill="toself",
        fillcolor="rgba(79,142,247,0.12)",
        line=dict(color="#4f8ef7", width=2),
        marker=dict(color="#4f8ef7", size=6),
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0, 100], gridcolor="#242d42",
                            tickfont=dict(color="#8899b4", size=8), color="#8899b4"),
            angularaxis=dict(gridcolor="#242d42", tickfont=dict(color="#b8c5d6", size=10)),
        ),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=20, b=20),
        height=250,
    )
    return fig


def mini_donut(approve: int, review: int, reject: int) -> go.Figure:
    fig = go.Figure(go.Pie(
        values=[approve, review, reject],
        labels=["Approve", "Review", "Reject"],
        hole=0.68,
        marker=dict(colors=["#27d98a", "#ffb340", "#ff4f5e"],
                    line=dict(color="#0b0e17", width=3)),
        textfont=dict(color="white", size=11),
        hovertemplate="%{label}: %{value}<extra></extra>",
    ))
    total = approve + review + reject
    fig.add_annotation(
        text=f"<b>{total}</b>",
        x=0.5, y=0.55, font_size=22,
        font_color="#e8edf4", font_family="Bricolage Grotesque",
        showarrow=False,
    )
    fig.add_annotation(
        text="Total", x=0.5, y=0.38,
        font_size=10, font_color="#8899b4",
        font_family="Bricolage Grotesque", showarrow=False,
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(font=dict(color="#b8c5d6", size=10, family="Bricolage Grotesque"),
                    orientation="h", x=0, y=-0.08),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        height=230,
    )
    return fig


# ═══════════════════════════════════════════════════════════
# DATA HELPERS
# ═══════════════════════════════════════════════════════════

def _parse_expl(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _parse_reasons(sel) -> list:
    if sel.risk_reasons:
        try:
            r = json.loads(sel.risk_reasons)
            if isinstance(r, list):
                return r
        except Exception:
            pass
    expl = _parse_expl(sel.explainability)
    return expl.get("risk_reasons", [])


# ═══════════════════════════════════════════════════════════
# ✅ FIX — DECISION NORMALISER
# Maps legacy DB values (APPROVED, REJECTED, MANUAL AUDIT)
# to current canonical labels (APPROVE, REJECT, REVIEW).
# Called at read-time so the DB stays untouched.
# ═══════════════════════════════════════════════════════════
def _normalise_decision(raw: str) -> str:
    _MAP = {
        "APPROVED":     "APPROVE",
        "APPROVE":      "APPROVE",
        "REJECTED":     "REJECT",
        "REJECT":       "REJECT",
        "MANUAL AUDIT": "REVIEW",
        "MANUAL_AUDIT": "REVIEW",
        "REVIEW":       "REVIEW",
    }
    return _MAP.get((raw or "").upper().strip(), (raw or "").upper().strip())


def fetch_runs(risk_filter="All", decision_filter="All") -> tuple[list, pd.DataFrame]:
    db   = SessionLocal()
    runs = db.query(WorkflowRun).order_by(WorkflowRun.id.desc()).all()
    db.close()

    rows = []
    for r in runs:
        rows.append({
            "ID":            r.id,
            # ✅ FIX 1 — normalise decision so APPROVED→APPROVE, REJECTED→REJECT etc.
            "Decision":      _normalise_decision(r.decision),
            "Risk Level":    (r.risk_level  or "N/A").upper(),
            "Risk Score":    r.risk_score       or 0,
            "Structural":    r.structural_score or 0,
            "LLM Score":     r.llm_score        or 0,
            "Fraud Score":   r.fraud_score      or 0,
            "Confidence":    r.final_confidence or 0,
            "Total Penalty": r.total_penalty    or 0,
            "Validation":    r.validation       or "Passed",
            "Created":       r.created_at,
        })
    df = pd.DataFrame(rows)

    if not df.empty:
        if risk_filter     != "All": df = df[df["Risk Level"] == risk_filter]
        if decision_filter != "All": df = df[df["Decision"]   == decision_filter]

    return runs, df


# ═══════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════

with st.sidebar:
    # ── Logo ──
    st.markdown("""
    <div style="padding:1.6rem 0 1.2rem;">
      <div style="display:flex;align-items:center;gap:10px;">
        <div style="background:linear-gradient(135deg,#4f8ef7,#00d2c8);
             width:36px;height:36px;border-radius:9px;display:flex;
             align-items:center;justify-content:center;font-size:1.1rem;
             flex-shrink:0;">🛡️</div>
        <div>
          <div style="font-size:1rem;font-weight:800;color:#e8edf4;
               letter-spacing:-.03em;line-height:1.1;">ResumeGuard</div>
          <div style="font-size:.62rem;color:#475d7a;font-weight:600;
               letter-spacing:.08em;text-transform:uppercase;">Risk Intelligence</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Nav ──
    nav = st.radio(
        "nav", ["📤  Analyze", "📊  Analytics", "🔎  Inspector"],
        label_visibility="collapsed",
    )

    st.markdown("<div style='margin:1rem 0;border-top:1px solid #242d42;'></div>",
                unsafe_allow_html=True)

    # ── Filters ──
    st.markdown("""<div style="font-size:.65rem;font-weight:700;text-transform:uppercase;
        letter-spacing:.1em;color:#475d7a;margin-bottom:.6rem;">Filters</div>""",
        unsafe_allow_html=True)

    _db = SessionLocal()
    _all = _db.query(WorkflowRun).all()
    _db.close()

    _risk_opts = sorted({(r.risk_level or "").upper() for r in _all if r.risk_level})
    # ✅ FIX 2 — normalise dropdown options so no duplicates (APPROVE vs APPROVED etc.)
    _decision_opts = sorted({_normalise_decision(r.decision) for r in _all if r.decision})

    rf        = st.selectbox("Risk Level", ["All"] + list(_risk_opts),     key="sf_risk")
    df_filter = st.selectbox("Decision",   ["All"] + list(_decision_opts), key="sf_dec")

    st.markdown("<div style='margin:1rem 0;border-top:1px solid #242d42;'></div>",
                unsafe_allow_html=True)

    # ── Stats ──
    st.markdown(f"""
    <div style="background:#141824;border:1px solid #242d42;border-radius:10px;
         padding:.9rem 1rem;">
      <div style="font-size:.65rem;font-weight:700;color:#475d7a;
           text-transform:uppercase;letter-spacing:.08em;margin-bottom:.6rem;">Engine</div>
      <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
        <span style="font-size:.75rem;color:#8899b4;">Total Runs</span>
        <span style="font-size:.75rem;font-weight:700;color:#e8edf4;">{len(_all)}</span>
      </div>
      <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
        <span style="font-size:.75rem;color:#8899b4;">Version</span>
        <span style="font-size:.75rem;font-weight:700;color:#4f8ef7;">v2.0</span>
      </div>
      <div style="display:flex;justify-content:space-between;">
        <span style="font-size:.75rem;color:#8899b4;">Model</span>
        <span style="font-size:.75rem;font-weight:700;color:#00d2c8;">Hybrid</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# PAGE HEADER UTILITY
# ═══════════════════════════════════════════════════════════

def topbar(title: str, sub: str):
    st.markdown(f"""
    <div style="padding:2rem 0 1.5rem;border-bottom:1px solid #1c2333;margin-bottom:2rem;">
      <div style="font-size:1.5rem;font-weight:800;color:#e8edf4;
           letter-spacing:-.04em;line-height:1.1;">{title}</div>
      <div style="font-size:.78rem;color:#475d7a;margin-top:.35rem;">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# PAGE ① — ANALYZE
# ═══════════════════════════════════════════════════════════

if "📤" in nav:
    topbar("Resume Analysis",
           "Upload a PDF resume — AI-powered fraud detection and risk scoring in seconds")

    up_col, info_col = st.columns([3, 1], gap="large")

    with info_col:
        st.markdown("""
        <div style="background:#141824;border:1px solid #1c2333;border-radius:12px;
             padding:1.2rem;margin-top:0;">
          <div style="font-size:.75rem;font-weight:700;color:#8899b4;text-transform:uppercase;
               letter-spacing:.08em;margin-bottom:.9rem;">What We Analyse</div>
        """, unsafe_allow_html=True)
        checks = [
            ("🗓", "Date Overlaps",       "Simultaneous full-time jobs"),
            ("🎓", "Seniority Mismatch",  "Title vs graduation year"),
            ("📊", "Academic Integrity",  "CGPA / percentage validity"),
            ("🔑", "Fraud Keywords",      "Scam / illegal / spam terms"),
            ("📋", "Employment Gaps",     "Unexplained career breaks"),
            ("🤖", "LLM Evaluation",      "Semantic quality scoring"),
            ("📐", "Schema Validation",   "Structural completeness"),
            ("🚩", "Impossible Claims",   "AGI / IQ / unrealistic data"),
        ]
        for icon, t, d in checks:
            st.markdown(f"""
            <div style="display:flex;gap:9px;padding:.5rem 0;
                 border-bottom:1px solid #1c2333;">
              <span style="font-size:.95rem;flex-shrink:0;">{icon}</span>
              <div>
                <div style="font-size:.78rem;font-weight:600;color:#dce8f5;">{t}</div>
                <div style="font-size:.68rem;color:#475d7a;">{d}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with up_col:
        uploaded = st.file_uploader(
            "Drop PDF resume here or click to browse",
            type=["pdf"],
            label_visibility="collapsed",
        )

        if not uploaded:
            st.markdown("""
            <div style="background:#141824;border:1.5px dashed #1c2333;border-radius:12px;
                 padding:2.5rem;text-align:center;margin-top:.5rem;">
              <div style="font-size:2rem;margin-bottom:.5rem;">📄</div>
              <div style="font-size:.9rem;font-weight:600;color:#8899b4;">
                Drop your PDF resume here</div>
              <div style="font-size:.75rem;color:#475d7a;margin-top:.3rem;">
                PDF format · Max 10 MB</div>
            </div>
            """, unsafe_allow_html=True)

        if uploaded:

            with st.spinner("🔍  Extracting · Validating · Scoring …"):

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(uploaded.read())
                    tmp_path = tmp_file.name

                doc_text = extract_text_from_pdf(tmp_path)
                result   = workflow.invoke({"document_text": doc_text})
                save_workflow(result)

                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

            # ── Decision banner ──────────────────────────────────
            # ✅ FIX 3 — normalise result decision before display
            dec  = _normalise_decision(result.get("decision") or "")
            rlvl = (result.get("risk_level") or "N/A").upper()
            _, bc, bbg = DECISION_CFG.get(dec, (dec, "#8899b4", "#141824"))

            st.markdown(f"""
            <div style="background:{bbg};border:1.5px solid {bc}40;border-radius:12px;
                 padding:1.3rem 1.6rem;margin:1.2rem 0;
                 display:flex;align-items:center;gap:16px;">
              <div style="font-size:2.2rem;line-height:1;">
                {"✅" if dec=="APPROVE" else "⚠️" if dec=="REVIEW" else "❌"}
              </div>
              <div>
                <div style="font-size:1.05rem;font-weight:800;color:{bc};
                     letter-spacing:-.02em;">{dec} — {rlvl} RISK</div>
                <div style="font-size:.78rem;color:#8899b4;margin-top:3px;">
                  Risk&nbsp;{result.get('risk_score',0)}/100 &nbsp;·&nbsp;
                  Confidence&nbsp;{result.get('final_confidence',0)}/100 &nbsp;·&nbsp;
                  Fraud&nbsp;Signal&nbsp;{result.get('fraud_score',0)}/100
                </div>
              </div>
              <div style="margin-left:auto;display:flex;gap:8px;align-items:center;">
                {risk_pill(rlvl)}
                {decision_pill(dec)}
              </div>
            </div>
            """, unsafe_allow_html=True)

            # ── Three gauges ──────────────────────────────────────
            g1, g2, g3 = st.columns(3)
            with g1:
                st.plotly_chart(
                    gauge_chart(result.get("risk_score", 0),       "Risk Score",   "#ff4f5e"),
                    use_container_width=True, config={"displayModeBar": False})
            with g2:
                st.plotly_chart(
                    gauge_chart(result.get("final_confidence", 0), "Confidence",   "#27d98a"),
                    use_container_width=True, config={"displayModeBar": False})
            with g3:
                st.plotly_chart(
                    gauge_chart(result.get("fraud_score", 0),      "Fraud Signal", "#ffb340"),
                    use_container_width=True, config={"displayModeBar": False})

            # ── Parse explainability ──────────────────────────────
            expl       = _parse_expl(result.get("explainability"))
            components = expl.get("score_components", {})
            reasons    = expl.get("risk_reasons", [])
            total_pen  = expl.get("total_penalty", result.get("total_penalty", 0))

            # ── Two-column detail ─────────────────────────────────
            dc1, dc2 = st.columns(2, gap="large")

            with dc1:
                section_header("📐", "Score Breakdown")
                if components:
                    maxes = {"section_score": 30, "density_score": 20,
                             "garbage_score": 10,  "contact_score": 15,
                             "structure_score": 25}
                    colors = ["#4f8ef7","#00d2c8","#27d98a","#ffb340","#b06cff"]
                    for i, (k, v) in enumerate(components.items()):
                        hbar(k.replace("_score","").replace("_"," ").title(),
                             v, maxes.get(k, 30), colors[i % len(colors)])

                    st.markdown("<div style='margin-top:.5rem;'></div>", unsafe_allow_html=True)
                    st.plotly_chart(radar_chart(components),
                                   use_container_width=True,
                                   config={"displayModeBar": False})

                # Quick score row
                sq1, sq2, sq3 = st.columns(3)
                with sq1: st.metric("Structural", result.get("structural_score", 0))
                with sq2: st.metric("LLM",        result.get("llm_score", 0))
                with sq3: st.metric("Penalty",     total_pen)

            with dc2:
                section_header("⚠️", "Risk Signals",
                               f"{len(reasons)} signal{'s' if len(reasons)!=1 else ''} detected")
                for r in reasons:
                    risk_flag_row(0, r)

                if not reasons:
                    st.success("No fraud signals detected.")

                if result.get("ai_summary"):
                    section_header("🧠", "AI Recruiter Summary")
                    st.markdown(f"""
                    <div style="background:#141824;border:1px solid #1c2333;
                         border-left:2.5px solid #4f8ef7;border-radius:9px;
                         padding:1rem 1.2rem;font-size:.83rem;color:#b8c5d6;
                         line-height:1.7;">{result.get("ai_summary")}</div>
                    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# PAGE ② — ANALYTICS
# ═══════════════════════════════════════════════════════════

elif "📊" in nav:
    topbar("Analytics", "Aggregate risk intelligence across all evaluated resumes")

    runs, df = fetch_runs(rf, df_filter)

    if df.empty:
        st.warning("No records match the selected filters.")
        st.stop()

    # ── KPI row ──────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1: kpi_card("📋", len(df),                                  "Total Runs",    "#4f8ef7")
    with k2: kpi_card("✅", len(df[df["Decision"]=="APPROVE"]),       "Approved",      "#27d98a")
    with k3: kpi_card("⚠️",  len(df[df["Decision"]=="REVIEW"]),        "Under Review",  "#ffb340")
    with k4: kpi_card("❌", len(df[df["Decision"]=="REJECT"]),        "Rejected",      "#ff4f5e")
    with k5: kpi_card("⬡", len(df[df["Risk Level"]=="CRITICAL"]),    "Critical",      "#b06cff")
    with k6:
        avg_r = round(df["Risk Score"].mean(), 1) if len(df) else 0
        kpi_card("📈", avg_r, "Avg Risk",  "#00d2c8",
                 delta=f"Max {df['Risk Score'].max()}")

    st.markdown("<div style='margin:1.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Row 1: Donut + Histogram ──────────────────────────────
    ch1, ch2 = st.columns([1, 2], gap="large")

    with ch1:
        section_header("🎯", "Decision Split")
        app = len(df[df["Decision"]=="APPROVE"])
        rev = len(df[df["Decision"]=="REVIEW"])
        rej = len(df[df["Decision"]=="REJECT"])
        st.plotly_chart(mini_donut(app, rev, rej),
                        use_container_width=True, config={"displayModeBar": False})

    with ch2:
        section_header("📊", "Risk Score Distribution")
        fig_hist = go.Figure(go.Histogram(
            x=df["Risk Score"], nbinsx=20,
            marker_color="#4f8ef7",
            marker_line_color="#0b0e17",
            marker_line_width=1.5,
        ))
        fig_hist.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10), height=240,
            xaxis=dict(gridcolor="#1c2333", color="#475d7a",
                       title=None, tickfont=dict(size=10)),
            yaxis=dict(gridcolor="#1c2333", color="#475d7a",
                       title=None, tickfont=dict(size=10)),
            bargap=0.08,
            font=dict(family="Bricolage Grotesque"),
        )
        st.plotly_chart(fig_hist, use_container_width=True,
                        config={"displayModeBar": False})

    # ── Row 2: Risk level bar + Scatter ──────────────────────
    ch3, ch4 = st.columns(2, gap="large")

    with ch3:
        section_header("🔵", "Risk Level Breakdown")
        lvl_df = df["Risk Level"].value_counts().reset_index()
        lvl_df.columns = ["Level", "Count"]
        color_map = {"LOW":"#27d98a","MEDIUM":"#ffb340","HIGH":"#ff4f5e","CRITICAL":"#b06cff"}
        fig_bar = px.bar(
            lvl_df, x="Level", y="Count",
            color="Level", color_discrete_map=color_map,
            text="Count",
        )
        fig_bar.update_traces(
            textposition="outside",
            textfont=dict(color="#e8edf4", size=12),
            marker_line_color="#0b0e17", marker_line_width=1.5,
        )
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10), height=240,
            xaxis=dict(gridcolor="#1c2333", color="#475d7a",
                       tickfont=dict(size=10), title=None),
            yaxis=dict(gridcolor="#1c2333", color="#475d7a",
                       tickfont=dict(size=10), title=None),
            showlegend=False,
            font=dict(family="Bricolage Grotesque"),
        )
        st.plotly_chart(fig_bar, use_container_width=True,
                        config={"displayModeBar": False})

    with ch4:
        section_header("🔬", "Structural vs LLM Score")
        fig_scatter = px.scatter(
            df, x="Structural", y="LLM Score",
            color="Risk Level", size="Risk Score",
            color_discrete_map=color_map,
            hover_data=["Decision", "Fraud Score"],
            size_max=22,
        )
        fig_scatter.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10), height=240,
            xaxis=dict(gridcolor="#1c2333", color="#475d7a",
                       tickfont=dict(size=10), title=None),
            yaxis=dict(gridcolor="#1c2333", color="#475d7a",
                       tickfont=dict(size=10), title=None),
            legend=dict(font=dict(color="#b8c5d6", size=10)),
            font=dict(family="Bricolage Grotesque"),
        )
        st.plotly_chart(fig_scatter, use_container_width=True,
                        config={"displayModeBar": False})

    # ── Table ─────────────────────────────────────────────────
    section_header("📂", "Run History", f"{len(df)} records")
    display_df = df[[
        "ID","Decision","Risk Level","Risk Score",
        "Fraud Score","Structural","LLM Score","Confidence","Total Penalty","Created"
    ]].copy()

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Risk Score":    st.column_config.ProgressColumn("Risk Score",    min_value=0, max_value=100, format="%d"),
            "Fraud Score":   st.column_config.ProgressColumn("Fraud Score",   min_value=0, max_value=100, format="%d"),
            "Structural":    st.column_config.ProgressColumn("Structural",    min_value=0, max_value=100, format="%d"),
            "LLM Score":     st.column_config.ProgressColumn("LLM Score",     min_value=0, max_value=100, format="%d"),
            "Confidence":    st.column_config.ProgressColumn("Confidence",    min_value=0, max_value=100, format="%d"),
        },
    )

    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇  Export CSV", csv, "resumeguard_export.csv", "text/csv")


# ═══════════════════════════════════════════════════════════
# PAGE ③ — INSPECTOR
# ═══════════════════════════════════════════════════════════

elif "🔎" in nav:
    topbar("Run Inspector", "Deep-dive into any individual resume evaluation")

    runs, _df = fetch_runs()
    if not runs:
        st.warning("No records yet.")
        st.stop()

    # ── Selector ─────────────────────────────────────────────
    opts = {
        # ✅ FIX 3 — normalise decision label in Inspector dropdown too
        f"#{r.id}  ·  {_normalise_decision(r.decision)}  ·  "
        f"{(r.risk_level or '—').upper()}  ·  Score {r.risk_score or 0}": r.id
        for r in runs
    }
    chosen_label = st.selectbox("Select run", list(opts.keys()),
                                label_visibility="collapsed")
    chosen_id    = opts[chosen_label]
    sel          = next((r for r in runs if r.id == chosen_id), None)

    if not sel:
        st.error("Record not found.")
        st.stop()

    # ✅ FIX 3 — normalise decision for header card display
    dec  = _normalise_decision(sel.decision)
    rlvl = (sel.risk_level or "N/A").upper()
    _, bc, bbg = DECISION_CFG.get(dec, (dec, "#8899b4", "#141824"))

    # ── Header card ───────────────────────────────────────────
    st.markdown(f"""
    <div style="background:#141824;border:1px solid #1c2333;border-radius:12px;
         padding:1.4rem 1.8rem;display:flex;align-items:center;
         justify-content:space-between;flex-wrap:wrap;gap:1rem;margin-bottom:1.5rem;">
      <div>
        <div style="font-size:1.35rem;font-weight:800;color:#e8edf4;
             letter-spacing:-.03em;">Run <span style="color:#4f8ef7;">#{sel.id}</span></div>
        <div style="font-size:.72rem;color:#475d7a;margin-top:3px;font-family:'Inconsolata',monospace;">
          {str(sel.created_at)[:19] if sel.created_at else "—"}
        </div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        {decision_pill(dec)}
        {risk_pill(rlvl)}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Score metrics ─────────────────────────────────────────
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1: st.metric("Risk Score",    sel.risk_score       or "—")
    with m2: st.metric("Structural",    sel.structural_score or "—")
    with m3: st.metric("LLM Score",     sel.llm_score        or "—")
    with m4: st.metric("Confidence",    sel.final_confidence or "—")
    with m5: st.metric("Fraud Score",   sel.fraud_score      or "—")
    with m6: st.metric("Total Penalty", sel.total_penalty    or "—")

    st.divider()

    # ── Two-column detail ─────────────────────────────────────
    left, right = st.columns(2, gap="large")

    with left:
        section_header("📈", "Score Gauges")
        ga, gb = st.columns(2)
        with ga:
            st.plotly_chart(
                gauge_chart(sel.risk_score or 0, "Risk Score", "#ff4f5e"),
                use_container_width=True, config={"displayModeBar": False})
        with gb:
            st.plotly_chart(
                gauge_chart(sel.fraud_score or 0, "Fraud Signal", "#ffb340"),
                use_container_width=True, config={"displayModeBar": False})

        expl       = _parse_expl(sel.explainability)
        components = expl.get("score_components", {})
        if components:
            section_header("📐", "Score Components")
            maxes  = {"section_score": 30, "density_score": 20,
                      "garbage_score": 10,  "contact_score": 15, "structure_score": 25}
            colors = ["#4f8ef7","#00d2c8","#27d98a","#ffb340","#b06cff"]
            for i, (k, v) in enumerate(components.items()):
                hbar(k.replace("_score","").replace("_"," ").title(),
                     v, maxes.get(k, 30), colors[i % len(colors)])
            st.plotly_chart(radar_chart(components),
                            use_container_width=True, config={"displayModeBar": False})

    with right:
        reasons = _parse_reasons(sel)
        section_header("⚠️", "Risk Signals",
                       f"{len(reasons)} signal{'s' if len(reasons)!=1 else ''}")
        if reasons:
            for r in reasons:
                risk_flag_row(0, r)
        else:
            st.success("No fraud signals detected.")

        section_header("✅", "Validation")
        if sel.validation and "failed" in (sel.validation or "").lower():
            st.error(sel.validation)
        elif sel.validation and sel.validation.lower() not in ("passed","none",""):
            st.warning(sel.validation)
        else:
            st.success("Schema validation passed — no structural errors.")

        if sel.ai_summary:
            section_header("🧠", "AI Summary")
            st.markdown(f"""
            <div style="background:#141824;border:1px solid #1c2333;
                 border-left:2.5px solid #4f8ef7;border-radius:9px;
                 padding:1rem 1.2rem;font-size:.83rem;color:#b8c5d6;
                 line-height:1.7;">{sel.ai_summary}</div>
            """, unsafe_allow_html=True)

    st.divider()

    # ── Raw data tabs ─────────────────────────────────────────
    t1, t2, t3, t4, t5 = st.tabs([
        "📄 Document Text",
        "📦 Processed Data",
        "✅ Validated Data",
        "🔬 Integrity Report",
        "🤖 LLM Report",
    ])

    with t1:
        st.text_area("", sel.document_text or "", height=320,
                     label_visibility="collapsed")

    with t2:
        try:    st.json(json.loads(sel.processed_data) if sel.processed_data else {})
        except: st.text(sel.processed_data or "No data available")

    with t3:
        try:    st.json(json.loads(sel.validated_data) if sel.validated_data else {})
        except: st.text(sel.validated_data or "No data available")

    with t4:
        try:    st.json(json.loads(sel.integrity_report) if sel.integrity_report else expl)
        except: st.text(sel.integrity_report or "No data available")

    with t5:
        try:    st.json(json.loads(sel.llm_full_report) if sel.llm_full_report else {})
        except: st.text(sel.llm_full_report or "No data available")