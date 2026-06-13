"""
eco_community.py — gamification + community layer for Block-By-Block
====================================================================
Persistence is Google Sheets (st-gsheets-connection) so data survives Streamlit
Community Cloud's ephemeral filesystem. EVERYTHING degrades gracefully: with no
`[connections.gsheets]` secret (e.g. local dev), `sheets_enabled()` is False, reads
return an empty frame, and the app falls back to a static + session-only experience.

Design: store raw append-only events in a `reports` worksheet; compute every
leaderboard/achievement aggregate on the fly with pandas (1 cached read per load,
1 append per submit — well within Sheets quotas, no read-modify-write races).
"""

import hashlib
import uuid
from datetime import datetime

import pandas as pd
import streamlit as st

REPORT_COLUMNS = ["id", "timestamp", "block_key", "lat", "lon", "borough",
                  "action_type", "trees_count", "detail", "place", "display_name",
                  "status", "session_hash"]

POINTS = {"tree_planted": 15, "action_completed": 10, "checklist_item": 8}
RECYCLING_TAGS = {"compost", "recycling", "compost_program", "recycle"}

# Fallback leaderboard when Sheets is unavailable (neighborhood, borough, trees).
STATIC_BOARD = [
    ("Park Slope", "Brooklyn", 892), ("Fort Greene", "Brooklyn", 734),
    ("Upper West Side", "Manhattan", 712), ("Forest Hills", "Queens", 654),
    ("Riverdale", "Bronx", 598), ("St. George", "Staten Island", 540),
]

LB_CATEGORIES = {
    "combined": "🏆 Combined score",
    "trees": "🌳 Most trees added",
    "canopy_pct": "📈 Biggest canopy boost",
    "temp": "🧊 Most heat cooled",
    "recycling": "♻️ Recycling actions",
    "actions": "✅ Most actions logged",
}


# ---------------------------------------------------------------------------
# CONNECTION (graceful: returns None when no secret / package / network)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _get_conn():
    try:
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            from streamlit_gsheets import GSheetsConnection
            return st.connection("gsheets", type=GSheetsConnection)
    except Exception:
        pass
    return None


def sheets_enabled():
    return _get_conn() is not None


def block_key(lat, lon):
    """Stable per-block id (~110 m), matching block_profile's 3-dp rounding."""
    return f"{round(lat, 3)},{round(lon, 3)}"


