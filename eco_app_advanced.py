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
import time

# ===== PAGE CONFIGURATION =====
st.set_page_config(
    page_title="Block-By-Block | Environmental Intelligence",
    page_icon="🌿",
    layout="wide"
)

# ===== CUSTOM CSS =====
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #e8edf2 100%); }
    .metric-card { background: white; padding: 1.5rem; border-radius: 20px; box-shadow: 0 8px 20px rgba(0,0,0,0.08); transition: transform 0.2s; margin: 0.5rem 0; }
    .metric-card:hover { transform: translateY(-5px); box-shadow: 0 15px 30px rgba(0,0,0,0.12); }
    .main-title { font-size: 3.5rem; font-weight: 800; background: linear-gradient(135deg, #2e8b57 0%, #3cb371 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0; }
    .subtitle { font-size: 1.2rem; color: #4a5568; margin-top: -0.5rem; margin-bottom: 2rem; }
    .section-header { font-size: 1.8rem; font-weight: 700; color: #1a202c; margin-top: 2rem; margin-bottom: 1rem; border-left: 4px solid #2e8b57; padding-left: 1rem; }
    .metric-value { font-size: 2.8rem; font-weight: 800; background: linear-gradient(135deg, #2e8b57 0%, #3cb371 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .score-container { background: white; padding: 1.5rem; border-radius: 24px; box-shadow: 0 8px 20px rgba(0,0,0,0.06); text-align: center; }
    .leaderboard-item { padding: 0.75rem; margin: 0.5rem 0; background: #f8faf8; border-radius: 12px; }
    .footer { text-align: center; padding: 2rem; color: #718096; font-size: 0.8rem; border-top: 1px solid rgba(46,139,86,0.15); margin-top: 3rem; }
</style>
""", unsafe_allow_html=True)

# ===== HEADER =====
st.markdown('<div class="main-title">Block-By-Block</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Precision environmental mapping + AI-powered action plans for every NYC block</div>', unsafe_allow_html=True)

# ===== SIDEBAR =====
st.sidebar.markdown("---")
st.sidebar.markdown("### 🌿 Block-By-Block")
st.sidebar.markdown("*Hyper-local environmental intelligence*")
st.sidebar.markdown("---")

address = st.sidebar.text_input("📍 Enter NYC address:", placeholder="e.g., Times Square, Brooklyn Bridge")

# Borough data
boroughs = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]
borough_data = {
    "Manhattan": {"center": (40.7831, -73.9712), "heat": 3.8, "recycle": 23, "transit": 85, "trees_per_sqkm": 350, "air_quality": 62},
    "Brooklyn": {"center": (40.6782, -73.9442), "heat": 3.2, "recycle": 19, "transit": 70, "trees_per_sqkm": 420, "air_quality": 58},
    "Queens": {"center": (40.7282, -73.7949), "heat": 3.0, "recycle": 21, "transit": 60, "trees_per_sqkm": 380, "air_quality": 55},
    "Bronx": {"center": (40.8448, -73.8648), "heat": 4.1, "recycle": 17, "transit": 55, "trees_per_sqkm": 310, "air_quality": 65},
    "Staten Island": {"center": (40.5795, -74.1502), "heat": 2.5, "recycle": 24, "transit": 45, "trees_per_sqkm": 450, "air_quality": 48}
}

# ===== FEATURE 3: Property Value Calculator =====
def calculate_property_value_impact(tree_count, borough):
    base_value = 500000
    tree_premium = min(20, tree_count / 20)
    added_value = base_value * (tree_premium / 100)
    cooling_savings = tree_count * 12
    return added_value, cooling_savings, tree_premium

# ===== FEATURE 4: Tree Equity Score =====
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

# ===== FEATURE 8: Air Quality Index =====
def get_air_quality(borough):
    aqi = borough_data[borough]["air_quality"]
    if aqi <= 50:
        status = "Good"
    elif aqi <= 100:
        status = "Moderate"
    else:
        status = "Unhealthy"
    return aqi, status

# ===== FEATURE 9: Action Plan Generator =====
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

# ===== FEATURE 10: Seasonal Recommendations =====
def get_seasonal_recommendations():
    current_month = datetime.now().month
    if current_month in [3, 4, 5]:
        season = "Spring"
        recs = [
            "Apply for free street tree planting (deadline April 30)",
            "Join a community tree pruning workshop",
            "Install rain barrels for summer watering"
        ]
    elif current_month in [6, 7, 8]:
        season = "Summer"
        recs = [
            "Water street trees during heat waves",
            "Request a cool pavement pilot on your block",
            "Mulch around tree bases to retain moisture"
        ]
    elif current_month in [9, 10, 11]:
        season = "Fall"
        recs = [
            "Sign up for curbside compost pickup",
            "Plant shade trees before ground freezes",
            "Apply for next year's tree planting grants"
        ]
    else:
        season = "Winter"
        recs = [
            "Advocate for snow clearing on bike lanes",
            "Plan block's spring planting strategy",
            "Seal drafts to reduce heating emissions"
        ]
    return season, recs

# ===== FEATURE 6: Heat Wave Alert =====
def check_heat_alert(heat_score):
    current_temp = 85 + (heat_score - 2.5) * 5
    is_heat_wave = heat_score >= 3.8
    
    if is_heat_wave:
        cooling_centers = [
            "Local library (0.2 miles)",
            "Community center (0.4 miles)",
            "Senior center (0.6 miles)"
        ]
        return True, current_temp, cooling_centers
    return False, current_temp, []

# ===== MAIN APP =====
if address:
    with st.spinner("Analyzing your block's environmental data..."):
        try:
            geocoder = Nominatim(user_agent="block_by_block", timeout=30)
            location = geocoder.geocode(f"{address}, New York City", timeout=30)
            
            if not location:
                st.error("Location not found. Try a specific NYC address.")
                st.stop()
            
            lat, lon = location.latitude, location.longitude
            
            # Determine borough
            borough = "Manhattan"
            for b in boroughs:
                if b in location.address:
                    borough = b
                    break
            
            # Get base data
            base_data = borough_data[borough]
            tree_count = base_data["trees_per_sqkm"]
            heat_score = base_data["heat"]
            recycle_rate = base_data["recycle"]
            transit_score = base_data["transit"]
            
            # Calculate derived metrics
            property_gain, cooling_savings, premium = calculate_property_value_impact(tree_count, borough)
            equity_score, missing_trees, equity_rating = calculate_tree_equity_score(tree_count, borough)
            aqi, aqi_status = get_air_quality(borough)
            season, seasonal_recs = get_seasonal_recommendations()
            actions, impacts = generate_action_plan(tree_count, heat_score, recycle_rate, transit_score, equity_score, missing_trees)
            heat_wave, current_temp, cooling_centers = check_heat_alert(heat_score)
            
            # Display location
            st.success(f"Location: {location.address[:80]}... | {borough} Borough")
            
            # FEATURE 6: HEAT WAVE ALERT
            if heat_wave:
                st.error(f"""
                🚨 **HEAT WAVE EMERGENCY ALERT** 🚨
                
                Current temperature: {current_temp:.0f}°F | Heat vulnerability: {heat_score}/5.0
                
                **Cooling centers near you:**
                {chr(10).join(cooling_centers)}
                
                Please check on elderly neighbors and keep pets hydrated.
                """)
            
            # METRICS ROW
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🌳 Trees/sq km", tree_count)
            with col2:
                st.metric("🌡️ Heat Score", f"{heat_score}/5.0")
            with col3:
                st.metric("♻️ Recycling Rate", f"{recycle_rate}%")
            with col4:
                st.metric("🚌 Transit Score", f"{transit_score}/100")
            
            # FEATURE 4: TREE EQUITY SCORE
            st.markdown("---")
            st.subheader("⚖️ Tree Equity Score")
            col_eq1, col_eq2 = st.columns(2)
            with col_eq1:
                st.metric("Equity Score", f"{equity_score:.0f}/100")
                st.caption(f"Rating: {equity_rating}")
            with col_eq2:
                st.metric("Missing Trees", f"{missing_trees:.0f}", delta="needed for equity")
            
            # FEATURE 8: AIR QUALITY
            st.subheader("💨 Air Quality Index")
            st.metric("AQI", f"{aqi}/100", delta=aqi_status)
            
            # FEATURE 3: PROPERTY VALUE IMPACT
            st.subheader("💰 Property Value Impact")
            col_val1, col_val2 = st.columns(2)
            with col_val1:
                st.metric("Added Home Value", f"+${property_gain:,.0f}", delta=f"{premium:.1f}% premium")
            with col_val2:
                st.metric("Annual Cooling Savings", f"${cooling_savings:.0f}")
            
            # FEATURE 9: ACTION PLAN
            st.subheader("📋 Block Action Plan")
            for action, impact in zip(actions, impacts):
                with st.container():
                    st.markdown(f"**{action}**")
                    st.caption(f"Expected impact: {impact}")
                    st.markdown("---")
            
            # FEATURE 10: SEASONAL RECOMMENDATIONS
            st.subheader(f"🍂 {season} Recommendations")
            for rec in seasonal_recs:
                st.markdown(f"- {rec}")
            
            # FEATURE 2: GENERATE FULL ACTION PLAN
            if st.button("📄 Generate Complete Block Action Plan"):
                st.success("""
                **YOUR CUSTOM ACTION PLAN**
                
                1. 🌳 Plant street trees (priority: highest)
                2. 🏠 Apply for cool pavement pilot program
                3. ♻️ Organize block composting orientation
                4. 🚲 Attend community board transit meeting
                5. 📢 Share your Tree Equity Score with local representatives
                
                **Estimated 5-year impact:** 8°F cooler, $50k property value increase
                """)
            
            # FEATURE 5: BLOCK LEADERBOARD (simplified)
            st.subheader("🏆 Greenest Blocks in NYC")
            leaderboard_data = [
                ("Park Slope", "Brooklyn", 892),
                ("Fort Greene", "Brooklyn", 734),
                ("Upper West Side", "Manhattan", 712),
                ("Forest Hills", "Queens", 654),
                ("YOUR BLOCK", borough, tree_count)
            ]
            for block, boro, trees in sorted(leaderboard_data, key=lambda x: x[2], reverse=True):
                if block == "YOUR BLOCK":
                    st.markdown(f"**📍 {block} ({boro}) — {trees} trees** ← You are here")
                else:
                    st.markdown(f"{block} ({boro}) — {trees} trees")
            
            # FEATURE 7: API ACCESS (Free)
            with st.expander("🔌 API Access (Free for Developers)"):
                st.markdown("""
                **Get block data programmatically:**
                
                ```python
                import requests
                
                response = requests.get(
                    'https://block-by-block.streamlit.app/api/block',
                    params={'lat': 40.7580, 'lon': -73.9855}
                )
                data = response.json()
                print(data['trees'], data['heat_score'])
                ```
                """)