import streamlit as st
import requests
import whisper
import tempfile
import os
import traceback
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
#  PAGE CONFIG  (must be the very first Streamlit call)
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HostelSOS",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
#  CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────
API_URL = "http://127.0.0.1:8000"

VALID_STATUSES = ["Submitted", "In Progress", "Resolved"]

CATEGORIES = {
    "Bathroom & Hygiene":         "Sanitation Dept.",
    "Anti-Ragging & Safety":      "Student Welfare Cell",
    "Mess & Food Quality":        "Hostel Mess Admin",
    "Academic Issues":            "Academic Office",
    "Infrastructure/Maintenance": "Maintenance Dept.",
    "Other":                      "General Admin",
}

# SVG icons — no external URLs needed
CAT_SVGS = {
    "Bathroom & Hygiene": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h16M4 6h16M4 18h7"/><circle cx="17" cy="18" r="3"/></svg>""",
    "Anti-Ragging & Safety": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>""",
    "Mess & Food Quality": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/></svg>""",
    "Academic Issues": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>""",
    "Infrastructure/Maintenance": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>""",
    "Other": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>""",
}

STATUS_SVGS = {
    "Submitted": """<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13"/><path d="M22 2L15 22 11 13 2 9l20-7z"/></svg>""",
    "In Progress": """<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-.18-5.5"/></svg>""",
    "Resolved": """<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>""",
}

TIMELINE_SVGS = {
    "Submitted": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>""",
    "In Progress": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>""",
    "Resolved": """<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>""",
}

# ──────────────────────────────────────────────────────────────────────────────
#  WHISPER — cached so the model loads once per session
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading speech model…")
def load_whisper():
    return whisper.load_model("base")

whisper_model = load_whisper()