def session_hash(seed=""):
    day = datetime.now().strftime("%Y-%m-%d")
    return hashlib.sha256(f"{seed}|{day}".encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# READ / WRITE
# ---------------------------------------------------------------------------
def _empty_df():
    return pd.DataFrame(columns=REPORT_COLUMNS)


@st.cache_data(ttl=60, show_spinner=False)
def _read_sheet():
    conn = _get_conn()
    if conn is None:
        return _empty_df()
    try:
        df = conn.read(worksheet="reports", ttl=0)
        if df is None or df.empty:
            return _empty_df()
        df = df.dropna(how="all")
        for col in REPORT_COLUMNS:
            if col not in df.columns:
                df[col] = None
        return df[REPORT_COLUMNS]
    except Exception:
        return _empty_df()


def load_reports(session_reports=None):
    """Sheet reports merged with this session's reports (dedup on id)."""
    df = _read_sheet()
    if session_reports:
        df = pd.concat([df, pd.DataFrame(session_reports)], ignore_index=True)
    if not df.empty:
        df = df.drop_duplicates(subset="id", keep="last")
        df["trees_count"] = pd.to_numeric(df["trees_count"], errors="coerce").fillna(0).astype(int)
    return df


def make_report(lat, lon, borough, action_type, trees_count=0, detail="", place="", display_name=""):
    name = (display_name or "").strip()[:32] or "Anonymous"
    return {
        "id": uuid.uuid4().hex,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "block_key": block_key(lat, lon),
        "lat": round(lat, 3), "lon": round(lon, 3), "borough": borough,
        "action_type": action_type, "trees_count": int(trees_count or 0),
        "detail": (detail or "").strip()[:60], "place": (place or "").strip()[:60],
        "display_name": name, "status": "community_unverified",
        "session_hash": session_hash(name),
    }


def append_report(row):
    """Append one report to the Sheet. Returns True on success (or if Sheets disabled,
    caller keeps it session-only). Idempotent on `id`."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        cur = conn.read(worksheet="reports", ttl=0)
        cur = _empty_df() if cur is None else cur.dropna(how="all")
        if not cur.empty and "id" in cur.columns and row["id"] in set(cur["id"].astype(str)):
            return True
        new = pd.concat([cur, pd.DataFrame([row])], ignore_index=True)
        conn.update(worksheet="reports", data=new)
        _read_sheet.clear()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# AGGREGATION  (pure pandas — unit-testable without Streamlit/Sheets)
# ---------------------------------------------------------------------------
def points_for(action_type, trees_count=0):
    base = POINTS.get(action_type, 0)
    if action_type == "tree_planted":
        base += 5 * max(0, int(trees_count or 0) - 1)
    return base


def _block_rollup(df):
    """One row per block_key with the raw aggregates leaderboards need."""
    if df.empty:
        return pd.DataFrame(columns=["block_key", "borough", "lat", "lon", "trees", "actions",
                                     "recycling", "points"])
    rows = []
    for bk, g in df.groupby("block_key"):
        trees = int(g.loc[g["action_type"] == "tree_planted", "trees_count"].sum())
        recycling = int(((g["action_type"] == "action_completed") &
                         (g["detail"].astype(str).str.lower().isin(RECYCLING_TAGS))).sum())
        pts = int(sum(points_for(a, t) for a, t in zip(g["action_type"], g["trees_count"])))
        first = g.iloc[0]
        rows.append({"block_key": bk, "borough": first.get("borough", "—"),
                     "lat": first.get("lat"), "lon": first.get("lon"),
                     "trees": trees, "actions": int(len(g)),
                     "recycling": recycling, "points": pts})
    return pd.DataFrame(rows)


def leaderboard(df, category="combined", eco_helper=None, top=8):
    """Ranked list of {block_key, borough, label, value, unit} for a category.

    eco_helper(lat, lon, borough) -> (modeled_trees, eco_score_int); used only for
    'combined' and 'canopy_pct'. Falls back gracefully if not provided.
    """
    roll = _block_rollup(df)
    if roll.empty:
        return []

    def eco(row):
        if eco_helper and row["lat"] is not None:
            try:
                return eco_helper(float(row["lat"]), float(row["lon"]), row["borough"])
            except Exception:
                return (300, 50)
        return (300, 50)

    out = []
    for _, r in roll.iterrows():
        base_trees, eco_score = eco(r)
        if category == "trees":
            val, unit = r["trees"], "🌳"
        elif category == "actions":
            val, unit = r["actions"], "actions"
        elif category == "recycling":
            val, unit = r["recycling"], "♻️"
        elif category == "temp":
            val, unit = round(r["trees"] * 0.015, 2), "°F cooler"
        elif category == "canopy_pct":
            val, unit = round(100 * r["trees"] / max(1, base_trees), 1), "% canopy"
        else:  # combined
            val, unit = round(r["points"] + 0.5 * eco_score), "pts"
        label = f"{r['borough']} · {r['block_key']}"
        out.append({"block_key": r["block_key"], "borough": r["borough"],
                    "label": label, "value": val, "unit": unit})
    out.sort(key=lambda d: d["value"], reverse=True)
    return out[:top]


# ---------------------------------------------------------------------------
# ACHIEVEMENTS  (tie to existing metrics + logged actions)
# ---------------------------------------------------------------------------
def compute_achievements(prof, scores, block_df):
    """Return a list of achievement dicts with progress, unlock state, and priority.

    prof: block_profile dict; scores: {eco, equity, missing};
    block_df: reports filtered to the current block_key.
    """
    trees_logged = int(block_df.loc[block_df["action_type"] == "tree_planted", "trees_count"].sum()) if not block_df.empty else 0
    n_actions = int(len(block_df))
    points = int(sum(points_for(a, t) for a, t in zip(block_df["action_type"], block_df["trees_count"]))) if not block_df.empty else 0
    recycling = int(((block_df["action_type"] == "action_completed") &
                     (block_df["detail"].astype(str).str.lower().isin(RECYCLING_TAGS))).sum()) if not block_df.empty else 0

    defs = [
        ("Seedling", "🌱", n_actions, 1, "Log your first action on this block"),
        ("Canopy Starter", "🌳", trees_logged, 5, "Log 5 trees planted on your block"),
        ("Block Forester", "🌲", trees_logged, 25, "Log 25 trees planted on your block"),
        ("Heat Buster", "🧊", 1 if prof["heat"] < 3.5 else 0, 1, "Bring this block's heat vulnerability below 3.5/5"),
        ("Clean Streak", "♻️", max(prof["recycle"] // 7 if prof["recycle"] >= 21 else 0, recycling), 3, "Reach a strong recycling rate or log 3 recycling actions"),
        ("Equity Champion", "⚖️", round(scores["equity"]), 60, "Reach a tree-equity score of 60+"),
        ("Transit Advocate", "🚌", prof["transit"], 70, "Reach strong transit access (70+)"),
        ("Clean Air Ally", "💨", 1 if prof["aqi"] <= 50 else 0, 1, "Reach 'Good' air quality (AQI ≤ 50)"),
        ("Plan Finisher", "✅", n_actions, 3, "Log progress on your top action-plan items"),
        ("Community Pillar", "🏛️", points, 100, "Earn 100 community points on this block"),
    ]
    achievements = []
    for title, icon, cur, target, hint in defs:
        cur = max(0, min(cur, target))
        achievements.append({
            "title": title, "icon": icon, "current": cur, "target": target,
            "unlocked": cur >= target, "hint": hint,
            "pct": int(100 * cur / target) if target else 0,
        })
    return achievements, points
