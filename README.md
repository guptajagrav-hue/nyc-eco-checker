# 🌿 Block-By-Block — NYC Environmental Intelligence

A hyper-local environmental dashboard for New York City. Enter an address, click the
map, or pick a borough and get a **block-level profile** of tree canopy, heat exposure,
air quality, recycling, and transit — powered by **live NYC open data**, distilled into
a single **Eco Score**, and paired with a **48-hour AI heat-wave forecast** and a
**community action leaderboard**.

![Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-7c9c82)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Data](https://img.shields.io/badge/Data-Live%20NYC%20Open%20Data-8a93d6)

> **TL;DR — run it locally**
> ```bash
> pip install -r requirements.txt
> streamlit run eco_app_advanced.py
> ```
> Then open <http://localhost:8501>. No API keys required. (Community persistence is
> optional — see [Community features setup](#-community-features-setup-optional).)

---

## 📑 Table of contents

1. [What it is](#-what-it-is)
2. [Feature tour (every tab explained)](#-feature-tour)
3. [How to use it](#-how-to-use-it)
4. [Setup & installation](#-setup--installation)
5. [Launching the app](#-launching-the-app)
6. [Community features setup (optional)](#-community-features-setup-optional)
7. [Deploying to Streamlit Community Cloud](#-deploying-to-streamlit-community-cloud)
8. [Data sources & methodology](#-data-sources--methodology)
9. [Project structure](#-project-structure)
10. [Configuration reference](#-configuration-reference)
11. [Troubleshooting](#-troubleshooting)
12. [Roadmap](#-roadmap)
13. [For developers](#-for-developers)

---

## 🌎 What it is

Block-By-Block answers a simple question — **"how healthy is *my* block, and what can I
do about it?"** — for any block across New York City's five boroughs.

It combines real municipal datasets with a transparent scoring model and an
engagement loop:

- **Real data, honestly labeled.** Tree canopy, heat vulnerability, and the weather
  forecast are pulled live. Each metric shows a `● LIVE` or `○ MODELED` badge so you
  always know what's measured vs. estimated.
- **One number, then the detail.** A 0–100 **Eco Score** (A–F grade) summarizes the
  block; tabs drill into each dimension.
- **Forward-looking.** A 48-hour **Heat-Wave Forecaster** predicts dangerous hours for
  *this specific block*, accounting for its urban heat-island effect and tree cover.
- **Action, not just analysis.** A prioritized action plan, a community leaderboard,
  and achievement badges turn insight into participation.

Everything is **free** and requires **no API keys** to run. If a data source is ever
unreachable, the app falls back to a modeled estimate and **never crashes**.

---

## 🧭 Feature tour

After you choose a location, the app shows a **location banner** (address, ZIP, and a
`● N LIVE SOURCES` badge), a **heat-risk alert** if conditions warrant, the **Eco
Score** gauge, four headline **metric cards**, and then eight tabs:

| Tab | What you'll find |
|---|---|
| **📈 Profile** | A radar chart scoring all five dimensions 0–100, plus "value impact" cards: estimated added home value and annual cooling savings from canopy, tree-equity score, and trees needed to hit the borough target. |
| **🌡️ Heat Forecast** | The **AI heat-wave forecaster**. Block danger level + risk score, peak feels-like temperature and time, count of dangerous hours, a 48-hour chart (your block's adjusted curve vs. the raw NWS forecast with risk bands), an explainable "why your block runs hotter" breakdown, and the proactive alert windows. |
| **🗺️ Heat Map** | An interactive map of the block with graduated heat-risk circles (green buffer → red core) and a rich popup of the block's stats. |
| **⚖️ Compare** | Your block vs. a typical block in any other borough (grouped bar chart), plus a "greenest blocks in NYC" reference leaderboard with your block slotted in. |
| **✅ Action Plan** | Prioritized **High / Medium / Low** actions tailored to *this* block's weaknesses, plus season-aware recommendations and how-to-get-started contacts (311, NYC Parks). |
| **🏆 Compete** | A live, community-powered leaderboard across **six categories** (most trees added, biggest canopy boost, most heat cooled, recycling actions, most actions logged, combined score), your block's point total, and a grid of **10 unlockable achievements** with progress bars. |
| **🌳 Community** | Log real-world action — "a tree was planted here" or "I completed a block action." Submissions feed the leaderboard and appear on a live community map and recent-activity feed. (Persisted to Google Sheets when configured; session-only otherwise.) |
| **📄 Report** | Download a branded **PDF report**, or export the raw data as **CSV** or **JSON**. |

### The Eco Score
A weighted blend of five dimensions, each normalized to 0–100 (higher = greener):

| Dimension | Weight |
|---|---|
| Tree equity | 30% |
| Air quality | 20% |
| Heat comfort | 20% |
| Recycling | 15% |
| Transit access | 15% |

Grades: **A** ≥ 85 · **B** ≥ 70 · **C** ≥ 55 · **D** ≥ 40 · **F** below.

---

## 🖱️ How to use it

1. **Pick a location** in the left sidebar using any of three methods:
   - **✏️ Type an address** — any NYC address or landmark (e.g. *Times Square*,
     *Prospect Park*, *Yankee Stadium*). Resolved by NYC GeoSearch.
   - **🖱️ Click the map** — drop a pin anywhere in the five boroughs.
   - **🏙️ Pick a borough** — jump straight to a known landmark.
2. **Read the headline** — the Eco Score gauge and the four metric cards (tree canopy,
   heat vulnerability, air quality, transit). Watch the `● LIVE` / `○ MODELED` badges.
3. **Explore the tabs** (see the [feature tour](#-feature-tour) above). Start with
   **Heat Forecast** for the standout feature and **Action Plan** for what to do.
4. **Log action** on the **Community** tab — record a tree planting or completed action;
   watch your block climb the **Compete** leaderboard and unlock achievements.
5. **Export** your block's report from the **Report** tab (PDF / CSV / JSON).

> Locations outside NYC's five boroughs show a friendly "outside the data area" notice
> instead of a profile.

---

## 🛠️ Setup & installation

### Prerequisites
- **Python 3.11** (3.10+ should work)
- `pip` and the ability to create a virtual environment

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/guptajagrav-hue/nyc-eco-checker.git
cd nyc-eco-checker

# 2. (Recommended) create and activate a virtual environment
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt
```

That's it — **no API keys are needed** for the core app and live data. (Optional Google
Sheets credentials unlock shared community persistence; see below.)

---

## 🚀 Launching the app

```bash
streamlit run eco_app_advanced.py
```

Streamlit prints a local URL (default <http://localhost:8501>) and opens it in your
browser. To use a different port:

```bash
streamlit run eco_app_advanced.py --server.port 8502
```

To stop the app, press **Ctrl-C** in the terminal.

---

## 🌳 Community features setup (optional)

The **Compete** leaderboard and **Community** reports persist in **Google Sheets** so
they're shared across everyone using the app. **Without credentials the app still runs
fully** — it enters a graceful **"Demo mode"** where reports are kept only for your
current session and the leaderboard shows reference blocks.

To enable shared persistence:

1. **Create a Google Cloud service account**, enable the **Google Sheets API** and
   **Google Drive API**, and download its **JSON key**.
2. **Create a Google Sheet** with a worksheet named **`reports`** whose first row
   (the header) is exactly these columns:
   ```
   id  timestamp  block_key  lat  lon  borough  action_type  trees_count  detail  place  display_name  status  session_hash
   ```
3. **Share the Sheet** with the service account's `client_email` as an **Editor**.
4. **Copy the secrets template** and fill it in:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
   Paste the values from your JSON key and the Sheet URL into
   `.streamlit/secrets.toml` (this file is git-ignored).
5. **Restart the app.** The "Demo mode" banner disappears and submissions now persist.

`.streamlit/secrets.toml.example` contains the full template and inline instructions.

---

## ☁️ Deploying to Streamlit Community Cloud

1. Push the repo to GitHub.
2. At <https://share.streamlit.io>, create a new app pointing to **`eco_app_advanced.py`**.
3. (Optional) In **App → Settings → Secrets**, paste the same
   `[connections.gsheets]` block from your `secrets.toml` to enable community
   persistence, and share the Sheet with the service-account email.
4. Deploy. Dependencies install automatically from `requirements.txt`.

The repo already includes `.streamlit/config.toml` (theme + static serving) and a
`static/` folder with the PWA manifest and app icons, so the deployed app is
installable to a phone home screen.

---

## 📊 Data sources & methodology

| Metric | Source | Status |
|---|---|---|
| **Tree canopy** | [NYC Street Tree Census](https://data.cityofnewyork.us/Environment/2015-Street-Tree-Census-Tree-Data/uvpi-gqnh) (`uvpi-gqnh`), counted within ~300 m | **Live** |
| **Heat vulnerability** | [NYC Heat Vulnerability Index](https://data.cityofnewyork.us/Health/Heat-Vulnerability-Index-Rankings/4mhf-duep) (`4mhf-duep`), by ZIP | **Live** |
| **48h heat forecast** | [Open-Meteo](https://open-meteo.com/) (apparent temperature, hourly) | **Live** |
| **Geocoding** | [NYC GeoSearch](https://geosearch.planninglabs.nyc/) (Planning Labs), Nominatim fallback | **Live** |
| **Air quality, recycling, transit** | Borough baselines (NYC Open Data / EPA references) + coordinate-seeded micro-variation | Modeled |

**How "modeled" works.** For dimensions without a free, keyless, block-level live feed,
the app starts from a borough baseline and applies a small, *deterministic* variation
seeded from the block's coordinates (rounded to ~110 m). The same block always returns
the same numbers, while neighboring blocks differ realistically. These are clearly
badged `○ MODELED` and are directional guidance, **not survey-grade measurements**.

**Graceful degradation.** Every live API call has a short timeout and a fallback. If a
source is unreachable, the app substitutes the modeled value (re-badged) and keeps
working. You can run the entire app offline without errors.

**About the "AI" forecaster.** The Heat-Wave Forecaster is a transparent, explainable
model — it layers this block's heat-island effect (from the Heat Vulnerability Index)
and low-canopy penalty on top of the live forecast, using NWS heat-risk thresholds. It
is real and defensible. *Multi-city transfer learning is on the roadmap and is not a
trained capability in this build.*

---

## 📁 Project structure

```
nyc-eco-checker/
├── eco_app_advanced.py            # Main app: UI, layout, design system, render flow
├── eco_data.py                    # Live API clients + Heat-Wave Forecaster model
├── eco_community.py               # Gamification + community (Google Sheets, aggregation, achievements)
├── requirements.txt               # Python dependencies
├── README.md                      # This file
├── docs/
│   └── ARCHITECTURE.md            # Developer deep-dive: data flow, models, schema, extending
├── static/                        # PWA manifest + app icons (served at /static)
│   ├── manifest.json
│   ├── icon-192.png
│   └── icon-512.png
├── .streamlit/
│   ├── config.toml                # Theme + server config
│   ├── secrets.toml.example       # Template for Google Sheets credentials
│   └── static/                    # Source copies of PWA assets
├── .devcontainer/                 # GitHub Codespaces config
└── .gitignore
```

See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for how the modules fit together,
the forecaster math, the Sheets schema, and how to extend the app.

---

## ⚙️ Configuration reference

### `.streamlit/config.toml`
- **`[theme]`** — the sage / charcoal / periwinkle palette (`primaryColor = "#7c9c82"`).
- **`[server] enableStaticServing = true`** — serves the `static/` folder at `/static`
  so the PWA manifest and icons load.

### `requirements.txt`
`streamlit`, `requests`, `geopy`, `folium`, `streamlit-folium`, `reportlab`, `pillow`,
`pandas`, `plotly`, `st-gsheets-connection`, `gspread`, `google-auth`.

### Optional environment / secrets
- **Google Sheets** — `[connections.gsheets]` in `.streamlit/secrets.toml` (see
  [Community setup](#-community-features-setup-optional)).
- **`SOCRATA_APP_TOKEN`** — an optional free token that raises NYC Open Data rate
  limits. Not required; the app works without it.

---

## 🩺 Troubleshooting

| Symptom | Fix |
|---|---|
| **`ModuleNotFoundError: eco_data`** when testing | Run via `streamlit run eco_app_advanced.py` (Streamlit adds the script's folder to the path). For scripts/tests, add the repo dir to `sys.path`. |
| **All metrics show `○ MODELED`** | You're offline or the NYC Open Data / Open-Meteo APIs are unreachable. The app is working as designed — it falls back to modeled values. Re-check your connection. |
| **"Demo mode" banner on the Compete tab** | Google Sheets isn't configured. This is expected without credentials — see [Community setup](#-community-features-setup-optional). |
| **Address not found** | Try a nearby landmark or use the **Click the map** / **Pick a borough** method. GeoSearch covers NYC addresses best. |
| **"Outside the NYC data area"** | The location is outside the five boroughs; the app only models NYC. |
| **Port already in use** | Launch with `--server.port 8502` (or any free port). |
| **Slow first load of a location** | The first call to each live API isn't cached yet; results are cached (30 min – 24 h) so repeat views are instant. |

---

## 🗺️ Roadmap

Planned next ("Awareness kit" and beyond):
- **"Why AI?" explainer modal** (`st.dialog`) addressing why this beats a spreadsheet.
- **Social sharing** — X / LinkedIn share intents and a downloadable score card.
- **Chart-embedded PDF** — richer report with the forecast and radar charts inline.
- **Live air-quality** integration (AirNow / OpenAQ) to make AQI a live metric.
- **Multi-city support** — adapting the pipeline to other cities' open data.

---

## 👩‍💻 For developers

A quick orientation (full detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)):

- **`eco_app_advanced.py`** owns all UI: the CSS design system, the sidebar location
  picker, the scoring helpers, the Plotly chart builders, the PDF generator, and the
  tab render flow.
- **`eco_data.py`** owns live data: one cached client per source, a combined
  `fetch_block_realdata()` that returns a `BlockRealData` dataclass (with a
  `sources` provenance map), and the `heat_forecast()` / `forecast_chart()` model.
- **`eco_community.py`** owns engagement: the Google Sheets connection, append/read with
  caching, the points/leaderboard aggregation (pure pandas — unit-testable without
  Streamlit), and the achievement definitions.

**Key design invariant:** every downstream function (scoring, charts, PDF, exports)
reads only the `block_profile` dict. Real data is overlaid by overwriting that dict's
fields after `block_profile()` is called, so adding a new live source is a localized
change.

**Verifying changes:** use Streamlit's `AppTest` to run the app headlessly across
states (landing / a borough / a heat-vulnerable block / out-of-bounds) and assert no
exceptions. Use **item assignment** (`at.session_state["lat"] = ...`), not `.update()`,
and add the repo directory to `sys.path` first.

---

*Block-By-Block · 100% free · for a greener New York, one block at a time.* 🌿
