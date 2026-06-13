# Architecture & Developer Guide

This document explains how Block-By-Block is built: the module layout, how data flows
from raw APIs to the UI, the math behind the scores and the heat forecaster, the
community/Sheets schema, and how to extend the app. For user-facing docs and setup, see
the [README](../README.md).

---

## 1. Module overview

The app is three Python files, deliberately separated so the data and community logic
are testable **without** a running Streamlit server.

```
eco_app_advanced.py   UI: design system, sidebar, scoring, charts, PDF, tab render flow
eco_data.py           Live API clients, BlockRealData, Heat-Wave Forecaster, forecast chart
eco_community.py      Google Sheets I/O, points/leaderboard aggregation, achievements
```

`eco_app_advanced.py` imports the other two. There is **no** reverse dependency:
`eco_data.py` and `eco_community.py` never import the app. Where they need app logic
(e.g. modeled values, or eco-score for a leaderboard block), the app **passes it in** as
an argument or callable. This keeps the dependency graph acyclic and the helpers pure.

> **Why a single entry file name?** Streamlit Community Cloud is configured to run
> `eco_app_advanced.py`. Keep that filename. The helper modules live beside it in the
> same repo and are imported normally (Streamlit adds the script's directory to
> `sys.path` at runtime).

---

## 2. The core data contract: `block_profile`

Everything downstream — scoring, charts, the PDF, exports — reads a single dict produced
by `block_profile(lat, lon, borough)`:

```python
{
  "borough": str,
  "trees": int,          # trees per sq km
  "heat": float,         # 0–5, higher = more heat-vulnerable
  "recycle": int,        # %
  "transit": int,        # 0–100
  "aqi": int,            # air quality index, lower = cleaner
  "target_trees": int,   # borough canopy target (for equity)
  "color": str,          # borough accent hex
}
```

`block_profile` produces **modeled** values (borough baseline + a deterministic,
coordinate-seeded micro-variation via SHA-256 — see `_frac()`). Real data is then
**overlaid** on top of this dict (next section). Because every consumer reads only this
shape, swapping modeled values for live ones is a **localized one-line-per-field**
change — no downstream edits.

---

## 3. Live data layer (`eco_data.py`)

### 3.1 Clients

Each client is decorated with `@st.cache_data` (so repeated reruns don't re-hit the
network), uses a short `timeout`, and **returns `None` on any failure** (broad except).
`None` is the signal for "fall back to modeled."

| Function | Source | TTL | Returns | Notes |
|---|---|---|---|---|
| `fetch_tree_canopy(lat, lon, radius_m=300)` | Tree Census `uvpi-gqnh` | 24 h | `{trees_per_sqkm, raw_count, zip, nta, health_good_frac}` | The dataset has **no `the_geom`** column, so we query a lat/lon **bounding box** on the `latitude`/`longitude` columns, then aggregate client-side (count, modal ZIP, alive/healthy fractions). Density = count ÷ bbox area. |
| `fetch_hvi_for_zip(zcta)` | HVI `4mhf-duep` | 24 h | `int` 1–5 | The current HVI dataset is keyed by **`zcta20` (ZIP)**, not NTA; `hvi` is a string we cast to int. |
| `fetch_forecast_48h(lat, lon)` | Open-Meteo | 30 min | `{time[], temp_f[], apparent_f[], source}` | No key. `hourly=temperature_2m,apparent_temperature`, `forecast_days=2`, Fahrenheit, America/New_York. |
| `geosearch_address(address)` | NYC GeoSearch | 1 h | `(lat, lon, label)` | Forward geocoding; the app uses this first and falls back to Nominatim. |
| `reverse_zip(lat, lon)` | Nominatim | 1 h | ZIP `str` | Used to find a ZIP for HVI when no trees (hence no ZIP) are nearby. |

### 3.2 `lat/lon → ZIP → HVI` mapping

The trickiest join. The Heat Vulnerability Index is per-ZIP, but the user gives
coordinates. Resolution ladder (in `fetch_block_realdata`):

