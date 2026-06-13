"""
eco_data.py — real-data layer + Heat-Wave Forecaster for Block-By-Block
=======================================================================
All network clients are defensive: short timeout, broad except → return None.
The combined `fetch_block_realdata()` substitutes the app's modeled values for any
field that couldn't be fetched and records provenance in `sources`, so the app
renders fully even with no connectivity and never raises.

Verified API facts (smoke-tested):
- Trees (Socrata uvpi-gqnh): NO `the_geom` column → query a lat/lon bounding box on
  the `latitude`/`longitude` columns; rows carry `zipcode`, `nta`, `status`, `health`.
- HVI (Socrata 4mhf-duep): keyed by `zcta20` (ZIP), `hvi` is a string "1".."5".
- Open-Meteo: free, no key, returns 48 hourly `apparent_temperature` points.
- NYC GeoSearch: returns features[].geometry.coordinates [lon,lat], properties.label.
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import plotly.graph_objects as go
import requests
import streamlit as st

TREES_URL = "https://data.cityofnewyork.us/resource/uvpi-gqnh.json"
HVI_URL = "https://data.cityofnewyork.us/resource/4mhf-duep.json"
METEO_URL = "https://api.open-meteo.com/v1/forecast"
GEOSEARCH_URL = "https://geosearch.planninglabs.nyc/v2/search"

# Borough-proxy HVI when ZIP-level lookup is unavailable (1=low .. 5=high vulnerability)
BOROUGH_HVI = {"Bronx": 5, "Manhattan": 4, "Brooklyn": 3, "Queens": 3, "Staten Island": 2}

# NWS HeatRisk apparent-temperature bands (°F)
HEAT_BANDS = [(80, 0), (90, 1), (103, 2), (115, 3)]
LEVEL_LABEL = {0: "None", 1: "Minor", 2: "Moderate", 3: "Major", 4: "Extreme"}


# ---------------------------------------------------------------------------
# API CLIENTS  (each cached; each returns None on any failure)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=86400)
def fetch_tree_canopy(lat, lon, radius_m=300):
    """Real street-tree density near a point via a lat/lon bounding box.

    Returns {"trees_per_sqkm", "raw_count", "zip", "nta", "health_good_frac"} or None.
    """
    try:
        dlat = radius_m / 111320.0
        dlon = radius_m / (111320.0 * math.cos(math.radians(lat)))
        where = (f"latitude between {lat - dlat} and {lat + dlat} "
                 f"and longitude between {lon - dlon} and {lon + dlon}")
        r = requests.get(TREES_URL, params={"$where": where,
                         "$select": "zipcode,nta,status,health", "$limit": 6000}, timeout=6)
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            return None
        count = len(rows)
        alive = sum(1 for x in rows if x.get("status") == "Alive")
        good = sum(1 for x in rows if x.get("health") == "Good")
        zips = Counter(x["zipcode"] for x in rows if x.get("zipcode"))
        ntas = Counter(x["nta"] for x in rows if x.get("nta"))
        area_km2 = (2 * dlat * 111.320) * (2 * dlon * 111.320 * math.cos(math.radians(lat)))
        return {
            "trees_per_sqkm": round(count / area_km2) if area_km2 else count,
            "raw_count": count,
            "zip": zips.most_common(1)[0][0] if zips else None,
            "nta": ntas.most_common(1)[0][0] if ntas else None,
            "health_good_frac": round(good / alive, 2) if alive else None,
        }
    except (requests.RequestException, ValueError, KeyError, ZeroDivisionError):
        return None


@st.cache_data(show_spinner=False, ttl=86400)
def fetch_hvi_for_zip(zcta):
    """NYC Heat Vulnerability Index (1..5) for a ZIP/ZCTA, or None."""
    if not zcta:
        return None
    try:
        r = requests.get(HVI_URL, params={"$where": f"zcta20='{zcta}'", "$limit": 1}, timeout=6)
        r.raise_for_status()
        rows = r.json()
        if isinstance(rows, list) and rows and rows[0].get("hvi") is not None:
            return int(float(rows[0]["hvi"]))
    except (requests.RequestException, ValueError, KeyError):
        pass
    return None


@st.cache_data(show_spinner=False, ttl=1800)
def fetch_forecast_48h(lat, lon):
    """48h hourly feels-like temps from Open-Meteo (no key), or None."""
    try:
        r = requests.get(METEO_URL, params={
            "latitude": lat, "longitude": lon,
            "hourly": "temperature_2m,apparent_temperature",
            "forecast_days": 2, "temperature_unit": "fahrenheit",
            "timezone": "America/New_York"}, timeout=6)
        r.raise_for_status()
        h = r.json().get("hourly", {})
        if h.get("time") and h.get("apparent_temperature"):
            return {"time": h["time"], "temp_f": h["temperature_2m"],
                    "apparent_f": h["apparent_temperature"], "source": "Open-Meteo"}
    except (requests.RequestException, ValueError, KeyError):
        pass
    return None


@st.cache_data(show_spinner=False, ttl=3600)
def geosearch_address(address):
    """Forward-geocode an NYC address via NYC GeoSearch. Returns (lat, lon, label) or None."""
    try:
        r = requests.get(GEOSEARCH_URL, params={"text": address, "size": 1}, timeout=6)
        r.raise_for_status()
        feats = r.json().get("features", [])
        if feats:
            lon, lat = feats[0]["geometry"]["coordinates"]
            return (lat, lon, feats[0]["properties"].get("label", address))
    except (requests.RequestException, ValueError, KeyError, IndexError):
        pass
    return None


@st.cache_data(show_spinner=False, ttl=3600)
def reverse_zip(lat, lon):
    """Best-effort ZIP from a reverse geocode (used for HVI when no trees nearby)."""
    try:
        from geopy.geocoders import Nominatim
        loc = Nominatim(user_agent="block-by-block-nyc", timeout=8).reverse((lat, lon), timeout=8)
        if loc and loc.raw:
            return loc.raw.get("address", {}).get("postcode")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# COMBINED FETCHER
# ---------------------------------------------------------------------------
@dataclass
class BlockRealData:
    trees: int
    heat: float
    aqi: int
    hvi: int
    zip: str | None
    forecast: dict | None
    health_good_frac: float | None
    sources: dict = field(default_factory=dict)

    @property
    def trees_live(self):
        return self.sources.get("trees") == "live"

    @property
    def hvi_live(self):
        return self.sources.get("heat") == "live"

    @property
    def forecast_live(self):
        return self.sources.get("forecast") == "live"


@st.cache_data(show_spinner="Fetching live block data…", ttl=1800)
def fetch_block_realdata(lat, lon, borough, modeled):
    """Fetch live data for a block, falling back to `modeled` per-field. Never raises.

    `modeled` is the app's block_profile dict (trees/heat/aqi/...). The returned
    object preserves those values for any field that couldn't be fetched live.
    """
    rlat, rlon = round(lat, 3), round(lon, 3)
    sources = {}

    tree = fetch_tree_canopy(rlat, rlon)
    if tree:
        trees, zcode = tree["trees_per_sqkm"], tree["zip"]
        health = tree["health_good_frac"]
        sources["trees"] = "live"
    else:
        trees, zcode, health = modeled["trees"], None, None
        sources["trees"] = "modeled"

    if not zcode:
        zcode = reverse_zip(rlat, rlon)

    hvi = fetch_hvi_for_zip(zcode)
    if hvi is not None:
        heat = float(hvi)                       # HVI 1–5 maps directly onto our 0–5 heat scale
        sources["heat"] = "live"
    else:
        hvi = BOROUGH_HVI.get(borough, round(modeled["heat"]))
        heat = modeled["heat"]
        sources["heat"] = "modeled"

    forecast = fetch_forecast_48h(rlat, rlon)
    sources["forecast"] = "live" if forecast else "modeled"

    # Air quality stays modeled (no free keyless real-time AQ source wired yet)
    sources["aqi"] = "modeled"

    return BlockRealData(trees=trees, heat=heat, aqi=modeled["aqi"], hvi=int(hvi),
                         zip=zcode, forecast=forecast, health_good_frac=health, sources=sources)


# ---------------------------------------------------------------------------
# HEAT-WAVE FORECASTER  (transparent, explainable; framed as AI in the UI)
# ---------------------------------------------------------------------------
def _band_level(temp_f):
    for thresh, lvl in HEAT_BANDS:
        if temp_f < thresh:
            return lvl
    return 4


def _danger_label(score):
    if score < 20:
        return "Low"
    if score < 40:
        return "Elevated"
    if score < 65:
        return "High"
    if score < 85:
        return "Severe"
    return "Extreme"


def _synth_forecast(hvi):
    """48h feels-like curve when Open-Meteo is unavailable, anchored on HVI."""
    base = 78 + (hvi - 3) * 3.5          # hotter base for higher-vulnerability blocks
    start = datetime.now().replace(minute=0, second=0, microsecond=0)
    times, apparent = [], []
    for h in range(48):
        t = start + timedelta(hours=h)
        # diurnal swing: peak ~3pm, trough ~5am
        swing = 11 * math.sin((t.hour - 9) / 24 * 2 * math.pi)
        times.append(t.strftime("%Y-%m-%dT%H:%M"))
        apparent.append(round(base + swing, 1))
    return {"time": times, "temp_f": apparent, "apparent_f": apparent, "source": "Modeled"}


def heat_forecast(forecast, hvi, trees_per_sqkm):
    """48h block heat-risk model: NWS bands + hyper-local HVI & canopy amplifiers.

    Returns a dict with peak, danger score/level, dangerous hours, the amplifier
    breakdown, and raw/adjusted series for charting. Fully deterministic and explainable.
    """
    modeled = forecast is None
    if modeled:
        forecast = _synth_forecast(hvi)

    times = forecast["time"][:48]
    raw = forecast["apparent_f"][:48]

    hvi_amp = round((hvi - 3) * 2.0, 1)                                  # ±4 °F
    canopy_amp = round(max(0.0, min(1.0, (300 - trees_per_sqkm) / 300)) * 4.0, 1)  # 0..+4 °F
    bump = hvi_amp + canopy_amp
    adj = [round(t + bump, 1) for t in raw]

    adj_levels = [_band_level(t) for t in adj]
    max_level = max(adj_levels) if adj_levels else 0
    hot_frac = (sum(1 for lv in adj_levels if lv >= 2) / len(adj_levels)) if adj_levels else 0
    danger_score = round(100 * (max_level / 4) * (0.6 + 0.4 * hot_frac)) if max_level else 0

    peak_i = max(range(len(raw)), key=lambda i: raw[i]) if raw else 0
    peak_apparent_f = raw[peak_i] if raw else 0
    peak_time = times[peak_i] if times else ""

    dangerous_hours = [(times[i], adj[i], LEVEL_LABEL[adj_levels[i]])
                       for i in range(len(adj)) if adj_levels[i] >= 2]

    return {
        "modeled": modeled,
        "times": times,
        "raw_apparent": raw,
        "adj_apparent": adj,
        "peak_apparent_f": peak_apparent_f,
        "peak_adj_f": max(adj) if adj else 0,
        "peak_time": peak_time,
        "danger_score": danger_score,
        "danger_level": _danger_label(danger_score),
        "dangerous_hours": dangerous_hours,
        "amp_breakdown": {"hvi": hvi_amp, "canopy": canopy_amp, "total": round(bump, 1)},
    }


def _fmt_hour(iso):
    """ISO hour → 'Sat 3PM' (cross-platform; %-I is not portable)."""
    try:
        d = datetime.strptime(iso, "%Y-%m-%dT%H:%M")
        hour = d.strftime("%I").lstrip("0") or "12"
        return f"{d.strftime('%a')} {hour}{d.strftime('%p')}"
    except (ValueError, TypeError):
        return iso


def forecast_chart(hf):
    """Plotly 48h forecast: raw feels-like vs. amplified block curve with risk bands."""
    times = hf["times"]
    x = list(range(len(times)))
    danger = hf["danger_score"] >= 40
    adj_color = "#e23b54" if danger else "#8a93d6"

    fig = go.Figure()
    # risk bands
    for y0, y1, c in [(90, 103, "rgba(217,154,43,.10)"), (103, 115, "rgba(224,122,74,.12)"),
                      (115, 130, "rgba(226,59,84,.14)")]:
        fig.add_hrect(y0=y0, y1=y1, line_width=0, fillcolor=c, layer="below")
    # raw feels-like
    fig.add_trace(go.Scatter(x=x, y=hf["raw_apparent"], mode="lines", name="Feels-like (NWS)",
                             line=dict(color="#9aa3ac", width=2),
                             hovertemplate="%{customdata}<br>%{y:.0f}°F<extra></extra>",
                             customdata=[_fmt_hour(t) for t in times]))
    # block-amplified
    fig.add_trace(go.Scatter(x=x, y=hf["adj_apparent"], mode="lines", name="Your block (AI-adjusted)",
                             line=dict(color=adj_color, width=3), fill="tonexty",
                             fillcolor="rgba(226,59,84,.08)" if danger else "rgba(138,147,214,.08)",
                             hovertemplate="%{customdata}<br>%{y:.0f}°F<extra></extra>",
                             customdata=[_fmt_hour(t) for t in times]))
    # peak marker
    if times:
        peak_i = max(range(len(hf["raw_apparent"])), key=lambda i: hf["raw_apparent"][i])
        fig.add_annotation(x=peak_i, y=hf["adj_apparent"][peak_i],
                           text=f"peak {hf['peak_adj_f']:.0f}°F", showarrow=True, arrowhead=2,
                           arrowcolor=adj_color, font=dict(size=11, color=adj_color), ay=-30)

    tickvals = x[::6]
    ticktext = [_fmt_hour(times[i]) for i in tickvals] if times else []
    fig.update_layout(
        height=340, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#2b2f33"),
        legend=dict(orientation="h", y=1.16, x=0),
        xaxis=dict(tickmode="array", tickvals=tickvals, ticktext=ticktext,
                   gridcolor="#e6e9e6", tickfont=dict(size=10)),
        yaxis=dict(title="°F feels-like", gridcolor="#e6e9e6"),
    )
    return fig