# ──────────────────────────────────────────────────────────────────────────────
#  SESSION STATE DEFAULTS
# ──────────────────────────────────────────────────────────────────────────────
for key, default in {
    "description":      "",
    "voice_text":       "",
    "dark_mode":        True,
    "submit_result":    None,
    "is_submitting":    False,
    "search_clicked":   False,
    "last_track_id":    "",
    "track_result":     None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ──────────────────────────────────────────────────────────────────────────────
#  FIX 2 — normalize_status
# ──────────────────────────────────────────────────────────────────────────────
def normalize_status(raw: str) -> str:
    """Standardize status strings from any source to one of VALID_STATUSES."""
    if not raw:
        return "Submitted"
    s = str(raw).strip().lower()
    if s in ("in progress", "inprogress", "in-progress", "processing", "pending"):
        return "In Progress"
    if s in ("resolved", "done", "closed", "fixed", "completed"):
        return "Resolved"
    return "Submitted"

# ──────────────────────────────────────────────────────────────────────────────
#  FIX 3+4+10 — safe API response parsing
# ──────────────────────────────────────────────────────────────────────────────
def safe_parse_response(res: dict) -> dict:
    """Extract and sanitize fields from an API complaint response."""
    try:
        raw_conf = res.get("confidence", 0) or 0
        conf_pct = int(float(raw_conf) * 100)
    except (TypeError, ValueError):
        conf_pct = 0

    raw_id = res.get("id", "")
    cid = str(raw_id).strip() if raw_id not in (None, "", 0) else ""

    return {
        "id":          cid,
        "student_name": str(res.get("student_name") or "Anonymous"),
        "description": str(res.get("description") or "No description."),
        "category":    str(res.get("category")    or "Other"),
        "department":  str(res.get("department")  or "General Admin"),
        "status":      normalize_status(res.get("status", "")),
        "resolution":  str(res.get("resolution")  or ""),
        "conf_pct":    conf_pct,
    }

# ──────────────────────────────────────────────────────────────────────────────
#  FIX 6 — API helpers with structured error handling
# ──────────────────────────────────────────────────────────────────────────────
def api_submit_complaint(student_name: str, description: str) -> tuple[dict | None, str | None]:
    """Returns (data, error_message)."""
    try:
        r = requests.post(
            f"{API_URL}/complaints",
            json={"student_name": student_name, "description": description},
            timeout=10,
        )
        print("Response:", r.text)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to server. Is FastAPI running on port 8000?"
    except requests.exceptions.Timeout:
        return None, "Request timed out. Server may be overloaded."
    except requests.exceptions.HTTPError as e:
        return None, f"Server error {e.response.status_code}: {e.response.text[:200]}"
    except Exception:
        return None, f"Unexpected error:\n{traceback.format_exc()}"


def api_get_complaints() -> tuple[list, str | None]:
    """Returns (complaints_list, error_message)."""
    try:
        r = requests.get(f"{API_URL}/complaints", timeout=10)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else [], None
    except requests.exceptions.ConnectionError:
        return [], "Cannot connect to server. Is FastAPI running?"
    except requests.exceptions.Timeout:
        return [], "Request timed out."
    except requests.exceptions.HTTPError as e:
        return [], f"Server error {e.response.status_code}"
    except Exception:
        return [], f"Unexpected error:\n{traceback.format_exc()}"


def api_update_status(complaint_id, status: str, resolution: str = "") -> tuple[bool, str | None]:
    """Returns (success, error_message)."""
    try:
        r = requests.put(
            f"{API_URL}/complaints/{complaint_id}/status",
            json={"status": status, "resolution": resolution},
            timeout=10,
        )
        if r.status_code == 200:
            return True, None
        return False, f"Server returned {r.status_code}: {r.text[:200]}"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to server."
    except Exception:
        return False, traceback.format_exc()

# ──────────────────────────────────────────────────────────────────────────────
#  UI HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def status_badge_html(status: str) -> str:
    norm = normalize_status(status)
    cls  = {
        "Submitted":   "badge-submitted",
        "In Progress": "badge-progress",
        "Resolved":    "badge-resolved",
    }.get(norm, "badge-submitted")
    svg = STATUS_SVGS.get(norm, "")
    return f'<span class="badge {cls}">{svg} {norm}</span>'


def confidence_color(pct: int) -> str:
    if pct >= 80: return "#34d399"
    if pct >= 60: return "#fbbf24"
    return "#f87171"


def safe_key(*parts) -> str:
    """Build a unique, safe widget key from arbitrary parts."""
    return "_".join(str(p).replace(" ", "_").replace("/", "_").replace("-", "_") for p in parts)

# ──────────────────────────────────────────────────────────────────────────────
#  GLOBAL CSS
# ──────────────────────────────────────────────────────────────────────────────
def inject_css():
    dm = st.session_state.dark_mode
    bg_app       = "#000000"  if dm else "#fffbf0"
    bg_card      = "#0d0d0d"  if dm else "#ffffff"
    bg_card2     = "#1a1a1a"  if dm else "#fff8e6"
    bg_sidebar   = "#0a0a0a"  if dm else "#ffffff"
    border_color = "#00d4d4"  if dm else "#ff8c00"
    text_primary = "#00ffff"  if dm else "#1a1a1a"
    text_muted   = "#008080"  if dm else "#8b4513"
    input_bg     = "#0d0d0d"  if dm else "#ffffff"
    badge_sub_bg = "#001a1a"  if dm else "#ffe6cc"
    badge_sub_fg = "#00ffff"  if dm else "#ff6600"
    badge_sub_bd = "#00a8a8"  if dm else "#ff8c00"
    badge_prg_bg = "#001f00"  if dm else "#fffacd"
    badge_prg_fg = "#00ffff"  if dm else "#ff8c00"
    badge_prg_bd = "#00a8a8"  if dm else "#ffaa00"
    badge_res_bg = "#001a00"  if dm else "#ffd699"
    badge_res_fg = "#00ffff"  if dm else "#ff6600"
    badge_res_bd = "#00a800"  if dm else "#ff8c00"
    chip_bg      = "#1a1a1a"  if dm else "#fff8e6"
    chip_fg      = "#00ffff"  if dm else "#ff6600"
    chip_bd      = "#00a8a8"  if dm else "#ff8c00"
    conf_bar_bg  = "#1a1a1a"  if dm else "#ffe6cc"
    metric_bg    = "#0d0d0d"  if dm else "#fff8e6"
    tracking_bg  = "#0a0a0a"  if dm else "#fffacd"
    desc_bg      = "#050505"  if dm else "#fff8e6"
    success_bg   = "#001a00"  if dm else "#ffd699"
    success_bd   = "#00a800"  if dm else "#ff8c00"
    error_bg     = "#1a0000"  if dm else "#ffcccc"
    error_bd     = "#a80000"  if dm else "#ff3300"

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{
    background-color: {bg_app} !important;
    font-family: 'DM Sans', sans-serif;
    color: {text_primary};
}}
[data-testid="stHeader"] {{
    display: block !important;
}}
.stDeployButton {{ display: none; }}

[data-testid="stSidebar"] {{
    background: {bg_sidebar} !important;
    border-right: 1px solid {border_color};
}}
[data-testid="stSidebar"] * {{ color: {text_primary} !important; }}

.block-container {{ padding: 1.5rem 2rem 4rem !important; }}

.card {{
    background: {bg_card};
    border: 1px solid {border_color};
    border-radius: 14px;
    padding: 1.4rem 1.5rem;
    margin-bottom: 1rem;
}}
.card-accent {{ border-left: 3px solid {f'#00d4d4' if dm else '#ff8c00'}; }}
.card-title {{
    font-family: 'Syne', sans-serif;
    font-size: 0.95rem;
    font-weight: 700;
    letter-spacing: 0.4px;
    margin: 0 0 1rem;
    color: {text_primary};
    display: flex; align-items: center; gap: 8px;
}}

.badge {{
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 11px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    font-family: 'DM Mono', monospace;
    letter-spacing: 0.5px;
    vertical-align: middle;
}}
.badge-submitted {{ background:{badge_sub_bg}; color:{badge_sub_fg}; border:1px solid {badge_sub_bd}; }}
.badge-progress  {{ background:{badge_prg_bg}; color:{badge_prg_fg}; border:1px solid {badge_prg_bd}; }}
.badge-resolved  {{ background:{badge_res_bg}; color:{badge_res_fg}; border:1px solid {badge_res_bd}; }}

.chip {{
    display: inline-flex; align-items: center; gap: 5px;
    padding: 2px 9px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    background: {chip_bg};
    color: {chip_fg};
    border: 1px solid {chip_bd};
}}

