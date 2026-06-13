"""
Block-By-Block — NYC Environmental Intelligence
================================================
A hyper-local environmental dashboard for New York City. Enter an address,
click the map, or pick a borough to get a modeled block-level profile of tree
canopy, heat exposure, air quality, recycling, and transit — distilled into a
single Eco Score with an actionable improvement plan.

Data note: borough baselines are seeded from NYC Open Data, the Heat
Vulnerability Index, and EPA air-quality references. Block-level figures are
*modeled estimates* — deterministic micro-variations derived from the block's
coordinates so that each block reads distinctly while staying anchored to its
borough's real-world averages. Clearly labeled as estimates throughout.
"""

import hashlib
import io
import json
from datetime import datetime

import folium
import plotly.graph_objects as go
import streamlit as st
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)
from streamlit_folium import st_folium

import eco_data
import eco_community

# ============================================================================
# PAGE CONFIG + PWA
# ============================================================================
st.set_page_config(
    page_title="Block-By-Block · NYC Environmental Intelligence",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject PWA manifest + icons (best-effort; ignored locally)
try:
    with open(".streamlit/static/manifest.json", "r") as f:
        _manifest = f.read().replace(chr(34), "%22")
    st.markdown(
        f'<link rel="manifest" href="data:application/manifest+json,{_manifest}">',
        unsafe_allow_html=True,
    )
except OSError:
    pass

st.markdown(
    """
    <link rel="apple-touch-icon" href="https://nyc-eco-checker.streamlit.app/static/icon-192.png">
    <link rel="icon" type="image/png" sizes="192x192" href="https://nyc-eco-checker.streamlit.app/static/icon-192.png">
    <meta name="theme-color" content="#7c9c82">
    <meta name="apple-mobile-web-app-capable" content="yes">
    """,
    unsafe_allow_html=True,
)

# ============================================================================
# DESIGN SYSTEM (CSS)
# ============================================================================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');

:root{
  /* ---- core palette: sage · charcoal · periwinkle · lipstick ---- */
  --sage:#7c9c82; --sage-deep:#5e7e66; --sage-dark:#415848; --sage-tint:#eef3ef;
  --charcoal:#2b2f33; --charcoal-soft:#3b4147;
  --periwinkle:#8a93d6; --periwinkle-soft:#aeb6e8; --periwinkle-tint:#eef0fb;
  --lipstick:#e23b54; --lipstick-tint:#fdecef;
  /* ---- legacy aliases (old markup still resolves) ---- */
  --green-900:#2b3a30; --green-700:var(--sage-deep); --green-500:var(--sage); --green-400:#9bb6a0;
  /* ---- neutrals + status ---- */
  --bg:#f4f6f4; --card:#ffffff; --ink:#2b2f33; --muted:#697079; --line:rgba(43,47,51,.10);
  --good:var(--sage-deep); --moderate:#d99a2b; --poor:#e07a4a; --critical:var(--lipstick);
  --radius:20px; --shadow:0 12px 34px rgba(43,47,51,.10); --shadow-sm:0 4px 14px rgba(43,47,51,.07);
}

html, body, [class*="css"], .stApp, [data-testid="stMarkdownContainer"]{ font-family:'Inter',system-ui,sans-serif; }
.stApp{
  background:
    radial-gradient(1100px 520px at 6% -8%, #e6ede7 0%, transparent 58%),
    radial-gradient(900px 480px at 108% -4%, #ecedf7 0%, transparent 52%),
    var(--bg);
}
#MainMenu, footer{ visibility:hidden; }
header[data-testid="stHeader"]{ background:transparent; }
.block-container{ padding-top:2.2rem; padding-bottom:2rem; max-width:1180px; }

/* ---------- HERO ---------- */
.hero{
  background:linear-gradient(135deg, var(--charcoal) 0%, var(--sage-dark) 60%, var(--sage-deep) 120%);
  border-radius:26px; padding:2.4rem 2.6rem; color:#f2f6f2; position:relative; overflow:hidden;
  box-shadow:0 22px 50px rgba(43,47,51,.30); margin-bottom:1.6rem;
}
.hero::after{
  content:""; position:absolute; inset:0;
  background:
    radial-gradient(440px 240px at 88% -10%, rgba(174,182,232,.22), transparent 62%),
    radial-gradient(300px 180px at -6% 120%, rgba(255,255,255,.10), transparent 60%);
  pointer-events:none;
}
.hero-eyebrow{ font-size:.78rem; letter-spacing:.22em; text-transform:uppercase; color:var(--periwinkle-soft); font-weight:700; }
.hero-title{ font-family:'Plus Jakarta Sans',sans-serif; font-size:3.1rem; font-weight:800; line-height:1.04; margin:.35rem 0 .5rem; letter-spacing:-.02em; }
.hero-sub{ font-size:1.06rem; color:#dde6df; max-width:42rem; line-height:1.5; }
.hero-pills{ margin-top:1.2rem; display:flex; gap:.5rem; flex-wrap:wrap; }
.hero-pill{ background:rgba(255,255,255,.13); border:1px solid rgba(255,255,255,.22); color:#f2f6f2; padding:.32rem .8rem; border-radius:999px; font-size:.8rem; font-weight:600; backdrop-filter:blur(4px); }

/* ---------- SECTION TITLES ---------- */
.section-title{ font-family:'Plus Jakarta Sans',sans-serif; font-size:1.3rem; font-weight:700; color:var(--ink); margin:.4rem 0 .2rem; display:flex; align-items:center; gap:.55rem; }
.section-cap{ color:var(--muted); font-size:.92rem; margin-bottom:.6rem; }

/* ---------- METRIC CARDS ---------- */
.metric-card{
  background:var(--card); border:1px solid var(--line); border-radius:var(--radius);
  padding:1.15rem 1.25rem; box-shadow:var(--shadow-sm); position:relative; overflow:hidden;
  transition:transform .18s ease, box-shadow .18s ease; height:100%;
}
.metric-card:hover{ transform:translateY(-4px); box-shadow:var(--shadow); }
.metric-card::before{ content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background:var(--accent,#7c9c82); }
.metric-top{ display:flex; align-items:center; justify-content:space-between; }
.metric-icon{ font-size:1.4rem; line-height:1; }
.metric-chip{ font-size:.7rem; font-weight:700; padding:.2rem .5rem; border-radius:999px; background:color-mix(in srgb, var(--accent) 14%, white); color:var(--accent); }
.metric-label{ color:var(--muted); font-size:.82rem; font-weight:600; margin-top:.65rem; text-transform:uppercase; letter-spacing:.04em; }
.metric-value{ font-family:'Plus Jakarta Sans',sans-serif; font-size:1.85rem; font-weight:800; color:var(--ink); line-height:1.1; margin-top:.1rem; }
.metric-sub{ color:var(--muted); font-size:.82rem; margin-top:.15rem; }

/* ---------- SCORE / BADGE ---------- */
.scorecard{ background:var(--card); border:1px solid var(--line); border-radius:var(--radius); padding:1.1rem 1.3rem; box-shadow:var(--shadow-sm); height:100%; }
.grade-badge{ display:inline-flex; align-items:center; justify-content:center; width:64px; height:64px; border-radius:18px; font-family:'Plus Jakarta Sans',sans-serif; font-size:2rem; font-weight:800; color:white; box-shadow:0 8px 18px rgba(0,0,0,.14); }
.pill{ display:inline-block; padding:.28rem .7rem; border-radius:999px; font-size:.78rem; font-weight:700; }

/* ---------- CALLOUTS ---------- */
.callout{ border-radius:16px; padding:1rem 1.15rem; border:1px solid var(--line); box-shadow:var(--shadow-sm); margin:.4rem 0; }
.callout-good{ background:linear-gradient(135deg,var(--sage-tint),#ffffff); border-left:5px solid var(--good); }
.callout-warn{ background:linear-gradient(135deg,#fff6ec,#ffffff); border-left:5px solid var(--poor); }
.callout-crit{ background:linear-gradient(135deg,var(--lipstick-tint),#ffffff); border-left:5px solid var(--critical); }
.callout-info{ background:linear-gradient(135deg,var(--periwinkle-tint),#ffffff); border-left:5px solid var(--periwinkle); }

/* ---------- ACTION ITEMS ---------- */
.action{ display:flex; gap:.8rem; align-items:flex-start; background:var(--card); border:1px solid var(--line); border-radius:14px; padding:.85rem 1rem; margin:.45rem 0; box-shadow:var(--shadow-sm); }
.action-pri{ font-size:.68rem; font-weight:800; letter-spacing:.05em; padding:.25rem .5rem; border-radius:8px; white-space:nowrap; }
.action-body b{ color:var(--ink); }
.action-body span{ color:var(--muted); font-size:.88rem; }

/* ---------- LEADERBOARD ---------- */
.lb-row{ display:flex; align-items:center; gap:.8rem; padding:.6rem .85rem; border-radius:12px; margin:.3rem 0; background:var(--card); border:1px solid var(--line); }
.lb-you{ background:linear-gradient(135deg,var(--sage-tint),#ffffff); border:1px solid var(--sage); box-shadow:var(--shadow-sm); }
.lb-rank{ font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; width:1.6rem; color:var(--muted); }
.lb-name{ font-weight:600; color:var(--ink); flex:1; }
.lb-val{ font-weight:700; color:var(--green-700); }

/* ---------- SIDEBAR ---------- */
section[data-testid="stSidebar"]{ background:linear-gradient(180deg,#ffffff,#eef1ee); border-right:1px solid var(--line); }
section[data-testid="stSidebar"] .stRadio label{ font-weight:500; }
.side-brand{ font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; font-size:1.25rem; color:var(--green-700); }
.side-tag{ color:var(--muted); font-size:.85rem; margin-bottom:.4rem; }

/* ---------- TABS ---------- */
.stTabs [data-baseweb="tab-list"]{ gap:.3rem; }
.stTabs [data-baseweb="tab"]{ font-weight:600; border-radius:12px 12px 0 0; padding:.4rem 1rem; }

/* ---------- DATA PROVENANCE BADGES ---------- */
.src-badge{ font-size:.62rem; font-weight:800; letter-spacing:.04em; padding:.16rem .42rem; border-radius:999px; vertical-align:middle; }
.src-live{ background:var(--sage-tint); color:var(--sage-deep); }
.src-modeled{ background:#f0f0f2; color:#8a8f97; }

/* ---------- AI / FORECAST ---------- */
.ai-chip{ display:inline-block; background:var(--periwinkle-tint); color:#4a52a8; font-size:.7rem; font-weight:800; letter-spacing:.04em; padding:.22rem .6rem; border-radius:999px; border:1px solid var(--periwinkle-soft); }
.amp-row{ display:flex; justify-content:space-between; padding:.5rem .85rem; border-radius:10px; background:var(--card); border:1px solid var(--line); margin:.3rem 0; font-size:.9rem; }
.amp-row b{ color:var(--charcoal); }
.hour-pill{ display:inline-block; background:var(--lipstick-tint); color:var(--lipstick); font-weight:700; font-size:.78rem; padding:.28rem .6rem; border-radius:10px; margin:.15rem; }

/* ---------- ACHIEVEMENTS / GAMIFICATION ---------- */
.ach{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:.85rem 1rem; box-shadow:var(--shadow-sm); height:100%; }
.ach-locked{ opacity:.55; filter:grayscale(.4); }
.ach-top{ display:flex; align-items:center; gap:.55rem; }
.ach-badge{ width:38px; height:38px; border-radius:11px; display:inline-flex; align-items:center; justify-content:center; font-size:1.2rem; background:var(--sage-tint); }
.ach-badge.locked{ background:#eef0f2; }
.ach-title{ font-weight:700; color:var(--charcoal); font-size:.95rem; }
.ach-sub{ color:var(--muted); font-size:.8rem; margin-top:.15rem; }
.ach-pri{ font-size:.6rem; font-weight:800; color:var(--lipstick); background:var(--lipstick-tint); padding:.14rem .42rem; border-radius:999px; margin-left:auto; }
.bar{ height:8px; border-radius:999px; background:#eceeec; overflow:hidden; margin-top:.6rem; }
.bar-fill{ height:100%; border-radius:999px; background:linear-gradient(90deg,var(--sage),var(--sage-deep)); }
.points-card{ background:linear-gradient(135deg,var(--periwinkle-tint),#ffffff); border:1px solid var(--periwinkle-soft); border-radius:var(--radius); padding:1.1rem 1.3rem; box-shadow:var(--shadow-sm); }
.points-num{ font-family:'Plus Jakarta Sans',sans-serif; font-size:2.2rem; font-weight:800; color:#4a52a8; line-height:1; }

/* ---------- FOOTER ---------- */
.app-footer{ text-align:center; color:var(--muted); font-size:.82rem; padding:1.6rem 0 .4rem; border-top:1px solid var(--line); margin-top:2rem; }
.app-footer b{ color:var(--sage-deep); }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================================
# DATA MODEL
# ============================================================================
NYC_BOUNDS = {"lat_min": 40.4774, "lat_max": 40.9176, "lon_min": -74.2591, "lon_max": -73.7004}

BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]

# Borough baselines anchored to NYC Open Data / Heat Vulnerability Index / EPA refs.
BOROUGH_DATA = {
    "Manhattan":     {"center": (40.7831, -73.9712), "heat": 3.8, "recycle": 23, "transit": 85, "trees_per_sqkm": 350, "air_quality": 62, "color": "#7c9c82"},
    "Brooklyn":      {"center": (40.6782, -73.9442), "heat": 3.2, "recycle": 19, "transit": 70, "trees_per_sqkm": 420, "air_quality": 58, "color": "#8a93d6"},
    "Queens":        {"center": (40.7282, -73.7949), "heat": 3.0, "recycle": 21, "transit": 60, "trees_per_sqkm": 380, "air_quality": 55, "color": "#d99a2b"},
    "Bronx":         {"center": (40.8448, -73.8648), "heat": 4.1, "recycle": 17, "transit": 55, "trees_per_sqkm": 310, "air_quality": 65, "color": "#e23b54"},
    "Staten Island": {"center": (40.5795, -74.1502), "heat": 2.5, "recycle": 24, "transit": 45, "trees_per_sqkm": 450, "air_quality": 48, "color": "#5e7e66"},
}

BOROUGH_QUICK = {
    "Manhattan — Times Square":   (40.7580, -73.9855),
    "Brooklyn — Downtown":        (40.6905, -73.9847),
    "Queens — Flushing":          (40.7282, -73.7949),
    "Bronx — Yankee Stadium":     (40.8296, -73.9261),
    "Staten Island — St. George": (40.6429, -74.0743),
}

# Composite Eco Score weights (each dimension normalized 0–100, higher = greener)
ECO_WEIGHTS = {"tree_equity": 0.30, "air": 0.20, "heat": 0.20, "recycle": 0.15, "transit": 0.15}


# ============================================================================
# GEO + BLOCK LOGIC
# ============================================================================
def is_in_nyc(lat, lon):
    b = NYC_BOUNDS
    if not (b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]):
        return False
    if lat < 40.7 and lon < -74.15:   # carve out NJ to the SW
        return False
    if lat < 40.7 and lon > -73.7:    # carve out Long Island to the SE
        return False
    return True


def get_borough_from_coords(lat, lon):
    if not is_in_nyc(lat, lon):
        return None
    if lat < 40.7:
        return "Staten Island" if lon < -74.05 else "Brooklyn"
    if lat > 40.85:
        return "Bronx"
    if lon > -73.9:
        return "Queens"
    return "Manhattan"


def borough_from_zip(zcode):
    """Refine borough from a NYC ZIP — far more reliable than coarse lat/lon thresholds."""
    if not zcode or len(str(zcode)) < 3:
        return None
    p = str(zcode)[:3]
    if p == "104":
        return "Bronx"
    if p == "103":
        return "Staten Island"
    if p == "112":
        return "Brooklyn"
    if p in {"110", "111", "113", "114", "116"}:
        return "Queens"
    if p in {"100", "101", "102"}:
        return "Manhattan"
    return None


def _frac(seed, salt):
    """Deterministic fraction in [0,1) from a stable hash."""
    h = hashlib.sha256(f"{seed}|{salt}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def block_profile(lat, lon, borough):
    """Modeled block-level metrics: borough baseline + deterministic micro-variation.

    Coordinates are rounded to ~3 decimals (≈110 m, roughly a block) so the same
    block always returns the same numbers, while neighboring blocks differ
    realistically. Values stay clamped to plausible NYC ranges.
    """
    base = BOROUGH_DATA[borough]
    seed = f"{round(lat, 3)},{round(lon, 3)}"

    def vary(salt, spread, lo, hi, base_val):
        return max(lo, min(hi, base_val + (_frac(seed, salt) * 2 - 1) * spread))

    trees = round(vary("trees", 95, 80, 620, base["trees_per_sqkm"]))
    heat = round(vary("heat", 0.7, 1.5, 5.0, base["heat"]), 1)
    recycle = round(vary("recycle", 6, 8, 38, base["recycle"]))
    transit = round(vary("transit", 16, 25, 99, base["transit"]))
    aqi = round(vary("aqi", 9, 28, 92, base["air_quality"]))
    return {
        "borough": borough,
        "trees": trees,
        "heat": heat,
        "recycle": recycle,
        "transit": transit,
        "aqi": aqi,
        "target_trees": base["trees_per_sqkm"],
        "color": base["color"],
    }


@st.cache_data(show_spinner=False, ttl=3600)
def geocode_address(address):
    """Return (lat, lon, label) or None. NYC GeoSearch first (authoritative), Nominatim fallback."""
    hit = eco_data.geosearch_address(address)
    if hit:
        return hit
    try:
        geocoder = Nominatim(user_agent="block-by-block-nyc", timeout=10)
        loc = geocoder.geocode(f"{address}, New York City, NY", timeout=10)
        if loc:
            return (loc.latitude, loc.longitude, loc.address)
    except (GeocoderTimedOut, GeocoderServiceError, Exception):
        return None
    return None


@st.cache_data(show_spinner=False, ttl=3600)
def reverse_geocode(lat, lon):
    try:
        geocoder = Nominatim(user_agent="block-by-block-nyc", timeout=10)
        loc = geocoder.reverse(f"{lat}, {lon}", timeout=10)
        if loc:
            return loc.address
    except (GeocoderTimedOut, GeocoderServiceError, Exception):
        pass
    return f"{lat:.4f}, {lon:.4f}"


# ============================================================================
# SCORING
# ============================================================================
def tree_equity(prof):
    score = min(100, (prof["trees"] / prof["target_trees"]) * 100)
    missing = max(0, prof["target_trees"] - prof["trees"])
    rating = ("Excellent" if score >= 80 else "Good" if score >= 60 else
              "Fair" if score >= 40 else "Poor" if score >= 20 else "Critical")
    return score, missing, rating


def air_status(aqi):
    return "Good" if aqi <= 50 else "Moderate" if aqi <= 100 else "Unhealthy"


def eco_score(prof):
    """Composite 0–100 Eco Score (higher = greener), normalized per dimension."""
    equity, _, _ = tree_equity(prof)
    dims = {
        "tree_equity": equity,
        "air": max(0, 100 - prof["aqi"]),          # lower AQI is better
        "heat": (5 - prof["heat"]) / 5 * 100,       # lower heat is better
        "recycle": min(100, prof["recycle"] / 35 * 100),
        "transit": prof["transit"],
    }
    total = sum(dims[k] * w for k, w in ECO_WEIGHTS.items())
    return round(total), dims


def grade_for(score):
    if score >= 85:
        return "A", "#5e7e66"
    if score >= 70:
        return "B", "#7c9c82"
    if score >= 55:
        return "C", "#d99a2b"
    if score >= 40:
        return "D", "#e07a4a"
    return "F", "#e23b54"


def property_impact(trees):
    premium = min(20, trees / 20)              # % home-value premium from canopy
    added = 500000 * (premium / 100)
    cooling = trees * 12                        # $/yr cooling savings
    return added, cooling, premium


def heat_alert(heat):
    temp = 85 + (heat - 2.5) * 5
    if heat >= 3.8:
        return True, temp, ["Public library (0.2 mi)", "Community center (0.4 mi)", "Senior center (0.6 mi)"]
    return False, temp, []


def seasonal_recs():
    m = datetime.now().month
    table = {
        "Spring": (["Apply for free street-tree planting (deadline Apr 30)",
                    "Join a community tree-pruning workshop",
                    "Install rain barrels for summer watering"], [3, 4, 5]),
        "Summer": (["Water young street trees during heat waves",
                    "Request a cool-pavement pilot for your block",
                    "Mulch tree pits to retain moisture"], [6, 7, 8]),
        "Fall":   (["Sign up for curbside compost pickup",
                    "Plant shade trees before the ground freezes",
                    "Apply for next year's tree-planting grants"], [9, 10, 11]),
        "Winter": (["Advocate for cleared, protected bike lanes",
                    "Plan your block's spring planting strategy",
                    "Seal drafts to cut heating emissions"], [12, 1, 2]),
    }
    for season, (recs, months) in table.items():
        if m in months:
            return season, recs
    return "Spring", table["Spring"][0]


def action_plan(prof, equity_score, missing):
    actions = []
    if prof["trees"] < 200 or missing > 60:
        actions.append(("Plant {} street trees on your block".format(min(20, int(missing))),
                        "Cuts summer heat and lifts property value", "HIGH"))
    if prof["heat"] >= 3.5:
        actions.append(("Install cool pavement or a green roof",
                        "Lowers surface temperature by up to 30°F", "HIGH"))
    if equity_score < 50:
        actions.append(("Join a neighborhood tree-equity campaign",
                        "Addresses canopy disparities across blocks", "HIGH"))
    if prof["recycle"] < 21:
        actions.append(("Start a block composting program",
                        "Diverts waste and builds community", "MEDIUM"))
    if prof["transit"] < 70:
        actions.append(("Advocate for protected bike lanes",
                        "Reduces emissions and improves safety", "MEDIUM"))
    if prof["aqi"] > 60:
        actions.append(("Add a green buffer along high-traffic edges",
                        "Filters particulates near the curb", "MEDIUM"))
    if not actions:
        actions.append(("Your block is thriving — share what works",
                        "Mentor a neighboring block's greening effort", "LOW"))
    return actions


# ============================================================================
# PLOTLY CHARTS
# ============================================================================
PLOT_FONT = dict(family="Inter, sans-serif", color="#2b2f33")


def gauge_chart(score, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"size": 46, "family": "Plus Jakarta Sans", "color": "#2b2f33"}, "suffix": ""},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#c5d2cc"},
            "bar": {"color": color, "thickness": 0.28},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 40], "color": "#fbe0e4"},
                {"range": [40, 55], "color": "#f7e6cf"},
                {"range": [55, 70], "color": "#eef0c9"},
                {"range": [70, 85], "color": "#e7efe7"},
                {"range": [85, 100], "color": "#dbe7dc"},
            ],
            "threshold": {"line": {"color": color, "width": 4}, "thickness": 0.8, "value": score},
        },
    ))
    fig.update_layout(height=230, margin=dict(l=18, r=18, t=12, b=4),
                      paper_bgcolor="rgba(0,0,0,0)", font=PLOT_FONT)
    return fig


def radar_chart(dims, color):
    labels = ["Tree Equity", "Air Quality", "Heat Comfort", "Recycling", "Transit"]
    vals = [dims["tree_equity"], dims["air"], dims["heat"], dims["recycle"], dims["transit"]]
    vals = [round(v) for v in vals]
    fig = go.Figure(go.Scatterpolar(
        r=vals + [vals[0]], theta=labels + [labels[0]],
        fill="toself", fillcolor="rgba(31,158,110,.18)",
        line=dict(color=color, width=2.5), marker=dict(size=6, color=color),
        hovertemplate="%{theta}: %{r}/100<extra></extra>",
    ))
    fig.update_layout(
        height=320, margin=dict(l=40, r=40, t=30, b=20),
        paper_bgcolor="rgba(0,0,0,0)", font=PLOT_FONT,
        polar=dict(
            bgcolor="rgba(255,255,255,.45)",
            radialaxis=dict(range=[0, 100], showticklabels=True, tickfont=dict(size=9, color="#8a978f"),
                            gridcolor="#dce6e0", angle=90),
            angularaxis=dict(tickfont=dict(size=11, color="#3a4a44"), gridcolor="#dce6e0"),
        ),
    )
    return fig


def compare_bars(prof_dims, boro_dims, names):
    labels = ["Tree Equity", "Air Quality", "Heat Comfort", "Recycling", "Transit"]
    keys = ["tree_equity", "air", "heat", "recycle", "transit"]
    fig = go.Figure()
    fig.add_bar(name=names[0], x=labels, y=[round(prof_dims[k]) for k in keys],
                marker_color="#7c9c82", marker_line_width=0)
    fig.add_bar(name=names[1], x=labels, y=[round(boro_dims[k]) for k in keys],
                marker_color="#aebfb1", marker_line_width=0)
    fig.update_layout(
        height=330, barmode="group", margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=PLOT_FONT,
        legend=dict(orientation="h", y=1.14, x=0), yaxis=dict(range=[0, 100], gridcolor="#e3ece7"),
    )
    return fig


# ============================================================================
# PDF REPORT
# ============================================================================
def build_pdf(label, prof, score, grade, equity_score, rating, added, cooling, actions):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.7 * inch,
                            bottomMargin=0.7 * inch, leftMargin=0.7 * inch, rightMargin=0.7 * inch)
    styles = getSampleStyleSheet()
    green = colors.HexColor("#415848")
    title = ParagraphStyle("t", parent=styles["Title"], textColor=green, fontSize=22, spaceAfter=2)
    sub = ParagraphStyle("s", parent=styles["Normal"], textColor=colors.HexColor("#5d6e68"), fontSize=9, spaceAfter=14)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=green, fontSize=13, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("b", parent=styles["Normal"], fontSize=10, leading=15)

    story = [
        Paragraph("Block-By-Block", title),
        Paragraph("NYC Environmental Intelligence Report", sub),
        Paragraph(f"<b>Location:</b> {label[:90]}", body),
        Paragraph(f"<b>Borough:</b> {prof['borough']} &nbsp;&nbsp; "
                  f"<b>Generated:</b> {datetime.now():%B %d, %Y}", body),
        Spacer(1, 10),
    ]

    score_tbl = Table([["Eco Score", "Grade", "Tree Equity", "Air Quality Index"],
                       [f"{score}/100", grade, f"{equity_score:.0f}/100 ({rating})",
                        f"{prof['aqi']} ({air_status(prof['aqi'])})"]],
                      colWidths=[1.7 * inch] * 4)
    score_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), green),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#eef6f1")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfe0d8")),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(score_tbl)

    story.append(Paragraph("Block Metrics", h2))
    metrics = [["Metric", "Value"],
               ["Tree canopy (trees / sq km)", str(prof["trees"])],
               ["Heat exposure (0–5, lower better)", f"{prof['heat']}/5.0"],
               ["Recycling rate", f"{prof['recycle']}%"],
               ["Transit access (0–100)", f"{prof['transit']}/100"],
               ["Est. added home value", f"+${added:,.0f}"],
               ["Est. annual cooling savings", f"${cooling:,.0f}"]]
    mt = Table(metrics, colWidths=[3.6 * inch, 3.2 * inch])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c9c82")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f7f3")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dce6e0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(mt)

    story.append(Paragraph("Recommended Actions", h2))
    for i, (act, impact, pri) in enumerate(actions, 1):
        story.append(Paragraph(f"<b>{i}. [{pri}] {act}</b><br/>{impact}", body))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "<i>Tree canopy (NYC Street Tree Census), heat vulnerability (NYC HVI) and the "
        "48-hour heat forecast (Open-Meteo) are live where available. Air quality, recycling "
        "and transit are modeled from borough baselines (NYC Open Data, EPA) with "
        "coordinate-seeded micro-variation. Use as directional guidance, not survey-grade "
        "measurement.</i>",
        ParagraphStyle("note", parent=styles["Normal"], fontSize=8,
                       textColor=colors.HexColor("#8a978f"), leading=11)))

    doc.build(story)
    buf.seek(0)
    return buf


# ============================================================================
# SMALL HTML HELPERS
# ============================================================================
def src_badge(live):
    return (f'<span class="src-badge src-{"live" if live else "modeled"}">'
            f'{"● LIVE" if live else "○ MODELED"}</span>')


def metric_card(icon, label, value, sub, accent, chip=None, live=None):
    chip_html = f'<span class="metric-chip">{chip}</span>' if chip else ""
    badge = "" if live is None else f' {src_badge(live)}'
    st.markdown(
        f"""
        <div class="metric-card" style="--accent:{accent}">
          <div class="metric-top"><span class="metric-icon">{icon}</span>{chip_html}</div>
          <div class="metric-label">{label}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-sub">{sub}{badge}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def section(title, caption=""):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="section-cap">{caption}</div>', unsafe_allow_html=True)


# ============================================================================
# SESSION STATE
# ============================================================================
st.session_state.setdefault("lat", None)
st.session_state.setdefault("lon", None)
st.session_state.setdefault("method", None)
st.session_state.setdefault("session_reports", [])  # community reports logged this session
st.session_state.setdefault("submit_count", 0)      # light per-session anti-abuse


def _eco_helper(la, lo, b):
    """For leaderboard scoring: (modeled trees, eco score) for any block — cheap, no network."""
    p = block_profile(la, lo, b)
    return p["trees"], eco_score(p)[0]

# ============================================================================
# SIDEBAR — LOCATION
# ============================================================================
with st.sidebar:
    st.markdown('<div class="side-brand">🌿 Block-By-Block</div>', unsafe_allow_html=True)
    st.markdown('<div class="side-tag">Hyper-local environmental intelligence for NYC</div>',
                unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("#### 📍 Choose a location")
    method = st.radio("Input method", ["✏️ Type an address", "🖱️ Click the map", "🏙️ Pick a borough"],
                      label_visibility="collapsed")

    if method == "✏️ Type an address":
        address = st.text_input("NYC address or landmark",
                                placeholder="e.g., Times Square or Prospect Park")
        if address:
            with st.spinner("Locating…"):
                res = geocode_address(address)
            if res:
                st.session_state.lat, st.session_state.lon = res[0], res[1]
                st.session_state.method = "address"
                st.success(f"📍 {res[2][:48]}…")
            else:
                st.error("Couldn't find that address. Try a nearby landmark.")

    elif method == "🖱️ Click the map":
        st.caption("Click anywhere on the map to drop a pin.")
        c = st.session_state.lat or 40.7549, st.session_state.lon or -73.9840
        mini = folium.Map(location=[c[0], c[1]], zoom_start=12, tiles="CartoDB positron")
        if st.session_state.lat:
            folium.Marker([st.session_state.lat, st.session_state.lon],
                          icon=folium.Icon(color="green", icon="leaf", prefix="fa")).add_to(mini)
        clicked = st_folium(mini, width=290, height=300, key="picker")
        if clicked and clicked.get("last_clicked"):
            st.session_state.lat = clicked["last_clicked"]["lat"]
            st.session_state.lon = clicked["last_clicked"]["lng"]
            st.session_state.method = "click"
            st.rerun()

    elif method == "🏙️ Pick a borough":
        choice = st.selectbox("Borough & landmark", list(BOROUGH_QUICK.keys()))
        if st.button("📍 Analyze this area", width="stretch"):
            st.session_state.lat, st.session_state.lon = BOROUGH_QUICK[choice]
            st.session_state.method = "borough"
            st.rerun()

    st.markdown("---")
    st.caption("Data: NYC Open Data · Heat Vulnerability Index · EPA. "
               "Block figures are modeled estimates.")


# ============================================================================
# HERO
# ============================================================================
st.markdown(
    """
    <div class="hero">
      <div class="hero-eyebrow">NYC Environmental Intelligence</div>
      <div class="hero-title">Know your block.</div>
      <div class="hero-sub">Tree canopy, heat exposure, air quality, recycling, and transit —
      distilled into one Eco Score with a concrete plan to make your block greener.</div>
      <div class="hero-pills">
        <span class="hero-pill">🌳 Tree equity</span>
        <span class="hero-pill">🌡️ Heat risk</span>
        <span class="hero-pill">💨 Air quality</span>
        <span class="hero-pill">🚌 Transit access</span>
        <span class="hero-pill">📄 PDF report</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
# MAIN
# ============================================================================
if st.session_state.lat is None:
    # ---- Landing state ----
    section("👋 Get started in one click", "Pick how you want to locate a block in the sidebar.")
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("✏️", "Type an address", "Any landmark", "Times Square, Prospect Park…", "#7c9c82")
    with c2:
        metric_card("🖱️", "Click the map", "Drop a pin", "Anywhere in the five boroughs", "#8a93d6")
    with c3:
        metric_card("🏙️", "Pick a borough", "5 boroughs", "Jump to a known landmark", "#d99a2b")

    st.markdown("<br>", unsafe_allow_html=True)
    section("🗺️ Explore NYC", "A preview of the five boroughs — choose a method to begin.")
    preview = folium.Map(location=[40.7128, -73.9560], zoom_start=11, tiles="CartoDB positron")
    for name, d in BOROUGH_DATA.items():
        folium.CircleMarker(d["center"], radius=10, color=d["color"], fill=True,
                            fill_color=d["color"], fill_opacity=0.7,
                            popup=f"{name}").add_to(preview)
    st_folium(preview, width=1100, height=420, key="preview")

else:
    lat, lon = st.session_state.lat, st.session_state.lon

    if not is_in_nyc(lat, lon):
        st.markdown(
            f"""
            <div class="callout callout-warn">
              <b>🚫 Outside the NYC data area</b><br>
              <span style="color:var(--muted)">({lat:.4f}, {lon:.4f}) is outside the five boroughs.
              Block-By-Block covers Manhattan, Brooklyn, Queens, the Bronx, and Staten Island.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        oob = folium.Map(location=[lat, lon], zoom_start=11, tiles="CartoDB positron")
        folium.Marker([lat, lon], icon=folium.Icon(color="red", icon="times", prefix="fa")).add_to(oob)
        st_folium(oob, width=1100, height=380, key="oob")
        st.stop()

    borough = get_borough_from_coords(lat, lon)
    prof = block_profile(lat, lon, borough)
    label = reverse_geocode(lat, lon)

    # ---- Overlay real data (graceful fallback to modeled per-field) ----
    rd = eco_data.fetch_block_realdata(lat, lon, borough, prof)
    zb = borough_from_zip(rd.zip)     # ZIP is far more accurate than coarse lat/lon thresholds
    if zb and zb != borough:
        borough = zb
        prof = block_profile(lat, lon, borough)
    prof["trees"] = rd.trees          # live: NYC Street Tree Census
    prof["heat"] = rd.heat            # live: NYC Heat Vulnerability Index (HVI 1–5)
    prof["aqi"] = rd.aqi
    n_live = sum(1 for v in rd.sources.values() if v == "live")
    hf = eco_data.heat_forecast(rd.forecast, rd.hvi, prof["trees"])

    score, dims = eco_score(prof)
    grade, grade_color = grade_for(score)
    equity_score, missing, rating = tree_equity(prof)
    added, cooling, premium = property_impact(prof["trees"])
    _, temp, centers = heat_alert(prof["heat"])
    season, recs = seasonal_recs()
    actions = action_plan(prof, equity_score, missing)

    # ---- Location banner ----
    prov = (f'<span class="src-badge src-live">● {n_live} LIVE SOURCES</span>'
            if n_live else '<span class="src-badge src-modeled">○ MODELED ESTIMATE</span>')
    st.markdown(
        f"""
        <div class="callout callout-good">
          <b>📍 {label[:78]}</b> &nbsp; {prov}<br>
          <span style="color:var(--muted)">{borough}{' · ZIP ' + rd.zip if rd.zip else ''} · {lat:.4f}, {lon:.4f}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if hf["danger_score"] >= 40:
        peak_label = eco_data._fmt_hour(hf["peak_time"])
        st.markdown(
            f"""
            <div class="callout callout-crit">
              <b>🚨 {hf['danger_level']} heat risk · peak feels-like ~{hf['peak_adj_f']:.0f}°F ({peak_label})</b><br>
              <span style="color:var(--muted)">Forecaster flags {len(hf['dangerous_hours'])} dangerous hours in the next 48h ·
              cooling centers: {' · '.join(centers)} · see the Heat Forecast tab</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ---- Eco Score + gauge ----
    st.markdown("<br>", unsafe_allow_html=True)
    g1, g2 = st.columns([1, 1.25])
    with g1:
        section("🌿 Block Eco Score", "Weighted blend of all five environmental dimensions.")
        st.markdown(
            f"""
            <div class="scorecard" style="display:flex; gap:1.1rem; align-items:center;">
              <div class="grade-badge" style="background:{grade_color}">{grade}</div>
              <div>
                <div style="font-family:'Plus Jakarta Sans'; font-size:2.4rem; font-weight:800; color:var(--ink); line-height:1">{score}<span style="font-size:1.1rem; color:var(--muted)">/100</span></div>
                <div style="color:var(--muted); font-size:.9rem">{rating} tree equity · {air_status(prof['aqi'])} air</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with g2:
        st.plotly_chart(gauge_chart(score, grade_color), width="stretch",
                        config={"displayModeBar": False})

    # ---- Metric cards ----
    st.markdown("<br>", unsafe_allow_html=True)
    section("📊 Block metrics", "Live where available, otherwise modeled from borough averages.")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        metric_card("🌳", "Tree canopy", f"{prof['trees']}", "trees / sq km",
                    "#7c9c82", chip=rating, live=rd.trees_live)
    with m2:
        heat_color = "#e23b54" if prof["heat"] >= 3.8 else "#e07a4a" if prof["heat"] >= 3.3 else "#7c9c82"
        metric_card("🌡️", "Heat vulnerability", f"{prof['heat']:.0f}/5", "NYC HVI · lower is cooler",
                    heat_color, chip="High" if prof["heat"] >= 3.8 else "Moderate" if prof["heat"] >= 3.3 else "Low",
                    live=rd.hvi_live)
    with m3:
        aqi_c = "#7c9c82" if prof["aqi"] <= 50 else "#d99a2b" if prof["aqi"] <= 100 else "#e23b54"
        metric_card("💨", "Air quality", f"{prof['aqi']}", "AQI · lower is cleaner",
                    aqi_c, chip=air_status(prof["aqi"]), live=False)
    with m4:
        metric_card("🚌", "Transit access", f"{prof['transit']}/100", "walk to frequent transit",
                    "#8a93d6", chip="Strong" if prof["transit"] >= 70 else "Fair" if prof["transit"] >= 50 else "Limited")

    # ---- Tabs ----
    st.markdown("<br>", unsafe_allow_html=True)
    (t_overview, t_forecast, t_map, t_compare,
     t_actions, t_compete, t_community, t_report) = st.tabs(
        ["📈 Profile", "🌡️ Heat Forecast", "🗺️ Heat Map", "⚖️ Compare",
         "✅ Action Plan", "🏆 Compete", "🌳 Community", "📄 Report"]
    )

    # ----- PROFILE -----
    with t_overview:
        cc1, cc2 = st.columns([1.1, 1])
        with cc1:
            section("Environmental profile", "Each axis scored 0–100, higher is greener.")
            st.plotly_chart(radar_chart(dims, grade_color), width="stretch",
                            config={"displayModeBar": False})
        with cc2:
            section("Value impact", "What canopy and cooling are worth on this block.")
            v1, v2 = st.columns(2)
            with v1:
                metric_card("💰", "Added home value", f"+${added:,.0f}", f"{premium:.1f}% canopy premium", "#7c9c82")
            with v2:
                metric_card("❄️", "Cooling savings", f"${cooling:,.0f}", "per year, est.", "#8a93d6")
            st.markdown("<br>", unsafe_allow_html=True)
            r1, r2 = st.columns(2)
            with r1:
                metric_card("⚖️", "Tree equity", f"{equity_score:.0f}/100", rating, grade_color)
            with r2:
                metric_card("🌱", "Trees needed", f"{missing:.0f}", "to reach borough target", "#d99a2b")

    # ----- HEAT FORECAST (AI) -----
    with t_forecast:
        amp = hf["amp_breakdown"]
        live_tag = ("live NWS forecast" if hf and not hf["modeled"] else "modeled forecast")
        st.markdown(
            f'<div class="section-title">🌡️ 48-Hour Heat-Wave Forecaster '
            f'<span class="ai-chip">AI</span></div>'
            f'<div class="section-cap">Our model layers this block\'s heat-island risk on top of the '
            f'{live_tag}, predicting dangerous hours up to 48 h ahead.</div>',
            unsafe_allow_html=True,
        )
        f1, f2, f3 = st.columns(3)
        with f1:
            dlvl = hf["danger_level"]
            dcolor = ("#e23b54" if hf["danger_score"] >= 65 else "#e07a4a"
                      if hf["danger_score"] >= 40 else "#d99a2b" if hf["danger_score"] >= 20 else "#7c9c82")
            metric_card("🔥", "Block danger level", dlvl, f"{hf['danger_score']}/100 risk score", dcolor)
        with f2:
            metric_card("🌡️", "Peak feels-like", f"{hf['peak_adj_f']:.0f}°F",
                        f"on this block · {eco_data._fmt_hour(hf['peak_time'])}", "#8a93d6")
        with f3:
            metric_card("⏱️", "Dangerous hours", f"{len(hf['dangerous_hours'])}",
                        "feels-like ≥90°F in next 48h", "#e07a4a")

        st.markdown("<br>", unsafe_allow_html=True)
        st.plotly_chart(eco_data.forecast_chart(hf), width="stretch",
                        config={"displayModeBar": False})

        # Why this block runs hotter — the explainable amplifier breakdown
        section("🧠 Why your block runs hotter", "The model's hyper-local adjustment, fully explainable.")
        st.markdown(
            f"""
            <div class="amp-row"><span>🏙️ Urban heat-island (HVI {rd.hvi}/5)</span><b>{amp['hvi']:+.1f}°F</b></div>
            <div class="amp-row"><span>🌳 Low tree canopy ({prof['trees']} trees/sq km)</span><b>{amp['canopy']:+.1f}°F</b></div>
            <div class="amp-row" style="background:var(--periwinkle-tint); border-color:var(--periwinkle-soft)">
              <span><b>Total block adjustment vs. the city forecast</b></span><b>{amp['total']:+.1f}°F</b></div>
            """,
            unsafe_allow_html=True,
        )
        if hf["dangerous_hours"]:
            section("⚠️ Proactive alert windows", "Plan errands, hydration, and check-ins around these hours.")
            chips = "".join(
                f'<span class="hour-pill">{eco_data._fmt_hour(t)} · {a:.0f}°F</span>'
                for t, a, _ in hf["dangerous_hours"][:16])
            st.markdown(f"<div>{chips}</div>", unsafe_allow_html=True)
            st.caption("In a deployed system these windows trigger proactive push alerts to "
                       "heat-vulnerable residents who opt in. Multi-city support is on the roadmap.")
        else:
            st.markdown(
                '<div class="callout callout-good"><b>✅ No dangerous heat hours forecast</b><br>'
                '<span style="color:var(--muted)">Feels-like stays below the 90°F caution threshold for the next 48 hours.</span></div>',
                unsafe_allow_html=True,
            )

    # ----- HEAT MAP -----
    with t_map:
        section("Heat vulnerability map", "Green = cooler buffer · red = elevated heat risk.")
        m = folium.Map(location=[lat, lon], zoom_start=15, tiles="CartoDB positron")
        folium.Circle(radius=520, location=[lat, lon], color="#7c9c82", weight=2,
                      fill=True, fill_color="#74c69d", fill_opacity=0.12).add_to(m)
        if prof["heat"] >= 3.5:
            folium.Circle(radius=260, location=[lat, lon], color="#e23b54", weight=2,
                          fill=True, fill_color="#e07a4a", fill_opacity=0.32).add_to(m)
            for dlat, dlon in [(0.0022, 0.0022), (0.0022, -0.0022), (-0.0022, 0.0022), (-0.0022, -0.0022)]:
                folium.Circle(radius=170, location=[lat + dlat, lon + dlon], color="#d99a2b",
                              weight=1, fill=True, fill_color="#f2b134", fill_opacity=0.28).add_to(m)
        folium.Marker(
            [lat, lon],
            tooltip=f"{borough} · Heat {prof['heat']}/5 · AQI {prof['aqi']}",
            popup=folium.Popup(
                f"<b>{borough}</b><br>Eco Score: {score}/100 ({grade})<br>"
                f"Trees: {prof['trees']}/sq km<br>Heat: {prof['heat']}/5<br>AQI: {prof['aqi']}",
                max_width=220),
            icon=folium.Icon(color="red" if prof["heat"] >= 3.5 else "green", icon="leaf", prefix="fa"),
        ).add_to(m)
        st_folium(m, width=1080, height=460, key="heatmap")

    # ----- COMPARE -----
    with t_compare:
        section("Compare with a borough average", "Your block vs. a typical block in another borough.")
        other = st.selectbox("Compare against", BOROUGHS,
                             index=BOROUGHS.index("Brooklyn" if borough != "Brooklyn" else "Manhattan"))
        other_center = BOROUGH_DATA[other]["center"]
        other_prof = block_profile(other_center[0], other_center[1], other)
        _, other_dims = eco_score(other_prof)
        st.plotly_chart(compare_bars(dims, other_dims, [f"Your block ({borough})", f"{other} avg"]),
                        width="stretch", config={"displayModeBar": False})

        section("🏆 Greenest blocks in NYC", "Where your block lands on the canopy leaderboard.")
        board = [("Park Slope", "Brooklyn", 892), ("Fort Greene", "Brooklyn", 734),
                 ("Upper West Side", "Manhattan", 712), ("Forest Hills", "Queens", 654),
                 ("Riverdale", "Bronx", 598), ("Your block", borough, prof["trees"])]
        for rank, (name, boro, trees) in enumerate(sorted(board, key=lambda x: -x[2]), 1):
            you = name == "Your block"
            st.markdown(
                f"""<div class="lb-row {'lb-you' if you else ''}">
                <span class="lb-rank">{rank}</span>
                <span class="lb-name">{'📍 ' if you else ''}{name} <span style="color:var(--muted); font-weight:500">· {boro}</span></span>
                <span class="lb-val">{trees} 🌳</span></div>""",
                unsafe_allow_html=True,
            )

    # ----- ACTION PLAN -----
    with t_actions:
        section("✅ Your block action plan", "Prioritized, concrete steps for this block.")
        pri_color = {"HIGH": ("#fdecef", "#e23b54"), "MEDIUM": ("#fbf2e2", "#b87f1e"), "LOW": ("#eef3ef", "#5e7e66")}
        for act, impact, pri in actions:
            bg, fg = pri_color[pri]
            st.markdown(
                f"""<div class="action">
                <span class="action-pri" style="background:{bg}; color:{fg}">{pri}</span>
                <div class="action-body"><b>{act}</b><br><span>{impact}</span></div></div>""",
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)
        section(f"🍂 {season} recommendations", "Seasonally-timed actions you can take right now.")
        for rec in recs:
            st.markdown(
                f"""<div class="action"><span class="action-pri" style="background:#eef0fb; color:#4a52a8">NOW</span>
                <div class="action-body"><b>{rec}</b></div></div>""",
                unsafe_allow_html=True,
            )

        st.markdown(
            """
            <div class="callout callout-info" style="margin-top:1rem">
              <b>📞 Need help getting started?</b><br>
              <span style="color:var(--muted)">Email trees@parks.nyc.gov · Call 311 (say "tree planting") · Share this plan with your community board.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Shared community data (read once for both Compete + Community tabs)
    bk = eco_community.block_key(lat, lon)
    sheets_on = eco_community.sheets_enabled()
    reports_df = eco_community.load_reports(st.session_state.session_reports)
    block_df = reports_df[reports_df["block_key"] == bk] if not reports_df.empty else reports_df
    achievements, my_points = eco_community.compute_achievements(
        prof, {"eco": score, "equity": equity_score, "missing": missing}, block_df)
    unlocked_n = sum(1 for a in achievements if a["unlocked"])

    # Which achievements are tied to a HIGH-priority need on this block
    priority_titles = set()
    if prof["heat"] >= 3.5:
        priority_titles.add("Heat Buster")
    if equity_score < 50:
        priority_titles.update({"Equity Champion", "Canopy Starter", "Block Forester"})
    if prof["aqi"] > 60:
        priority_titles.add("Clean Air Ally")
    if prof["transit"] < 70:
        priority_titles.add("Transit Advocate")
    if prof["recycle"] < 21:
        priority_titles.add("Clean Streak")

    # ----- COMPETE -----
    with t_compete:
        st.markdown(
            '<div class="section-title">🏆 Compete — Greenest Block in NYC '
            '<span class="ai-chip">LIVE</span></div>'
            '<div class="section-cap">Log real actions to earn points and climb the live, '
            'community-powered leaderboard.</div>',
            unsafe_allow_html=True,
        )
        if not sheets_on:
            st.markdown(
                '<div class="callout callout-info"><b>Demo mode</b> — a shared database isn\'t '
                'connected, so the leaderboard shows reference blocks plus anything you log this '
                'session. <span style="color:var(--muted)">Add Google Sheets credentials to persist '
                'community data across everyone.</span></div>',
                unsafe_allow_html=True,
            )

        cpt1, cpt2 = st.columns([1, 1.7])
        with cpt1:
            st.markdown(
                f"""
                <div class="points-card">
                  <div style="color:#4a52a8; font-weight:700; font-size:.8rem; text-transform:uppercase; letter-spacing:.05em">Your block</div>
                  <div class="points-num">{my_points}<span style="font-size:1rem; color:var(--muted)"> pts</span></div>
                  <div style="color:var(--muted); font-size:.9rem; margin-top:.2rem">{unlocked_n}/10 achievements unlocked</div>
                  <div style="color:var(--muted); font-size:.82rem; margin-top:.4rem">{borough} · {bk}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with cpt2:
            cat = st.radio("Leaderboard category", list(eco_community.LB_CATEGORIES),
                           format_func=lambda k: eco_community.LB_CATEGORIES[k],
                           horizontal=True, label_visibility="collapsed")
            lb = eco_community.leaderboard(reports_df, cat, eco_helper=_eco_helper)
            if lb:
                for rank, e in enumerate(lb, 1):
                    you = e["block_key"] == bk
                    st.markdown(
                        f"""<div class="lb-row {'lb-you' if you else ''}">
                        <span class="lb-rank">{rank}</span>
                        <span class="lb-name">{'📍 ' if you else ''}{e['label']}</span>
                        <span class="lb-val">{e['value']} {e['unit']}</span></div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No community actions logged yet — be the first on the Community tab! "
                           "Meanwhile, here are NYC's reference green blocks:")
                for rank, (name, boro, trees) in enumerate(eco_community.STATIC_BOARD, 1):
                    st.markdown(
                        f"""<div class="lb-row"><span class="lb-rank">{rank}</span>
                        <span class="lb-name">{name} <span style="color:var(--muted); font-weight:500">· {boro}</span></span>
                        <span class="lb-val">{trees} 🌳</span></div>""",
                        unsafe_allow_html=True,
                    )

        st.markdown("<br>", unsafe_allow_html=True)
        section("🎖️ Achievements", "Unlock badges by improving your block and logging action.")
        acols = st.columns(2)
        for i, a in enumerate(achievements):
            locked = not a["unlocked"]
            pri = (a["title"] in priority_titles) and locked
            with acols[i % 2]:
                st.markdown(
                    f"""
                    <div class="ach {'ach-locked' if locked else ''}">
                      <div class="ach-top">
                        <span class="ach-badge {'locked' if locked else ''}">{a['icon']}</span>
                        <div><div class="ach-title">{a['title']}</div>
                        <div class="ach-sub">{a['hint']}</div></div>
                        {'<span class="ach-pri">PRIORITY</span>' if pri else ''}
                      </div>
                      <div class="bar"><div class="bar-fill" style="width:{a['pct']}%"></div></div>
                      <div class="ach-sub" style="margin-top:.3rem">{a['current']}/{a['target']}{' · unlocked ✓' if a['unlocked'] else ''}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # ----- COMMUNITY -----
    with t_community:
        st.markdown(
            '<div class="section-title">🌳 Community — report real-world action</div>'
            '<div class="section-cap">Logged actions feed the leaderboard and the live map below. '
            'All reports are community-submitted and unverified.</div>',
            unsafe_allow_html=True,
        )
        can_submit = st.session_state.submit_count < 10

        def _submit(row):
            persisted = eco_community.append_report(row)
            st.session_state.session_reports.append(row)
            st.session_state.submit_count += 1
            eco_community._read_sheet.clear()
            st.toast("Logged! 🌳 Community-reported, unverified."
                     + ("" if persisted else " (saved this session)"), icon="🌳")
            st.rerun()

        fc1, fc2 = st.columns(2)
        with fc1:
            with st.form("tree_form", clear_on_submit=True):
                st.markdown("**🌳 A tree was planted here**")
                n_trees = st.number_input("How many trees?", 1, 50, 1)
                tname = st.text_input("Your name (optional)", key="tname")
                tree_sub = st.form_submit_button("Log planting", width="stretch")
            if tree_sub:
                if can_submit:
                    _submit(eco_community.make_report(lat, lon, borough, "tree_planted",
                            trees_count=n_trees, place=label[:40], display_name=tname))
                else:
                    st.warning("Submission limit reached for this session.")
        with fc2:
            with st.form("action_form", clear_on_submit=True):
                st.markdown("**✅ I completed a block action**")
                act_type = st.selectbox("Action", ["recycling", "compost", "cool_pavement",
                                                    "bike_lane", "green_buffer", "tree_care"])
                aname = st.text_input("Your name (optional)", key="aname")
                act_sub = st.form_submit_button("Log action", width="stretch")
            if act_sub:
                if can_submit:
                    _submit(eco_community.make_report(lat, lon, borough, "action_completed",
                            detail=act_type, place=label[:40], display_name=aname))
                else:
                    st.warning("Submission limit reached for this session.")

        # Live community map
        st.markdown("<br>", unsafe_allow_html=True)
        section("🗺️ Community activity map", "One pin per block where neighbors have logged action.")
        cmap = folium.Map(location=[lat, lon], zoom_start=13, tiles="CartoDB positron")
        folium.Marker([lat, lon], tooltip="Your block",
                      icon=folium.Icon(color="green", icon="leaf", prefix="fa")).add_to(cmap)
        if not reports_df.empty:
            for kb, g in reports_df.groupby("block_key"):
                try:
                    rlat, rlon = float(g.iloc[0]["lat"]), float(g.iloc[0]["lon"])
                except (TypeError, ValueError):
                    continue
                trees = int(g.loc[g["action_type"] == "tree_planted", "trees_count"].sum())
                folium.CircleMarker(
                    [rlat, rlon], radius=7 + min(8, trees), color="#8a93d6", fill=True,
                    fill_color="#8a93d6", fill_opacity=0.55,
                    popup=folium.Popup(f"<b>{g.iloc[0].get('place') or g.iloc[0].get('borough')}</b><br>"
                                       f"{len(g)} reports · {trees} trees<br><i>community-reported, unverified</i>",
                                       max_width=200)).add_to(cmap)
        st_folium(cmap, width=1080, height=380, key="community_map")

        # Recent activity feed
        section("📰 Recent activity", "")
        if reports_df.empty:
            st.caption("No reports yet. Be the first to log an action above!")
        else:
            recent = reports_df.tail(8).iloc[::-1]
            verb = {"tree_planted": "🌳 planted", "action_completed": "✅ completed",
                    "checklist_item": "📋 checked off"}
            for _, r in recent.iterrows():
                who = r.get("display_name") or "Anonymous"
                what = verb.get(r["action_type"], r["action_type"])
                extra = (f"{int(r['trees_count'])} trees" if r["action_type"] == "tree_planted"
                         else str(r.get("detail") or "").replace("_", " "))
                where = r.get("place") or r.get("borough") or r.get("block_key")
                st.markdown(
                    f"""<div class="lb-row"><span class="lb-name">
                    <b>{who}</b> {what} {extra} <span style="color:var(--muted)">· {where}</span></span></div>""",
                    unsafe_allow_html=True,
                )

    # ----- REPORT & EXPORT -----
    with t_report:
        section("📄 Download your block report", "A branded PDF plus raw data for spreadsheets and tools.")
        pdf = build_pdf(label, prof, score, grade, equity_score, rating, added, cooling, actions)
        export = {
            "location": label, "borough": borough,
            "coordinates": {"lat": lat, "lon": lon},
            "eco_score": score, "grade": grade,
            "trees_per_sqkm": prof["trees"], "heat_score": prof["heat"],
            "recycling_rate": prof["recycle"], "transit_score": prof["transit"],
            "air_quality_index": prof["aqi"], "tree_equity_score": round(equity_score),
            "added_home_value_usd": round(added), "annual_cooling_savings_usd": round(cooling),
            "generated": datetime.now().isoformat(),
        }
        csv = "Metric,Value\n" + "\n".join(
            f"{k},{v}" for k, v in export.items() if not isinstance(v, dict))

        d1, d2, d3 = st.columns(3)
        with d1:
            st.download_button("📄 PDF report", data=pdf, file_name=f"block_report_{borough}.pdf",
                               mime="application/pdf", width="stretch")
        with d2:
            st.download_button("📊 CSV data", data=csv, file_name=f"block_data_{borough}.csv",
                               mime="text/csv", width="stretch")
        with d3:
            st.download_button("🔌 JSON data", data=json.dumps(export, indent=2),
                               file_name=f"block_data_{borough}.json", mime="application/json",
                               width="stretch")

        with st.expander("Preview raw data (JSON)"):
            st.json(export)


# ============================================================================
# FOOTER
# ============================================================================
st.markdown(
    """
    <div class="app-footer">
      <b>Block-By-Block</b> · NYC Environmental Intelligence · 100% free<br>
      Borough baselines: NYC Open Data · Heat Vulnerability Index · EPA Air Quality.
      Block-level values are modeled estimates for directional guidance.
    </div>
    """,
    unsafe_allow_html=True,
)
