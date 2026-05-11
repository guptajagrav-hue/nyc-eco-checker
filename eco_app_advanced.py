import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import io
from datetime import datetime
import time
import json

# Page configuration
st.set_page_config(
    page_title="NYC Environmental Checker",
    page_icon="🌍",
    layout="wide"
)

# Title
st.title("🌍 NYC Environmental Checker")
st.markdown("Check trees, heat risk, recycling, and transit for any NYC location")
st.markdown("---")

# Sidebar
st.sidebar.header("📍 Location Search")

# Option 1: Borough dropdown (always works)
st.sidebar.markdown("### Quick Select:")
selected_borough = st.sidebar.selectbox(
    "Or pick a borough:",
    ["-- Use address search below --", "Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]
)

# Option 2: Address search
st.sidebar.markdown("### Or Search Any Address:")
address = st.sidebar.text_input(
    "Enter NYC address or landmark:",
    placeholder="e.g., Brooklyn Bridge, Times Square, 250 Bedford Ave"
)

# Borough coordinates and data
borough_data = {
    "Manhattan": {"lat": 40.7831, "lon": -73.9712, "heat": 3.8, "recycle": 23, "transit": 85, "tree_estimate": 350},
    "Brooklyn": {"lat": 40.6782, "lon": -73.9442, "heat": 3.2, "recycle": 19, "transit": 70, "tree_estimate": 420},
    "Queens": {"lat": 40.7282, "lon": -73.7949, "heat": 3.0, "recycle": 21, "transit": 60, "tree_estimate": 380},
    "Bronx": {"lat": 40.8448, "lon": -73.8648, "heat": 4.1, "recycle": 17, "transit": 55, "tree_estimate": 310},
    "Staten Island": {"lat": 40.5795, "lon": -74.1502, "heat": 2.5, "recycle": 24, "transit": 45, "tree_estimate": 450}
}

# Manual coordinate override for known landmarks (no API call)
landmark_coords = {
    "brooklyn bridge": (40.7061, -73.9969, "Brooklyn"),
    "times square": (40.7580, -73.9855, "Manhattan"),
    "central park": (40.7829, -73.9654, "Manhattan"),
    "prospect park": (40.6602, -73.9688, "Brooklyn"),
    "coney island": (40.5749, -73.9859, "Brooklyn"),
    "flushing meadows": (40.7459, -73.8454, "Queens"),
    "yankee stadium": (40.8296, -73.9261, "Bronx"),
    "staten island ferry": (40.6429, -74.0743, "Staten Island")
}

# Determine location
lat = None
lon = None
heat_score = None
recycle_rate = None
transit_score = None
borough = None
location_source = ""

# Check if borough selected
if selected_borough != "-- Use address search below --":
    borough = selected_borough
    lat = borough_data[borough]["lat"]
    lon = borough_data[borough]["lon"]
    heat_score = borough_data[borough]["heat"]
    recycle_rate = borough_data[borough]["recycle"]
    transit_score = borough_data[borough]["transit"]
    location_source = f"{borough} Borough (center)"

# Check address search
elif address:
    address_lower = address.lower().strip()
    
    # Check if it's a known landmark (no API call needed)
    found = False
    for landmark, (lati, long, boro) in landmark_coords.items():
        if landmark in address_lower:
            lat = lati
            lon = long
            borough = boro
            heat_score = borough_data[boro]["heat"]
            recycle_rate = borough_data[boro]["recycle"]
            transit_score = borough_data[boro]["transit"]
            location_source = f"{address} (landmark)"
            found = True
            break
    
    # If not a known landmark, try to approximate from address
    if not found:
        # Simple keyword matching for common places
        if "brooklyn" in address_lower:
            borough = "Brooklyn"
        elif "queens" in address_lower:
            borough = "Queens"
        elif "bronx" in address_lower:
            borough = "Bronx"
        elif "staten island" in address_lower:
            borough = "Staten Island"
        else:
            borough = "Manhattan"  # Default
        
        # Use borough center
        lat = borough_data[borough]["lat"]
        lon = borough_data[borough]["lon"]
        heat_score = borough_data[borough]["heat"]
        recycle_rate = borough_data[borough]["recycle"]
        transit_score = borough_data[borough]["transit"]
        location_source = f"{borough} Borough (approximated from '{address}')"
        st.info(f"📍 Approximating '{address}' to {borough} Borough center")

# If no input, show welcome
if lat is None:
    st.info("👈 Select a borough OR enter an address in the sidebar to get started!")
    
    st.markdown("""
    ### 🌟 Features:
    - **Interactive Map** - See your location with heat zones
    - **PDF Reports** - Download environmental reports
    - **Real-time Tree Data** - Live from NYC Open Data
    - **Address Search** - Try "Brooklyn Bridge", "Times Square", etc.
    
    ### Try these examples:
    - Brooklyn Bridge
    - Times Square
    - Central Park
    - Prospect Park
    - Or pick a borough from the dropdown
    """)
    st.stop()

# Display location info
st.success(f"✅ Location: {location_source}")
st.info(f"📌 Coordinates: {lat:.4f}, {lon:.4f}")

# Get tree count
def get_tree_count(lat, lon):
    tree_url = "https://data.cityofnewyork.us/resource/uvpi-gqnh.json"
    tree_params = {
        "$where": f"latitude between {lat-0.005} and {lat+0.005} AND longitude between {lon-0.005} and {lon+0.005}",
        "$limit": 5000
    }
    try:
        tree_response = requests.get(tree_url, params=tree_params, timeout=10)
        trees = tree_response.json()
        return len(trees)
    except:
        return None

with st.spinner("Counting trees in this area..."):
    tree_count = get_tree_count(lat, lon)
    
    if tree_count is None or tree_count == 0:
        tree_count = borough_data[borough]["tree_estimate"]
        st.info(f"💡 Using estimated tree count for {borough} (approximately {tree_count} trees per sq km)")

# Calculate scores
tree_score = min(100, tree_count / 4)
heat_normalized = (5 - heat_score) / 5 * 100
recycle_score = recycle_rate * 2
overall = (tree_score + heat_normalized + recycle_score + transit_score) / 4

# Create map with heat circles
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🗺️ Interactive Map")
    st.markdown("*🟢 Green circle: 500m search radius | 🔴 Red circles: Heat vulnerability zones*")
    
    # Create map
    m = folium.Map(location=[lat, lon], zoom_start=14, tiles='CartoDB positron')
    
    # Add marker for location
    folium.Marker(
        [lat, lon],
        popup=f"📍 {location_source}<br>🌳 {tree_count} trees<br>🌡️ Heat: {heat_score}/5.0",
        icon=folium.Icon(color='red', icon='info-sign'),
        tooltip="Selected location"
    ).add_to(m)
    
    # Add tree search circle (green)
    folium.Circle(
        radius=500,
        location=[lat, lon],
        popup=f'Trees within 500m: {tree_count}',
        color='green',
        weight=3,
        fill=True,
        fill_color='lightgreen',
        fill_opacity=0.3
    ).add_to(m)
    
    # ADD HEAT CIRCLES - Fixed version!
    if heat_score >= 3.0:
        # Create a grid of heat circles around the location
        offsets = [
            (0.003, 0.003), (0.003, -0.003), (-0.003, 0.003), (-0.003, -0.003),
            (0.005, 0), (-0.005, 0), (0, 0.005), (0, -0.005)
        ]
        
        for i, (dlat, dlon) in enumerate(offsets):
            circle_color = 'darkred' if heat_score >= 3.8 else 'red' if heat_score >= 3.0 else 'orange'
            circle_radius = 150 if heat_score >= 3.8 else 120
            
            folium.Circle(
                radius=circle_radius,
                location=[lat + dlat, lon + dlon],
                popup=f'Heat zone {i+1}<br>Temperature risk: {"High" if heat_score >= 3.8 else "Moderate"}',
                color=circle_color,
                weight=2,
                fill=True,
                fill_color=circle_color,
                fill_opacity=0.4
            ).add_to(m)
        
        # Add a heat legend
        legend_html = '''
        <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000; background-color: white; padding: 10px; border-radius: 5px; border: 1px solid grey;">
        <b>🌡️ Heat Risk</b><br>
        <span style="color: darkred;">●</span> High (3.8-4.1)<br>
        <span style="color: red;">●</span> Moderate (3.0-3.8)<br>
        <span style="color: orange;">●</span> Lower (2.5-3.0)
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
    
    st_folium(m, width=600, height=450)

with col2:
    st.subheader("📊 Key Metrics")
    st.metric("🌳 Trees within 500m", tree_count)
    st.metric("🌡️ Heat Score", f"{heat_score}/5.0", 
              delta="High risk" if heat_score >= 3.5 else "Moderate" if heat_score >= 2.5 else "Low")
    st.metric("♻️ Recycling Rate", f"{recycle_rate}%", 
              delta="Above avg" if recycle_rate >= 23 else "Below avg" if recycle_rate < 19 else "Average")
    st.metric("🚌 Transit Score", f"{transit_score}/100",
              delta="Excellent" if transit_score >= 80 else "Good" if transit_score >= 60 else "Fair")

# Overall score
st.markdown("---")
st.subheader("⭐ Overall Neighborhood Score")
st.progress(int(overall))
st.markdown(f"### {overall:.0f}/100")

if overall >= 70:
    st.success("🌟 Excellent environmental quality and transit access!")
elif overall >= 50:
    st.info("👍 Good - room for improvement")
else:
    st.warning("⚠️ Needs more trees, better recycling, or transit access")

# Score breakdown
with st.expander("📊 View detailed score breakdown"):
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("Tree Score", f"{tree_score:.0f}/100")
        st.metric("Heat Score (normalized)", f"{heat_normalized:.0f}/100")
    with col_b:
        st.metric("Recycling Score", f"{recycle_score:.0f}/100")
        st.metric("Transit Score", f"{transit_score}/100")

# Recommendations
st.markdown("---")
st.subheader("💡 Recommendations")

if tree_count < 150:
    st.markdown("- 🌳 Plant a street tree or support local tree planting initiatives")
if heat_score >= 3.5:
    st.markdown("- 🏠 Use light-colored roofs and pavement to reduce heat absorption")
if recycle_rate < 20:
    st.markdown("- ♻️ Separate recyclables correctly: paper, plastic, glass, metal")
if transit_score < 60:
    st.markdown("- 🚌 Advocate for more bus stops and protected bike lanes")
elif overall >= 60:
    st.markdown("- ✅ Your neighborhood is doing well! Consider sharing this report with neighbors")

# PDF Export
st.markdown("---")
col_export, col_empty = st.columns([1, 3])
with col_export:
    if st.button("📄 Export Report as PDF", type="primary"):
        with st.spinner("Generating PDF..."):
            pdf_data = {
                "tree_count": tree_count,
                "heat_score": heat_score,
                "recycle_rate": recycle_rate,
                "transit_score": transit_score,
                "overall_score": overall
            }
            
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.green, spaceAfter=30)
            story.append(Paragraph("NYC Environmental Report", title_style))
            story.append(Paragraph(f"<b>Location:</b> {location_source}", styles['Normal']))
            story.append(Paragraph(f"<b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            story.append(Spacer(1, 20))
            
            data_table = [
                ['Metric', 'Value', 'Rating'],
                ['Trees within 500m', str(tree_count), 'Excellent' if tree_count > 300 else 'Good' if tree_count > 150 else 'Fair'],
                ['Heat Vulnerability', f"{heat_score}/5.0", 'High Risk' if heat_score >= 3.5 else 'Moderate' if heat_score >= 2.5 else 'Low'],
                ['Recycling Rate', f"{recycle_rate}%", 'Above Average' if recycle_rate >= 23 else 'Average' if recycle_rate >= 19 else 'Below Average'],
                ['Transit Access', f"{transit_score}/100", 'Excellent' if transit_score >= 80 else 'Good' if transit_score >= 60 else 'Fair']
            ]
            
            table = Table(data_table, colWidths=[2*inch, 1.5*inch, 2*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.green),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
            story.append(Spacer(1, 20))
            story.append(Paragraph(f"<b>Overall Neighborhood Score:</b> {overall:.0f}/100", styles['Heading2']))
            
            doc.build(story)
            buffer.seek(0)
            
            st.download_button(
                label="📥 Download PDF Report",
                data=buffer,
                file_name=f"nyc_environmental_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf"
            )

st.markdown("---")
st.markdown("📊 **Data sources:** NYC Open Data (Tree Census), NYC Heat Vulnerability Index, NYC Recycling Rates, NYC Transit")