.conf-bar-bg   {{ background:{conf_bar_bg}; border-radius:4px; height:5px; margin-top:5px; }}
.conf-bar-fill {{ height:5px; border-radius:4px; }}

.metric-card {{
    background: {metric_bg};
    border: 1px solid {border_color};
    border-radius: 10px;
    padding: 1.1rem;
    text-align: center;
}}
.metric-num   {{ font-size:1.9rem; font-weight:700; color:{f'#00d4d4' if dm else '#ff8c00'}; font-family:'Syne',sans-serif; }}
.metric-label {{ font-size:0.7rem; color:{text_muted}; text-transform:uppercase; letter-spacing:1.2px; margin-top:4px; }}

.tracking-box {{
    background: {tracking_bg};
    border: 1px solid {f'#00d4d4' if dm else '#ff8c00'};
    border-radius: 10px;
    padding: 1rem 1.5rem;
    font-family: 'DM Mono', monospace;
    font-size: 1.05rem;
    color: {f'#00ffff' if dm else '#ff6600'};
    letter-spacing: 2.5px;
    text-align: center;
}}

.voice-box {{
    background: {f'rgba(0,212,212,0.08)' if dm else 'rgba(255,140,0,0.08)'};
    border: 1px solid {f'rgba(0,212,212,0.22)' if dm else 'rgba(255,140,0,0.22)'};
    border-radius: 10px;
    padding: 11px 16px;
    font-size: 14px;
    color: {f'#00ffff' if dm else '#ff6600'};
    font-style: italic;
    margin-top: 10px;
    line-height: 1.6;
    display: flex; align-items: flex-start; gap: 8px;
}}
.voice-icon svg {{ flex-shrink:0; margin-top:2px; }}

.complaint-card {{
    background: {bg_card};
    border: 1px solid {border_color};
    border-left: 3px solid {f'#00d4d4' if dm else '#ff8c00'};
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-bottom: 8px;
}}
.complaint-id {{
    font-size: 10px; font-weight:600; letter-spacing:2px;
    text-transform:uppercase; color:{f'#00d4d4' if dm else '#ff8c00'}; margin-bottom:5px;
    font-family:'DM Mono',monospace;
}}
.complaint-name {{ font-family:'Syne',sans-serif; font-size:14px; font-weight:700; color:{text_primary}; margin-bottom:3px; }}
.complaint-desc {{ font-size:13px; color:{text_muted}; margin-bottom:9px; line-height:1.5; }}
.complaint-tags {{ display:flex; gap:6px; flex-wrap:wrap; align-items:center; }}
.ctag {{ font-size:11px; padding:3px 10px; border-radius:999px; font-weight:500; display:inline-flex; align-items:center; gap:4px; }}
.ctag-cat  {{ background:{f'rgba(0,212,212,.14)' if dm else 'rgba(255,140,0,.14)'}; color:{f'#00ffff' if dm else '#ff6600'}; border:1px solid {f'rgba(0,212,212,.25)' if dm else 'rgba(255,140,0,.25)'}; }}
.ctag-dept {{ background:{f'rgba(0,212,212,.11)' if dm else 'rgba(255,140,0,.11)'}; color:{f'#00ffff' if dm else '#ff6600'}; border:1px solid {f'rgba(0,212,212,.25)' if dm else 'rgba(255,140,0,.25)'}; }}
.ctag-status-open     {{ background:{f'rgba(0,212,212,.11)' if dm else 'rgba(255,140,0,.11)'}; color:{f'#00ffff' if dm else '#ff6600'}; border:1px solid {f'rgba(0,212,212,.25)' if dm else 'rgba(255,140,0,.25)'}; }}
.ctag-status-resolved {{ background:{f'rgba(0,212,212,.11)' if dm else 'rgba(255,140,0,.11)'}; color:{f'#00ffff' if dm else '#ff6600'}; border:1px solid {f'rgba(0,212,212,.25)' if dm else 'rgba(255,140,0,.25)'}; }}
.ctag-status-default  {{ background:rgba(255,255,255,.06); color:{text_muted}; border:1px solid {border_color}; }}

.desc-block {{
    background:{desc_bg}; border-radius:8px;
    padding:0.75rem 1rem; font-size:0.85rem;
    color:{text_primary}; line-height:1.6; margin:0.75rem 0;
}}

.stTextInput>div>div>input,
.stTextArea>div>div>textarea {{
    background: {input_bg} !important;
    border: 1px solid {border_color} !important;
    border-radius: 9px !important;
    color: {text_primary} !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 14px !important;
    caret-color: {f'#00d4d4' if dm else '#ff8c00'};
}}
.stTextInput>div>div>input:focus,
.stTextArea>div>div>textarea:focus {{
    border-color: {f'#00d4d4' if dm else '#ff8c00'} !important;
    box-shadow: 0 0 0 3px {f'rgba(0,212,212,0.13)' if dm else 'rgba(255,140,0,0.13)'} !important;
}}
label, .stTextInput label, .stTextArea label {{
    color: {text_muted} !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}}
.stSelectbox>div>div {{
    background: {input_bg} !important;
    border: 1px solid {border_color} !important;
    border-radius: 9px !important;
    color: {text_primary} !important;
}}

