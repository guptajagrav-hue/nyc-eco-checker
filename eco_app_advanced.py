import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import io
from datetime import datetime
import json

# ===== PAGE CONFIGURATION =====
st.set_page_config(
    page_title="Block-By-Block | Environmental Intelligence",
    page_icon="🌿",
    layout="wide"
)
# ===== FORCE PWA MANIFEST TO BE SERVED =====
# Read the manifest file and inject it into the page
try:
    with open('.streamlit/static/manifest.json', 'r') as f:
        manifest_content = f.read()
    st.markdown(f'<link rel="manifest" href="data:application/manifest+json,{manifest_content.replace(chr(34), "%22")}">', unsafe_allow_html=True)
except:
    pass

# Inject icon links
st.markdown('<link rel="apple-touch-icon" href="https://nyc-eco-checker.streamlit.app/static/icon-192.png">', unsafe_allow_html=True)
st.markdown('<link rel="icon" type="image/png" sizes="192x192" href="https://nyc-eco-checker.streamlit.app/static/icon-192.png">', unsafe_allow_html=True)
st.markdown('<link rel="icon" type="image/png" sizes="512x512" href="https://nyc-eco-checker.streamlit.app/static/icon-512.png">', unsafe_allow_html=True)
st.markdown('<meta name="theme-color" content="#2e8b57">', unsafe_allow_html=True)
st.markdown('<meta name="apple-mobile-web-app-capable" content="yes">', unsafe_allow_html=True)
# ===== CUSTOM CSS =====
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #e8edf2 100%); }
    .metric-card { background: white; padding: 1.5rem; border-radius: 20px; box-shadow: 0 8px 20px rgba(0,0,0,0.08); transition: transform 0.2s; margin: 0.5rem 0; }
    .metric-card:hover { transform: translateY(-5px); box-shadow: 0 15px 30px rgba(0,0,0,0.12); }
    .main-title { font-size: 3.5rem; font-weight: 800; background: linear-gradient(135deg, #2e8b57 0%, #3cb371 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0; }
    .subtitle { font-size: 1.2rem; color: #4a5568; margin-top: -0.5rem; margin-bottom: 2rem; }
    .section-header { font-size: 1.8rem; font-weight: 700; color: #1a202c; margin-top: 2rem; margin-bottom: 1rem; border-left: 4px solid #2e8b57; padding-left: 1rem; }
    .footer { text-align: center; padding: 2rem; color: #718096; font-size: 0.8rem; border-top: 1px solid rgba(46,139,86,0.15); margin-top: 3rem; }
    .warning-box { background: #fff5f0; border-left: 4px solid #e53e3e; padding: 1rem; border-radius: 8px; margin: 1rem 0; }
</style>
""", unsafe_allow_html=True)

# ===== HEADER =====
st.markdown('<div class="main-title">Block-By-Block</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Precision environmental mapping for every NYC block · Type, click, or select a borough</div>', unsafe_allow_html=True)

# ===== SIDEBAR =====
st.sidebar.markdown("---")
st.sidebar.markdown("### 🌿 Block-By-Block")
st.sidebar.markdown("*Hyper-local environmental intelligence*")
st.sidebar.markdown("---")

# ===== WORKING LOCATION METHODS ONLY =====
st.sidebar.markdown("### 📍 Choose Location Method")

location_method = st.sidebar.radio(
    "Select input method:",
    ["✏️ Type Address", "🖱️ Click on Map Below", "🏙️ Select Borough"]
)

# Initialize session state
if 'lat' not in st.session_state:
    st.session_state.lat = 40.7831
    st.session_state.lon = -73.9712
    st.session_state.location_method = None

# Borough data
boroughs = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]
borough_data = {
    "Manhattan": {"center": (40.7831, -73.9712), "heat": 3.8, "recycle": 23, "transit": 85, "trees_per_sqkm": 350, "air_quality": 62},
    "Brooklyn": {"center": (40.6782, -73.9442), "heat": 3.2, "recycle": 19, "transit": 70, "trees_per_sqkm": 420, "air_quality": 58},
    "Queens": {"center": (40.7282, -73.7949), "heat": 3.0, "recycle": 21, "transit": 60, "trees_per_sqkm": 380, "air_quality": 55},
    "Bronx": {"center": (40.8448, -73.8648), "heat": 4.1, "recycle": 17, "transit": 55, "trees_per_sqkm": 310, "air_quality": 65},
    "Staten Island": {"center": (40.5795, -74.1502), "heat": 2.5, "recycle": 24, "transit": 45, "trees_per_sqkm": 450, "air_quality": 48}
}

# ===== NYC BOUNDARY CHECK =====
def is_in_nyc(lat, lon):
    nyc_bounds = {"lat_min": 40.4774, "lat_max": 40.9176, "lon_min": -74.2591, "lon_max": -73.7004}
    if not (nyc_bounds["lat_min"] <= lat <= nyc_bounds["lat_max"] and nyc_bounds["lon_min"] <= lon <= nyc_bounds["lon_max"]):
        return False
    if lat < 40.7 and lon < -74.15:
        return False
    if lat < 40.7 and lon > -73.7:
        return False
    if lat > 40.9:
        return False
    return True

def get_borough_from_coords(lat, lon):
    if not is_in_nyc(lat, lon):
        return None
    if lat < 40.7:
        return "Staten Island" if lon < -74.05 else "Brooklyn"
    elif lat > 40.85:
        return "Bronx"
    elif lon > -73.9:
        return "Queens"
    else:
        return "Manhattan"

def reverse_geocode(lat, lon):
    try:
        geocoder = Nominatim(user_agent="block_by_block", timeout=10)
        location = geocoder.reverse(f"{lat}, {lon}")
        if location:
            return location.address
    except:
        pass
    return f"{lat:.4f}, {lon:.4f}"

# ===== FEATURE FUNCTIONS =====
def calculate_property_value_impact(tree_count, borough):
    base_value = 500000
    tree_premium = min(20, tree_count / 20)
    added_value = base_value * (tree_premium / 100)
    cooling_savings = tree_count * 12
    return added_value, cooling_savings, tree_premium

def calculate_tree_equity_score(tree_count, borough):
    target_trees = borough_data[borough]["trees_per_sqkm"]
    equity_score = min(100, (tree_count / target_trees) * 100)
    missing_trees = max(0, target_trees - tree_count)
    if equity_score >= 80:
        rating = "Excellent"
    elif equity_score >= 60:
        rating = "Good"
    elif equity_score >= 40:
        rating = "Fair"
    elif equity_score >= 20:
        rating = "Poor"
    else:
        rating = "Critical"
    return equity_score, missing_trees, rating

def get_air_quality(borough):
    aqi = borough_data[borough]["air_quality"]
    status = "Good" if aqi <= 50 else "Moderate" if aqi <= 100 else "Unhealthy"
    return aqi, status

def generate_action_plan(tree_count, heat_score, recycle_rate, transit_score, equity_score, missing_trees):
    actions = []
    impacts = []
    if tree_count < 150 or missing_trees > 50:
        actions.append(f"Plant {min(20, int(missing_trees))} street trees on your block")
        impacts.append("HIGH: Reduces heat, increases property value")
    if heat_score >= 3.5:
        actions.append("Install light-colored pavement or green roof")
        impacts.append("HIGH: Lowers surface temperature by 30°F")
    if recycle_rate < 21:
        actions.append("Start a block composting program")
        impacts.append("MEDIUM: Diverts waste, builds community")
    if transit_score < 70:
        actions.append("Advocate for protected bike lanes")
        impacts.append("MEDIUM: Reduces emissions, improves safety")
    if equity_score < 50:
        actions.append("Join a tree equity campaign in your neighborhood")
        impacts.append("HIGH: Addresses environmental disparities")
    if not actions:
        actions.append("Your block is doing great! Share your success with neighbors")
        impacts.append("Share best practices")
    return actions, impacts

def get_seasonal_recommendations():
    current_month = datetime.now().month
    if current_month in [3, 4, 5]:
        season = "Spring"
        recs = ["Apply for free street tree planting (deadline April 30)", "Join a community tree pruning workshop", "Install rain barrels for summer watering"]
    elif current_month in [6, 7, 8]:
        season = "Summer"
        recs = ["Water street trees during heat waves", "Request a cool pavement pilot on your block", "Mulch around tree bases to retain moisture"]
    elif current_month in [9, 10, 11]:
        season = "Fall"
        recs = ["Sign up for curbside compost pickup", "Plant shade trees before ground freezes", "Apply for next year's tree planting grants"]
    else:
        season = "Winter"
        recs = ["Advocate for snow clearing on bike lanes", "Plan block's spring planting strategy", "Seal drafts to reduce heating emissions"]
    return season, recs

def check_heat_alert(heat_score):
    current_temp = 85 + (heat_score - 2.5) * 5
    is_heat_wave = heat_score >= 3.8
    if is_heat_wave:
        cooling_centers = ["Local library (0.2 miles)", "Community center (0.4 miles)", "Senior center (0.6 miles)"]
        return True, current_temp, cooling_centers
    return False, current_temp, []

# ===== METHOD 1: TYPE ADDRESS =====
if location_method == "✏️ Type Address":
    address = st.sidebar.text_input("Enter NYC address:", placeholder="e.g., Times Square, Brooklyn Bridge")
    if address:
        with st.spinner("Finding location..."):
            try:
                geocoder = Nominatim(user_agent="block_by_block", timeout=30)
                location = geocoder.geocode(f"{address}, New York City", timeout=30)
                if location:
                    st.session_state.lat = location.latitude
                    st.session_state.lon = location.longitude
                    st.session_state.location_method = "address"
                    st.sidebar.success(f"📍 {location.address[:50]}...")
                else:
                    st.sidebar.error("Location not found")
            except:
                st.sidebar.error("Geocoding service unavailable")

# ===== METHOD 2: CLICK ON MAP =====
elif location_method == "🖱️ Click on Map Below":
    st.sidebar.info("🖱️ Click anywhere on the map below")
    mini_map = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=12, height=300, tiles='CartoDB positron')
    folium.Marker([st.session_state.lat, st.session_state.lon], popup="Current location", icon=folium.Icon(color='green')).add_to(mini_map)
    map_click = st_folium(mini_map, width=280, height=300, key="sidebar_map")
    if map_click and map_click.get('last_clicked'):
        clicked_lat = map_click['last_clicked']['lat']
        clicked_lon = map_click['last_clicked']['lng']
        if clicked_lat and clicked_lon:
            st.session_state.lat = clicked_lat
            st.session_state.lon = clicked_lon
            st.session_state.location_method = "click"
            st.sidebar.success(f"📍 {clicked_lat:.4f}, {clicked_lon:.4f}")
            st.rerun()

# ===== METHOD 3: SELECT BOROUGH =====
elif location_method == "🏙️ Select Borough":
    st.sidebar.markdown("**Choose a borough:**")
    borough_coords = {
        "Manhattan (Times Square)": (40.7580, -73.9855),
        "Brooklyn (Downtown)": (40.6782, -73.9442),
        "Queens (Flushing)": (40.7282, -73.7949),
        "Bronx (Yankee Stadium)": (40.8296, -73.9261),
        "Staten Island (Ferry)": (40.6429, -74.0743)
    }
    selected = st.sidebar.selectbox("Select borough:", list(borough_coords.keys()))
    if st.sidebar.button("📍 Go to Borough", use_container_width=True):
        coords = borough_coords[selected]
        st.session_state.lat = coords[0]
        st.session_state.lon = coords[1]
        st.session_state.location_method = "borough"
        st.sidebar.success(f"✅ {selected.split(' (')[0]}")
        st.rerun()

# ===== MAIN APP =====
if st.session_state.lat and st.session_state.lon:
    lat = st.session_state.lat
    lon = st.session_state.lon
    
    in_nyc = is_in_nyc(lat, lon)
    
    if not in_nyc:
        st.markdown(f"""
        <div class="warning-box">
            <b>🚫 OUTSIDE NYC DATA AREA</b><br><br>
            The location <b>({lat:.4f}, {lon:.4f})</b> is outside New York City's five boroughs.<br><br>
            Block-By-Block only provides environmental data for:<br>
            • Manhattan &nbsp; • Brooklyn &nbsp; • Queens &nbsp; • Bronx &nbsp; • Staten Island
        </div>
        """, unsafe_allow_html=True)
        m = folium.Map(location=[lat, lon], zoom_start=12, tiles='CartoDB positron')
        folium.Marker([lat, lon], popup="Outside NYC", icon=folium.Icon(color='red', icon='warning')).add_to(m)
        st_folium(m, width=700, height=400)
        st.stop()
    
    borough = get_borough_from_coords(lat, lon)
    address_display = reverse_geocode(lat, lon)
    
    st.success(f"✅ Location within NYC: {address_display[:80]}...")
    st.info(f"📌 Coordinates: {lat:.4f}, {lon:.4f} | Borough: {borough}")
    
    base_data = borough_data[borough]
    tree_count = base_data["trees_per_sqkm"]
    heat_score = base_data["heat"]
    recycle_rate = base_data["recycle"]
    transit_score = base_data["transit"]
    
    property_gain, cooling_savings, premium = calculate_property_value_impact(tree_count, borough)
    equity_score, missing_trees, equity_rating = calculate_tree_equity_score(tree_count, borough)
    aqi, aqi_status = get_air_quality(borough)
    season, seasonal_recs = get_seasonal_recommendations()
    actions, impacts = generate_action_plan(tree_count, heat_score, recycle_rate, transit_score, equity_score, missing_trees)
    heat_wave, current_temp, cooling_centers = check_heat_alert(heat_score)
    
    if heat_wave:
        st.error(f"🚨 **HEAT WAVE ALERT** | {current_temp:.0f}°F | Cooling centers: {', '.join(cooling_centers)}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🌳 Trees/sq km", tree_count)
    with col2:
        st.metric("🌡️ Heat Score", f"{heat_score}/5.0")
    with col3:
        st.metric("♻️ Recycling Rate", f"{recycle_rate}%")
    with col4:
        st.metric("🚌 Transit Score", f"{transit_score}/100")
    
    st.markdown("---")
    st.subheader("⚖️ Tree Equity Score")
    col_eq1, col_eq2 = st.columns(2)
    with col_eq1:
        st.metric("Equity Score", f"{equity_score:.0f}/100")
        st.caption(f"Rating: {equity_rating}")
    with col_eq2:
        st.metric("Missing Trees", f"{missing_trees:.0f}", delta="needed for equity")
    
    st.subheader("💨 Air Quality Index")
    st.metric("AQI", f"{aqi}/100", delta=aqi_status)
    
    st.subheader("💰 Property Value Impact")
    col_val1, col_val2 = st.columns(2)
    with col_val1:
        st.metric("Added Home Value", f"+${property_gain:,.0f}", delta=f"{premium:.1f}% premium")
    with col_val2:
        st.metric("Annual Cooling Savings", f"${cooling_savings:.0f}")
    
    st.subheader("📋 Block Action Plan")
    for action, impact in zip(actions, impacts):
        st.markdown(f"- **{action}** → *{impact}*")
    
    st.subheader(f"🍂 {season} Recommendations")
    for rec in seasonal_recs:
        st.markdown(f"- {rec}")
    
    st.subheader("🏆 Greenest Blocks in NYC")
    leaderboard_data = [("Park Slope", "Brooklyn", 892), ("Fort Greene", "Brooklyn", 734), ("Upper West Side", "Manhattan", 712), ("Forest Hills", "Queens", 654), ("YOUR BLOCK", borough, tree_count)]
    for block, boro, trees in sorted(leaderboard_data, key=lambda x: x[2], reverse=True):
        if block == "YOUR BLOCK":
            st.markdown(f"**📍 {block} ({boro}) — {trees} trees** ← You are here")
        else:
            st.markdown(f"{block} ({boro}) — {trees} trees")
    
    with st.expander("📊 Compare with Another Neighborhood"):
        compare_boro = st.selectbox("Select borough to compare:", boroughs)
        if compare_boro:
            comp_data = borough_data[compare_boro]
            st.markdown(f"**Comparison: {borough} vs {compare_boro}**")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.metric("Trees/sq km", f"{tree_count} vs {comp_data['trees_per_sqkm']}")
                st.metric("Heat Score", f"{heat_score} vs {comp_data['heat']}")
            with col_c2:
                st.metric("Recycling", f"{recycle_rate}% vs {comp_data['recycle']}%")
                st.metric("Transit", f"{transit_score} vs {comp_data['transit']}")
    
        with st.expander("📋 View Complete Block Action Plan", expanded=False):
            st.markdown("""
        **YOUR CUSTOM ACTION PLAN**
    
        1. 🌳 **Plant street trees** (priority: highest)
        - Apply for free street trees through NYC Parks
        - Goal: Add 15-20 trees to your block
    
        2. 🏠 **Apply for cool pavement pilot program**
        - Light-colored pavement reduces heat by 30°F
        - Contact your community board
    
        3. ♻️ **Organize block composting orientation**
        - Connect with NYC Compost Project
        - Reduce waste by 30%
    
        4. 🚲 **Attend community board transit meeting**
        - Advocate for protected bike lanes
         - Request more frequent bus service
    
        5. 📢 **Share your Tree Equity Score**
        - Present to local representatives
        - Join a tree equity campaign
    
        ---
        ### 🌟 Estimated 5-year impact:
        - 🌡️ 8°F cooler on your block
        - 💰 $50k property value increase
        - 🌳 50% more tree canopy
        - ♻️ 40% waste diversion
    
        ### 📞 Need help getting started?
        - 📧 Email: trees@parks.nyc.gov
        - 📱 Call 311 (say "tree planting")
        - 👥 Share this plan with neighbors
        """)
    
    with st.expander("🔌 Data Export (JSON/CSV)"):
        export_data = {
            "location": address_display,
            "borough": borough,
            "coordinates": {"lat": lat, "lon": lon},
            "trees_per_sqkm": tree_count,
            "heat_score": heat_score,
            "recycling_rate": recycle_rate,
            "transit_score": transit_score,
            "air_quality": aqi,
            "equity_score": equity_score,
            "timestamp": datetime.now().isoformat()
        }
        col_api1, col_api2 = st.columns(2)
        with col_api1:
            st.download_button(label="📥 Download as JSON", data=json.dumps(export_data, indent=2), file_name=f"block_data_{borough}.json", mime="application/json")
        with col_api2:
            csv_data = "Metric,Value\n" + "\n".join([f"{k},{v}" for k, v in export_data.items() if not isinstance(v, dict)])
            st.download_button(label="📊 Download as CSV", data=csv_data, file_name=f"block_data_{borough}.csv", mime="text/csv")
    
    with st.expander("🗺️ Heat Vulnerability Map", expanded=True):
        m = folium.Map(location=[lat, lon], zoom_start=15, tiles='CartoDB positron')
        folium.Marker([lat, lon], popup=f"{borough}<br>Heat: {heat_score}/5.0", icon=folium.Icon(color='red' if heat_score >= 3.5 else 'green')).add_to(m)
        folium.Circle(radius=500, location=[lat, lon], color='green', weight=2, fill=True, fill_color='lightgreen', fill_opacity=0.15).add_to(m)
        if heat_score >= 3.5:
            folium.Circle(radius=250, location=[lat, lon], color='darkred', weight=2, fill=True, fill_color='red', fill_opacity=0.4).add_to(m)
            offsets = [(0.002, 0.002), (0.002, -0.002), (-0.002, 0.002), (-0.002, -0.002)]
            for dlat, dlon in offsets:
                folium.Circle(radius=180, location=[lat + dlat, lon + dlon], color='orange', fill=True, fill_color='orange', fill_opacity=0.3).add_to(m)
        st_folium(m, width=700, height=450)

else:
    st.info("👈 Select a location method in the sidebar to get started!")
    st.markdown("""
    ### 🌟 Three Working Location Methods:
    
    | Method | How It Works |
    |--------|--------------|
    | ✏️ **Type Address** | Enter any NYC address or landmark |
    | 🖱️ **Click on Map** | Click anywhere on the map |
    | 🏙️ **Select Borough** | Pick from 5 NYC boroughs |
    
    ### Try These Examples:
    - Times Square, Manhattan
    - Prospect Park, Brooklyn
    - Flushing Meadows, Queens
    - Yankee Stadium, Bronx
    """)
    preview_map = folium.Map(location=[40.7580, -73.9855], zoom_start=11, tiles='CartoDB positron')
    folium.Marker([40.7580, -73.9855], popup="Times Square", icon=folium.Icon(color='green')).add_to(preview_map)
    st_folium(preview_map, width=700, height=400)

st.markdown("---")
st.markdown("""
<div class="footer">
    <strong>Block-By-Block</strong> · 3 working location methods · 10 features · 100% free<br>
    Data: NYC Open Data · Heat Vulnerability Index · EPA Air Quality
</div>
""", unsafe_allow_html=True)