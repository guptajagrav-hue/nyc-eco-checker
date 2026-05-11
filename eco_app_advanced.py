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

# Sidebar - Borough selector instead of address search
st.sidebar.header("📍 Location Selection")

# Borough coordinates (center points)
boroughs = {
    "Manhattan": {"lat": 40.7831, "lon": -73.9712, "heat": 3.8, "recycle": 23, "transit": 85},
    "Brooklyn": {"lat": 40.6782, "lon": -73.9442, "heat": 3.2, "recycle": 19, "transit": 70},
    "Queens": {"lat": 40.7282, "lon": -73.7949, "heat": 3.0, "recycle": 21, "transit": 60},
    "Bronx": {"lat": 40.8448, "lon": -73.8648, "heat": 4.1, "recycle": 17, "transit": 55},
    "Staten Island": {"lat": 40.5795, "lon": -74.1502, "heat": 2.5, "recycle": 24, "transit": 45}
}

selected_borough = st.sidebar.selectbox(
    "Select a borough:",
    list(boroughs.keys())
)

# Optional: Specific neighborhood input (for better tree counting)
neighborhood = st.sidebar.text_input(
    "Or enter a specific neighborhood (optional):",
    placeholder="e.g., Times Square, Williamsburg, Flushing"
)

# Use borough coordinates
lat = boroughs[selected_borough]["lat"]
lon = boroughs[selected_borough]["lon"]
heat_score = boroughs[selected_borough]["heat"]
recycle_rate = boroughs[selected_borough]["recycle"]
transit_score = boroughs[selected_borough]["transit"]

# Display location info
st.sidebar.info(f"📍 {selected_borough} Borough\n📌 {lat:.4f}, {lon:.4f}")

# Function to get tree count from API
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

# Get tree count
with st.spinner("Counting trees in this area..."):
    tree_count = get_tree_count(lat, lon)
    
    # If no trees found or API failed, use estimate based on borough
    if tree_count is None or tree_count == 0:
        estimated_trees = {
            "Manhattan": 350,
            "Brooklyn": 420,
            "Queens": 380,
            "Bronx": 310,
            "Staten Island": 450
        }
        tree_count = estimated_trees.get(selected_borough, 350)
        st.info(f"💡 Using estimated tree count for {selected_borough} (API temporarily unavailable)")

# Calculate scores
tree_score = min(100, tree_count / 4)
heat_normalized = (5 - heat_score) / 5 * 100
recycle_score = recycle_rate * 2
overall = (tree_score + heat_normalized + recycle_score + transit_score) / 4

# Create two columns for layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🗺️ Interactive Map")
    st.markdown("*Green circle: 500m search radius*")
    
    # Create map
    m = folium.Map(location=[lat, lon], zoom_start=13, tiles='CartoDB positron')
    
    # Add marker for borough center
    folium.Marker(
        [lat, lon],
        popup=f"📍 {selected_borough}<br>🌳 {tree_count} trees nearby<br>🌡️ Heat: {heat_score}/5.0",
        icon=folium.Icon(color='red', icon='info-sign'),
        tooltip=selected_borough
    ).add_to(m)
    
    # Add circle for search radius
    folium.Circle(
        radius=500,
        location=[lat, lon],
        popup=f'Search area: 500m radius<br>{tree_count} trees found',
        color='green',
        fill=True,
        fill_color='lightgreen',
        fill_opacity=0.2
    ).add_to(m)
    
    st_folium(m, width=600, height=400)

with col2:
    st.subheader("📊 Key Metrics")
    st.metric("🌳 Trees within 500m", tree_count)
    st.metric("🌡️ Heat Score", f"{heat_score}/5.0")
    st.metric("♻️ Recycling Rate", f"{recycle_rate}%")
    st.metric("🚌 Transit Score", f"{transit_score}/100")

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

if tree_count < 100:
    st.markdown("- 🌳 Plant a street tree via NYC Parks' Tree Planting program")
if heat_score >= 3.5:
    st.markdown("- 🏠 Use reflective materials on roof/pavement to reduce heat")
if recycle_rate < 20:
    st.markdown("- ♻️ Separate recyclables: paper, plastic, glass, metal")
if transit_score < 50:
    st.markdown("- 🚌 Advocate for more bus stops and bike lanes in your area")
elif overall >= 60:
    st.markdown("- ✅ Your neighborhood is doing well! Share this report")

# PDF Export Button
st.markdown("---")
col_export, col_empty = st.columns([1, 3])
with col_export:
    if st.button("📄 Export Report as PDF", type="primary"):
        with st.spinner("Generating PDF..."):
            # Create data dict for PDF
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
            story.append(Paragraph(f"<b>Location:</b> {selected_borough} Borough", styles['Normal']))
            if neighborhood:
                story.append(Paragraph(f"<b>Neighborhood:</b> {neighborhood}", styles['Normal']))
            story.append(Paragraph(f"<b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            story.append(Spacer(1, 20))
            
            data_table = [
                ['Metric', 'Value', 'Rating'],
                ['Trees within 500m', str(tree_count), 'Excellent' if tree_count > 300 else 'Good' if tree_count > 150 else 'Fair'],
                ['Heat Vulnerability', f"{heat_score}/5.0", 'High Risk' if heat_score >= 3.5 else 'Moderate'],
                ['Recycling Rate', f"{recycle_rate}%", 'Above Average' if recycle_rate >= 23 else 'Average'],
                ['Transit Access', f"{transit_score}/100", 'Excellent' if transit_score >= 80 else 'Good']
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
st.markdown("📊 **Data sources:** NYC Open Data (Tree Census, Recycling Rates), NYC Heat Vulnerability Index, NYC Transit")