.stButton>button {{
    background: {f'linear-gradient(135deg,#00d4d4,#009a9a)' if dm else 'linear-gradient(135deg,#ff8c00,#ff6600)'}  !important;
    color: {f'#000000' if dm else '#ffffff'} !important;
    border: none !important;
    border-radius: 9px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    letter-spacing: 0.5px;
    padding: 0.55rem 1.4rem !important;
    transition: all 0.18s ease !important;
}}
.stButton>button:hover {{
    background: {f'linear-gradient(135deg,#00ffff,#00d4d4)' if dm else 'linear-gradient(135deg,#ffaa00,#ff8c00)'} !important;
    transform: translateY(-1px);
    box-shadow: 0 7px 22px {f'rgba(0,212,212,0.32)' if dm else 'rgba(255,140,0,0.32)'} !important;
}}
.stButton>button:disabled {{
    background: rgba(124,58,237,0.3) !important;
    cursor: not-allowed !important;
    transform: none !important;
    box-shadow: none !important;
}}

.stSuccess {{ background:{success_bg} !important; border:1px solid {success_bd} !important; border-radius:9px !important; }}
.stError   {{ background:{error_bg}   !important; border:1px solid {error_bd}   !important; border-radius:9px !important; }}
.stWarning {{ background:rgba(245,158,11,.1) !important; border:1px solid rgba(245,158,11,.3) !important; border-radius:9px !important; }}
.stInfo    {{ background:rgba(99,102,241,.08) !important; border:1px solid rgba(99,102,241,.25) !important; border-radius:9px !important; }}

hr {{ border-color: {border_color} !important; }}

[data-testid="stSidebar"] .stRadio>div {{ gap: 4px; }}
[data-testid="stSidebar"] .stRadio label {{
    font-size: 13px !important;
    padding: 7px 10px;
    border-radius: 8px;
    cursor: pointer;
    text-transform: none !important;
    letter-spacing: 0 !important;
    font-weight: 400 !important;
}}
[data-testid="stSidebar"] .stRadio label:hover {{ background: {f'rgba(0,212,212,0.1)' if dm else 'rgba(255,140,0,0.1)'}; }}
[data-testid="stSidebar"] .stButton>button {{
    background: {f'rgba(0,212,212,0.12)' if dm else 'rgba(255,140,0,0.12)'} !important;
    border: 1px solid {f'rgba(0,212,212,0.25)' if dm else 'rgba(255,140,0,0.25)'} !important;
    color: {f'#00ffff' if dm else '#ff6600'} !important;
    font-size: 16px !important;
    padding: 0.3rem 0.6rem !important;
    border-radius: 8px !important;
}}

.hero-wrap {{
    position: relative;
    background: {f'linear-gradient(135deg, #000000 0%, #0a1a1a 50%, #001010 100%)' if dm else 'linear-gradient(135deg, #fffbf0 0%, #fff8e6 50%, #ffe6cc 100%)'};
    border-radius: 18px;
    padding: 2.2rem 2rem 1.8rem;
    margin-bottom: 1.8rem;
    overflow: hidden;
    border: 1px solid {f'rgba(0,212,212,0.07)' if dm else 'rgba(255,140,0,0.07)'};
}}
.hero-wrap::before {{
    content:''; position:absolute; top:-50px; right:-50px;
    width:200px; height:200px;
    background: {f'radial-gradient(circle,rgba(0,212,212,0.28) 0%,transparent 70%)' if dm else 'radial-gradient(circle,rgba(255,140,0,0.28) 0%,transparent 70%)'};
    pointer-events:none;
}}
.hero-wrap::after {{
    content:''; position:absolute; bottom:-35px; left:-35px;
    width:160px; height:160px;
    background: {f'radial-gradient(circle,rgba(0,212,212,0.18) 0%,transparent 70%)' if dm else 'radial-gradient(circle,rgba(255,140,0,0.18) 0%,transparent 70%)'};
    pointer-events:none;
}}
.hero-tag {{
    display:inline-block; background:{f'rgba(0,212,212,0.18)' if dm else 'rgba(255,140,0,0.18)'};
    color:{f'#00ffff' if dm else '#ff6600'}; font-size:10px; font-weight:600;
    letter-spacing:2px; text-transform:uppercase;
    padding:4px 12px; border-radius:999px;
    border:1px solid {f'rgba(0,212,212,0.3)' if dm else 'rgba(255,140,0,0.3)'}; margin-bottom:10px;
}}
.hero-title {{
    font-family:'Syne',sans-serif; font-size:2.3rem; font-weight:800;
    line-height:1.1; margin:0 0 6px;
    background: {f'linear-gradient(135deg,#00ffff 30%,#00d4d4 65%,#00ffff 100%)' if dm else 'linear-gradient(135deg,#ff8c00 30%,#ffaa00 65%,#ff6600 100%)'};
    -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}}
.hero-sub {{ font-size:14px; color:rgba(232,230,240,0.52); margin:0; font-weight:300; }}
.hero-pills {{ display:flex; gap:8px; margin-top:1rem; flex-wrap:wrap; }}
.hero-pill {{
    font-size:11px; padding:4px 10px; border-radius:999px;
    border:1px solid {f'rgba(0,212,212,0.2)' if dm else 'rgba(255,140,0,0.2)'}; color:{f'rgba(0,255,255,0.55)' if dm else 'rgba(255,140,0,0.55)'};
    display:inline-flex; align-items:center; gap:5px;
}}