1. **Trees carry a ZIP.** `fetch_tree_canopy` returns the **modal `zipcode`** of trees in
   the radius → look up HVI by that ZIP. (Best; one extra cheap call.)
2. **No trees nearby** (park interiors, water edges) → `reverse_zip()` reverse-geocodes a
   ZIP.
3. **Still nothing** → borough-proxy HVI (`BOROUGH_HVI = {Bronx:5, Manhattan:4,
   Brooklyn:3, Queens:3, Staten Island:2}`), or the modeled heat value.

The ZIP is *also* used to **fix borough detection** in the app: `borough_from_zip()` maps
NYC ZIP prefixes to boroughs, which is far more reliable than the coarse lat/lon
thresholds in `get_borough_from_coords()` (those mislabel edge cases — e.g. Yankee
Stadium reads as Manhattan by latitude alone, but its ZIP `104xx` correctly says Bronx).

### 3.3 The combined fetcher

```python
fetch_block_realdata(lat, lon, borough, modeled) -> BlockRealData
```

- Rounds `lat`/`lon` to 3 decimals **before** calling (≈110 m; matches `block_profile`'s
  block granularity and maximizes cache hits).
- Calls the clients; for each `None`, copies the matching value from `modeled` and marks
  it `"modeled"` in `sources`, else `"live"`.
- Maps a live HVI (1–5) directly onto the `heat` scale (HVI *is* heat vulnerability).
- Air quality stays modeled (no free keyless block-level AQ source is wired in yet).

```python
@dataclass
class BlockRealData:
    trees: int
    heat: float
    aqi: int
    hvi: int
    zip: str | None
    forecast: dict | None
    health_good_frac: float | None
    sources: dict          # field -> "live" | "modeled"
    # properties: trees_live, hvi_live, forecast_live
```

In the app, after `prof = block_profile(...)`:

```python
rd = eco_data.fetch_block_realdata(lat, lon, borough, prof)
zb = borough_from_zip(rd.zip)            # refine borough from the (accurate) ZIP
if zb and zb != borough:
    borough = zb
    prof = block_profile(lat, lon, borough)
prof["trees"] = rd.trees                 # live: Tree Census
prof["heat"]  = rd.heat                  # live: HVI
prof["aqi"]   = rd.aqi
```

The `rd.sources` map drives the `● LIVE` / `○ MODELED` badges on the metric cards.

---

## 4. The Heat-Wave Forecaster

A transparent, deterministic model (`heat_forecast`) — framed as "AI" in the UI, but
fully explainable.

### 4.1 Inputs → outputs

```python
heat_forecast(forecast, hvi, trees_per_sqkm) -> dict
```

**Step 1 — base risk per hour** from the forecast's `apparent_f` using NWS HeatRisk
bands (`HEAT_BANDS`):

| Feels-like (°F) | Level |
|---|---|
| < 80 | 0 None |
| 80–90 | 1 Minor |
| 90–103 | 2 Moderate |
| 103–115 | 3 Major |
| ≥ 115 | 4 Extreme |

**Step 2 — hyper-local amplifiers** (the block-level value-add), added in °F **before**
re-bucketing so they're chartable and explainable:

```
hvi_amp    = (hvi - 3) * 2.0                         # ±4 °F (HVI 5 → +4, HVI 1 → −4)
canopy_amp = clamp((300 - trees)/300, 0, 1) * 4.0    # sparse canopy → up to +4 °F
adj[h]     = apparent_f[h] + hvi_amp + canopy_amp
```

**Step 3 — outputs:**

```
danger_score = round(100 * (max_adj_level / 4) * (0.6 + 0.4 * frac_hours_level≥2))
danger_level = Low <20 · Elevated <40 · High <65 · Severe <85 · Extreme ≥85
```

plus `peak_apparent_f` + `peak_time`, `peak_adj_f`, `dangerous_hours` (every hour at
adjusted level ≥ 2), and `amp_breakdown` (`{hvi, canopy, total}` for the explainer).