.result-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:1rem; }}
.result-chip {{
    background:{bg_card2}; border:1px solid {border_color};
    border-radius:10px; padding:12px 14px;
}}
.rc-label {{ font-size:10px; font-weight:600; letter-spacing:1.5px; text-transform:uppercase; color:{text_muted}; margin-bottom:3px; }}
.rc-val {{ font-family:'Syne',sans-serif; font-size:15px; font-weight:700; color:{f'#00ffff' if dm else '#ff6600'}; display:flex; align-items:center; gap:6px; }}

.empty-state {{ text-align:center; padding:2.5rem 1rem; color:{text_muted}; font-size:14px; }}
.es-icon {{ margin-bottom:8px; }}

.page-title {{ font-family:'Syne',sans-serif; font-size:1.7rem; font-weight:800; color:{text_primary}; margin-bottom:3px; }}
.page-sub   {{ color:{text_muted}; font-size:0.88rem; margin-bottom:1.5rem; }}

.error-detail {{
    background:{error_bg}; border:1px solid {error_bd};
    border-radius:9px; padding:0.75rem 1rem;
    font-family:'DM Mono',monospace; font-size:11px;
    color:#f87171; white-space:pre-wrap; margin-top:6px;
}}
</style>
""", unsafe_allow_html=True)

inject_css()

# ──────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    col_logo, col_toggle = st.columns([4, 1])
    with col_logo:
        st.markdown("""
        <div style="padding:0.9rem 0 1rem; border-bottom:1px solid rgba(255,255,255,0.06); margin-bottom:1.2rem;">
            <div style="font-family:'Syne',sans-serif; font-size:1.35rem; font-weight:800; color:#00ffff;">
                <svg style="vertical-align:middle;margin-right:6px;" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                HostelSOS
            </div>
            <div style="font-size:0.72rem; color:#4b5563; margin-top:2px;">Smart Campus Complaint System</div>
        </div>
        """, unsafe_allow_html=True)
    with col_toggle:
        st.markdown("<br>", unsafe_allow_html=True)
        toggle_label = "Light" if st.session_state.dark_mode else "Dark"
        if st.button("☀" if st.session_state.dark_mode else "◑", help=f"Switch to {toggle_label} mode", key="theme_toggle"):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

    page = st.radio(
        "Navigation",
        ["Submit Complaint", "Track Complaint", "Admin Dashboard"],
        label_visibility="collapsed",
        key="nav_radio",
    )

    st.markdown("---")

    # Live sidebar stats
    sidebar_complaints, sidebar_err = api_get_complaints()
    if sidebar_err:
        st.caption("Server offline — stats unavailable")
        total = pending = resolved = 0
    else:
        total    = len(sidebar_complaints)
        resolved = sum(1 for c in sidebar_complaints if normalize_status(c.get("status","")) == "Resolved")
        pending  = total - resolved

    st.markdown(f"""
    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:7px; margin-top:0.3rem;">
        <div class="metric-card"><div class="metric-num">{total}</div><div class="metric-label">Total</div></div>
        <div class="metric-card"><div class="metric-num" style="color:#fbbf24;">{pending}</div><div class="metric-label">Open</div></div>
        <div class="metric-card"><div class="metric-num" style="color:#34d399;">{resolved}</div><div class="metric-label">Done</div></div>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — SUBMIT COMPLAINT
# ══════════════════════════════════════════════════════════════════════════════
if page == "Submit Complaint":

    st.markdown("""
    <div class="hero-wrap">
        <div class="hero-tag">Hostel Management System</div>
        <div class="hero-title">HostelSOS</div>
        <p class="hero-sub">Report issues instantly — voice or text. We've got you covered.</p>
        <div class="hero-pills">
            <span class="hero-pill">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
                Voice input
            </span>
            <span class="hero-pill">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                AI categorisation
            </span>
            <span class="hero-pill">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
                Live tracking
            </span>
            <span class="hero-pill">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                Email alerts
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_form, col_info = st.columns([2, 1], gap="large")

    with col_form:
        # ── Voice Input ────────────────────────────────────────────────────
        st.markdown("""
        <div class="card-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
            Voice Input
        </div>
        """, unsafe_allow_html=True)

        try:
            from audio_recorder_streamlit import audio_recorder
            audio_bytes = audio_recorder(
                text="Hold to Record",
                recording_color="#7c3aed",
                neutral_color="#4b4b6b",
                icon_name="microphone",
                icon_size="2x",
            )
        except ImportError:
            st.info("Install audio_recorder_streamlit to enable voice input.")
            audio_bytes = None

        # FIX 7 — delete temp audio file after transcription
        if audio_bytes:
            tmp_path = None
            try:
                with st.spinner("Transcribing…"):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                        tmp.write(audio_bytes)
                        tmp_path = tmp.name
                    result = whisper_model.transcribe(tmp_path)
                    transcribed = result.get("text", "").strip()
                    if transcribed:
                        st.session_state.voice_text = transcribed
                        st.session_state["input_description"] = transcribed
                        st.session_state.description = transcribed

                        st.rerun()   # 👈 THIS IS THE MAGIC LINE
            except Exception as e:
                st.error(f"Transcription failed: {e}")
            finally:
                # FIX 7 — always clean up
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

        if st.session_state.voice_text:
            st.markdown(f"""
            <div class="voice-box">
                <span class="voice-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/></svg>
                </span>
                <span>{st.session_state.voice_text}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Submit Form ────────────────────────────────────────────────────
        st.markdown("""
        <div class="card-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00ffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            Submit a Complaint
        </div>
        """, unsafe_allow_html=True)

        student_name = st.text_input(
            "Your Name",
            placeholder="e.g. Arjun Sharma",
            key="input_student_name",
        )
        description = st.text_area(
            "Describe your issue",
            value=st.session_state.get("input_description", ""),
            placeholder="e.g. Water supply has been cut since last night in Block C, Room 204…",
            height=120,
            key="input_description",
        )
        # FIX 8 — sync back; prefer voice if text area is blank
        st.session_state.description = description

        # FIX 11 — disable button while a submission is in progress
        submit_disabled = st.session_state.is_submitting
        if st.button(
            "Submitting…" if submit_disabled else "Submit Complaint",
            use_container_width=True,
            disabled=submit_disabled,
            key="btn_submit",
        ):
            # FIX 8 — correct fallback order
            final_desc = (description or st.session_state.voice_text).strip()
            if not student_name.strip():
                st.warning("Please enter your name.")
            elif not final_desc:
                st.warning("Please describe the issue or use voice input.")
            else:
                st.session_state.is_submitting = True
                with st.spinner("Submitting to server…"):
                    res, err = api_submit_complaint(student_name.strip(), final_desc)

                st.session_state.is_submitting = False

                if err:
                    st.error("Submission failed")
                    st.markdown(f'<div class="error-detail">{err}</div>', unsafe_allow_html=True)
                elif res:
                    st.session_state.submit_result = res
                    st.session_state.description   = ""
                    st.session_state.voice_text    = ""
                    st.success("Complaint submitted successfully!")

        # Show last result (FIX 3+4 — safe parsing)
        if st.session_state.submit_result:
            p = safe_parse_response(st.session_state.submit_result)
            clr = confidence_color(p["conf_pct"])

            if p["id"]:
                st.markdown(
                    f'<div class="tracking-box">{p["id"]}</div>'
                    '<div style="text-align:center;font-size:11px;color:#6b7280;margin-top:5px;">Save your tracking ID</div>',
                    unsafe_allow_html=True,
                )

            cat_svg = CAT_SVGS.get(p["category"], CAT_SVGS["Other"])
            st.markdown(f"""
            <div class="result-grid">
                <div class="result-chip">
                    <div class="rc-label">Category</div>
                    <div class="rc-val">{cat_svg} {p['category']}</div>
                </div>
                <div class="result-chip">
                    <div class="rc-label">Department</div>
                    <div class="rc-val">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
                        {p['department']}
                    </div>
                </div>
                <div class="result-chip" style="grid-column:1/-1;">
                    <div class="rc-label">Confidence</div>
                    <div class="rc-val" style="color:{clr};">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="{clr}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                        {p['conf_pct']}%
                    </div>
                    <div class="conf-bar-bg"><div class="conf-bar-fill" style="width:{p['conf_pct']}%;background:{clr};"></div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_info:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("""
        <div class="card-title">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            Categories
        </div>
        """, unsafe_allow_html=True)
        for cat, dept in CATEGORIES.items():
            svg = CAT_SVGS[cat]
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:9px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                {svg}
                <div>
                    <div style="font-size:0.8rem;">{cat}</div>
                    <div style="font-size:0.7rem;color:#6b7280;">→ {dept}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""
        <div class="card" style="margin-top:1rem;">
            <div class="card-title">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                Tips
            </div>
            <div style="font-size:0.78rem;color:#6b7280;line-height:2;">
                <div style="display:flex;align-items:center;gap:6px;">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    Mention exact room / block / floor
                </div>
                <div style="display:flex;align-items:center;gap:6px;">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    State how long the issue has existed
                </div>
                <div style="display:flex;align-items:center;gap:6px;">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    Be specific — good detail = faster fix
                </div>
                <div style="display:flex;align-items:center;gap:6px;">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    Use voice input for hands-free reporting
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — TRACK COMPLAINT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Track Complaint":
    st.markdown('<div class="page-title">Track Your Complaint</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Enter your tracking ID, or browse all submitted complaints below.</div>', unsafe_allow_html=True)

    tc1, tc2 = st.columns([4, 1])
    with tc1:
        track_id_input = st.text_input(
            "",
            placeholder="Enter Complaint ID…",
            label_visibility="collapsed",
            key="track_id_input",
        )
    with tc2:
        # FIX 5 — tracking only runs on explicit button click
        search_clicked = st.button("Search", use_container_width=True, key="btn_search")

    if search_clicked:
        st.session_state.search_clicked = True
        st.session_state.last_track_id  = track_id_input.strip()
        st.session_state.track_result   = None  # reset previous

    if st.session_state.search_clicked and st.session_state.last_track_id:
        tid = st.session_state.last_track_id
        complaints, err = api_get_complaints()

        if err:
            st.error("Could not reach server")
            st.markdown(f'<div class="error-detail">{err}</div>', unsafe_allow_html=True)
        else:
            found = next(
                (c for c in complaints if str(c.get("id","")).strip() == tid),
                None,
            )
            if not found:
                st.error(f"No complaint found with ID: {tid}")
            else:
                p = safe_parse_response(found)
                clr = confidence_color(p["conf_pct"])

                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    st.markdown(f'<div class="metric-card"><div class="metric-num" style="font-size:0.9rem;font-family:\'DM Mono\';">{p["id"]}</div><div class="metric-label">Tracking ID</div></div>', unsafe_allow_html=True)
                with mc2:
                    st.markdown(f'<div class="metric-card"><div style="margin:10px 0;">{status_badge_html(p["status"])}</div><div class="metric-label">Status</div></div>', unsafe_allow_html=True)
                with mc3:
                    st.markdown(f'<div class="metric-card"><div style="font-size:0.82rem;font-weight:600;color:#34d399;padding:10px 0;">{p["department"]}</div><div class="metric-label">Assigned To</div></div>', unsafe_allow_html=True)

                cat_svg = CAT_SVGS.get(p["category"], CAT_SVGS["Other"])
                st.markdown(f"""
                <div class="card card-accent" style="margin-top:1rem;">
                    <div style="font-size:0.7rem;color:#6b7280;text-transform:uppercase;letter-spacing:1px;">Description</div>
                    <div class="desc-block">{p['description']}</div>
                    <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center;font-size:0.75rem;color:#6b7280;">
                        <span class="chip">{cat_svg} {p['category']}</span>
                        <span style="display:flex;align-items:center;gap:4px;">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                            {p['student_name']}
                        </span>
                        <span style="color:{clr};">Confidence: {p['conf_pct']}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Timeline
                st.markdown('<div style="font-size:0.88rem;font-weight:600;color:#a78bfa;margin:1.2rem 0 0.6rem;">Status Timeline</div>', unsafe_allow_html=True)
                steps    = ["Submitted", "In Progress", "Resolved"]
                step_idx = steps.index(p["status"]) if p["status"] in steps else 0
                tcols    = st.columns(3)
                for i, s in enumerate(steps):
                    done   = i <= step_idx
                    active = i == step_idx
                    bdr    = "#7c3aed" if active else ("#34d399" if (done and s == "Resolved") else ("#7c3aed" if done else "rgba(255,255,255,0.08)"))
                    clr2   = "#34d399" if (done and s == "Resolved") else ("#a78bfa" if done else "#4b5563")
                    svg    = TIMELINE_SVGS[s]
                    # Recolor SVG stroke for inactive steps
                    display_svg = svg.replace('stroke="#a78bfa"', f'stroke="{clr2}"').replace('stroke="#34d399"', f'stroke="{clr2}"')
                    with tcols[i]:
                        st.markdown(f"""
                        <div style="border:2px solid {bdr};border-radius:10px;padding:0.9rem;text-align:center;">
                            <div style="display:flex;justify-content:center;">{display_svg}</div>
                            <div style="font-size:0.82rem;font-weight:600;color:{clr2};margin-top:6px;">{s}</div>
                        </div>
                        """, unsafe_allow_html=True)

                if p["resolution"]:
                    st.markdown(f"""
                    <div class="card" style="margin-top:1rem;border-left:3px solid #34d399;">
                        <div style="font-size:0.7rem;color:#34d399;text-transform:uppercase;letter-spacing:1px;margin-bottom:7px;display:flex;align-items:center;gap:5px;">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                            Admin Response
                        </div>
                        <div style="font-size:0.87rem;line-height:1.6;">{p['resolution']}</div>
                    </div>
                    """, unsafe_allow_html=True)

    # ── Browse all ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div style="font-size:0.82rem;color:#6b7280;margin-bottom:0.8rem;">All Submitted Complaints</div>', unsafe_allow_html=True)

    browse_complaints, browse_err = api_get_complaints()
    if browse_err:
        st.warning("Could not load complaints list.")
    elif not browse_complaints:
        st.markdown('<div class="empty-state"><div class="es-icon"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg></div>No complaints yet.</div>', unsafe_allow_html=True)
    else:
        # FIX 1 — use enumerate index + id for unique keys
        for idx, c in enumerate(browse_complaints):
            p    = safe_parse_response(c)
            clr  = confidence_color(p["conf_pct"])
            # FIX 9 — use normalized status for class
            norm = normalize_status(p["status"])
            scls = (
                "ctag-status-resolved" if norm == "Resolved"
                else "ctag-status-open" if norm in ("Submitted", "In Progress")
                else "ctag-status-default"
            )
            desc_preview = p["description"][:120] + ("…" if len(p["description"]) > 120 else "")
            safe_id      = p["id"] if p["id"] else f"unk_{idx}"
            cat_svg      = CAT_SVGS.get(p["category"], CAT_SVGS["Other"])

            st.markdown(f"""
            <div class="complaint-card">
                <div class="complaint-id">#{safe_id}</div>
                <div class="complaint-name">{p['student_name']}</div>
                <div class="complaint-desc">{desc_preview}</div>
                <div class="complaint-tags">
                    <span class="ctag ctag-cat">{cat_svg} {p['category']}</span>
                    <span class="ctag ctag-dept">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
                        {p['department']}
                    </span>
                    <span class="ctag {scls}">{STATUS_SVGS.get(norm,'')} {norm}</span>
                    <span class="ctag" style="color:{clr};border-color:{clr};background:rgba(0,0,0,0);">{p['conf_pct']}%</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 3 — ADMIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Admin Dashboard":
    st.markdown('<div class="page-title">Admin Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Review, triage, and resolve all campus complaints.</div>', unsafe_allow_html=True)

    complaints, fetch_err = api_get_complaints()
    if fetch_err:
        st.error("Failed to load complaints")
        st.markdown(f'<div class="error-detail">{fetch_err}</div>', unsafe_allow_html=True)
        st.stop()

    parsed_all = [safe_parse_response(c) for c in complaints]

    total     = len(parsed_all)
    submitted = sum(1 for p in parsed_all if p["status"] == "Submitted")
    in_prog   = sum(1 for p in parsed_all if p["status"] == "In Progress")
    resolved  = sum(1 for p in parsed_all if p["status"] == "Resolved")

    mc1, mc2, mc3, mc4 = st.columns(4)
    for col, num, label, clr in [
        (mc1, total,     "Total",       "#a78bfa"),
        (mc2, submitted, "Submitted",   "#818cf8"),
        (mc3, in_prog,   "In Progress", "#fbbf24"),
        (mc4, resolved,  "Resolved",    "#34d399"),
    ]:
        with col:
            st.markdown(f'<div class="metric-card"><div class="metric-num" style="color:{clr};">{num}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Filters — FIX 1: unique keys
    fc1, fc2 = st.columns(2)
    with fc1:
        f_status = st.selectbox(
            "Filter by Status",
            ["All"] + VALID_STATUSES,
            key="admin_filter_status",
        )
    with fc2:
        f_cat = st.selectbox(
            "Filter by Category",
            ["All"] + list(CATEGORIES.keys()),
            key="admin_filter_cat",
        )

    # FIX 9 — filter uses normalized status
    filtered = [
        p for p in parsed_all
        if (f_status == "All" or p["status"] == f_status)
        and (f_cat == "All" or p["category"] == f_cat)
    ]

    st.markdown(f'<div style="font-size:0.78rem;color:#6b7280;margin-bottom:0.8rem;">{len(filtered)} complaint(s) shown</div>', unsafe_allow_html=True)

    if not filtered:
        st.markdown('<div class="empty-state"><div class="es-icon"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div>No complaints match the filter.</div>', unsafe_allow_html=True)

    # FIX 1 — globally unique keys using idx + safe_id
    for idx, p in enumerate(filtered):
        cat_svg  = CAT_SVGS.get(p["category"], CAT_SVGS["Other"])
        clr      = confidence_color(p["conf_pct"])
        # FIX 10 — safe_id never None
        safe_id  = p["id"] if p["id"] else f"unk_{idx}"
        key_base = safe_key("admin", idx, safe_id)

        expander_label = f"#{safe_id}  —  {p['description'][:65]}{'…' if len(p['description'])>65 else ''}"

        with st.expander(expander_label):
            rc1, rc2, rc3 = st.columns(3)
            with rc1:
                st.markdown(f'<div style="font-size:0.78rem;"><div style="color:#6b7280;">Category</div><div style="color:#a78bfa;font-weight:600;display:flex;align-items:center;gap:5px;">{cat_svg} {p["category"]}</div></div>', unsafe_allow_html=True)
            with rc2:
                st.markdown(f'<div style="font-size:0.78rem;"><div style="color:#6b7280;">Department</div><div style="color:#34d399;font-weight:600;">{p["department"]}</div></div>', unsafe_allow_html=True)
            with rc3:
                st.markdown(f'<div style="font-size:0.78rem;"><div style="color:#6b7280;">AI Confidence</div><div style="color:{clr};font-weight:600;">{p["conf_pct"]}%</div><div class="conf-bar-bg"><div class="conf-bar-fill" style="width:{p["conf_pct"]}%;background:{clr};"></div></div></div>', unsafe_allow_html=True)

            st.markdown(f"""
            <div class="desc-block">{p['description']}</div>
            <div style="font-size:0.72rem;color:#6b7280;display:flex;align-items:center;gap:5px;">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                {p['student_name']}
            </div>
            """, unsafe_allow_html=True)

            # FIX 1 — unique keys for every widget in loop
            cur_idx = VALID_STATUSES.index(p["status"]) if p["status"] in VALID_STATUSES else 0
            new_status = st.selectbox(
                "Update Status",
                VALID_STATUSES,
                index=cur_idx,
                key=f"sel_status_{key_base}",
            )
            new_resolution = st.text_area(
                "Resolution / Response note",
                value=p["resolution"],
                placeholder="Write a response or resolution for the student…",
                key=f"txt_res_{key_base}",
                height=80,
            )

            if st.button("Save Update", key=f"btn_save_{key_base}"):
                ok, upd_err = api_update_status(safe_id, new_status, new_resolution)
                if ok:
                    st.success("Updated successfully!")
                    st.rerun()
                else:
                    st.error("Update failed")
                    if upd_err:
                        st.markdown(f'<div class="error-detail">{upd_err}</div>', unsafe_allow_html=True)