### 4.2 Fallback

If `forecast is None` (Open-Meteo unreachable), `_synth_forecast(hvi)` builds a 48-hour
diurnal curve (`base = 78 + (hvi-3)*3.5`, sinusoidal day/night swing) and the result is
flagged `modeled: True`. The same amplifiers apply, so the feature never goes blank.

### 4.3 The chart

`forecast_chart(hf)` builds a Plotly figure: the raw NWS feels-like line, the block's
amplified line (lipstick if dangerous, periwinkle otherwise) filled between them, NWS
risk bands at 90/103/115 °F, a peak annotation, and a day/hour axis. `_fmt_hour()`
formats ISO timestamps cross-platform (avoids the non-portable `%-I`).

---

## 5. Scoring (`eco_app_advanced.py`)

`eco_score(prof)` normalizes each dimension to 0–100 (higher = greener) and weights them:

```
tree_equity = min(100, trees / target_trees * 100)        weight 0.30
air         = 100 - aqi                                    weight 0.20
heat        = (5 - heat) / 5 * 100                         weight 0.20
recycle     = min(100, recycle / 35 * 100)                 weight 0.15
transit     = transit                                      weight 0.15
```

`grade_for(score)` maps the total to **A/B/C/D/F** with a palette color. Other helpers:
`tree_equity()` (score + rating + trees missing), `property_impact()` (added home value &
cooling savings from canopy), `heat_alert()` (cooling-center text), `seasonal_recs()`,
and `action_plan()` (prioritized High/Medium/Low actions from the block's weaknesses).

---

## 6. Community & gamification (`eco_community.py`)

### 6.1 Persistence model

Raw, append-only **events** are stored; all aggregates are computed on the fly with
pandas. This keeps Google Sheets traffic to **1 cached read per load + 1 append per
submit** (well within quotas) and avoids read-modify-write races on a materialized
leaderboard.

**Worksheet `reports`** columns (`REPORT_COLUMNS`):

```
id            uuid4 hex (idempotency key)
timestamp     ISO
block_key     "40.758,-73.986"  (round(lat,3),round(lon,3) — matches block_profile)
lat, lon      rounded to 3 dp (block centroid, not raw click — light privacy)
borough
action_type   tree_planted | action_completed | checklist_item
trees_count   int (≥0)
detail        tag/checklist id (e.g. "recycling")
place         human label (e.g. reverse-geocoded address)
display_name  sanitized, ≤32 chars, blank → "Anonymous"
status        community_unverified
session_hash  sha256(name + day) — abuse audit only
```

### 6.2 Connection & I/O

- `_get_conn()` (`@st.cache_resource`) returns a `GSheetsConnection` **only if** the
  `[connections.gsheets]` secret exists; otherwise `None`. `sheets_enabled()` exposes this.
- `_read_sheet()` (`@st.cache_data(ttl=60)`) reads with `ttl=0` (we own the cache).
- `load_reports(session_reports)` merges the sheet with the current session's reports and
  dedups on `id`.
- `append_report(row)` reads fresh → dedups on `id` → concatenates → `conn.update()` →
  clears the read cache. Returns `False` when Sheets is disabled (caller keeps it
  session-only).

**Graceful degradation:** with no secret, `sheets_enabled()` is `False`, the Compete tab
shows a "Demo mode" banner, the leaderboard falls back to `STATIC_BOARD` (famous green
blocks), and submissions live in `st.session_state.session_reports` for the session.

### 6.3 Points & leaderboard

```
POINTS = {tree_planted: 15, action_completed: 10, checklist_item: 8}
# tree_planted earns +5 per extra tree beyond the first
```

`leaderboard(df, category, eco_helper, top=8)` groups by `block_key` and computes one of
six categories (`LB_CATEGORIES`):

| Category | Formula |
|---|---|
| `trees` | Σ `trees_count` |
| `actions` | row count |
| `recycling` | count of `action_completed` whose `detail` ∈ `RECYCLING_TAGS` |
| `temp` | `trees_added * 0.015` °F cooled (modeled) |
| `canopy_pct` | `100 * trees_added / modeled_base_trees` |
| `combined` (default) | `points + 0.5 * eco_score` |

`canopy_pct` and `combined` need `eco_helper(lat, lon, borough) -> (modeled_trees,
eco_score)`, which the app supplies as `_eco_helper` (cheap, no network).

### 6.4 Achievements

`compute_achievements(prof, scores, block_df)` returns 10 achievements with `current` /
`target` / `unlocked` / `pct`, tied to existing metrics and logged actions (Seedling,
Canopy Starter, Block Forester [laddered], Heat Buster, Clean Streak, Equity Champion,
Transit Advocate, Clean Air Ally, Plan Finisher, Community Pillar). In the UI, any locked
achievement whose metric triggered a **HIGH** action-plan item gets a lipstick "Priority"
chip.

---

## 7. UI & render flow (`eco_app_advanced.py`)

Top to bottom: page config + PWA injection → the CSS **design system** (a `:root`
token block: `--sage`, `--charcoal`, `--periwinkle`, `--lipstick`, with legacy
`--green-*` aliased) → data constants → geo/scoring/chart/PDF helpers → session-state
init (via `setdefault`, so keys are robust to pre-seeded state) → sidebar location
picker → hero → main render.

The main render (when a location is set) computes `prof`, overlays real data, runs the
forecaster, then draws: location banner, optional heat alert, Eco Score gauge, four
metric cards, and **eight tabs** (`Profile`, `Heat Forecast`, `Heat Map`, `Compare`,
`Action Plan`, `Compete`, `Community`, `Report`).

Small HTML helpers: `metric_card(..., live=)` (renders a card with an optional provenance
badge), `src_badge(live)`, and `section(title, caption)`.

---

## 8. Extending the app

**Add a new live metric** (e.g. real air quality):
1. Write a cached client in `eco_data.py` returning the value or `None`.
2. Call it in `fetch_block_realdata`, add the field to `BlockRealData`, set
   `sources["aqi"]`.
3. In the app, overwrite `prof["aqi"] = rd.aqi` and pass `live=rd.aqi_live` to the metric
   card. Nothing else changes (the `block_profile` contract holds).

**Add a leaderboard category:** add an entry to `LB_CATEGORIES` and a branch in
`leaderboard()`.

**Add an achievement:** append a tuple to the `defs` list in `compute_achievements()`.

**Change the theme:** edit the `:root` tokens in the CSS block and `primaryColor` in
`.streamlit/config.toml`. Inline Plotly/folium hexes reference the same palette values.

---

## 9. Testing & verification

The data and community logic are pure and importable, so unit-test them directly. For
the full app, use Streamlit's headless `AppTest`:

```python
import sys; sys.path.insert(0, "<repo dir>")          # mirror runtime sys.path
from streamlit.testing.v1 import AppTest

at = AppTest.from_file("eco_app_advanced.py", default_timeout=60)
at.session_state["lat"] = 40.8296      # item assignment — NOT at.session_state.update()
at.session_state["lon"] = -73.9261
at.session_state["method"] = "borough"
at.run()
assert not at.exception
```

Run across **landing**, a normal **borough**, a **heat-vulnerable block** (Bronx), and an
**out-of-bounds** point. Because `st.tabs` renders all children, a single `at.run()`
exercises the PDF generator, every Plotly chart, the maps, and all tabs.

**Offline / degradation test:** point the client base URLs at an unreachable host, clear
the caches, and confirm `fetch_block_realdata` returns all-`modeled` and the app renders
without exceptions.

> **Screenshot note:** Streamlit holds a persistent WebSocket, so network-idle
> screenshot tools time out. Capture via a browser-driving tool instead; Plotly-heavy
> tabs may still need a retry between renders.
