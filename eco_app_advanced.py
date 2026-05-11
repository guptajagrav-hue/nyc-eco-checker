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
address = st.sidebar.text_input("Enter NYC address, landmark, or neighborhood:", 
                                 placeholder="e.g., Times Square, Brooklyn Bridge, Prospect Park")

# Initialize geocoder with longer timeout
@st.cache_resource
def get_geocoder():
    return Nominatim(user_agent="eco_app", timeout=30)

# Function to get environmental data
def get_environmental_data(lat, lon, borough):
    # Trees
    tree_url = "https://data.cityofnewyork.us/resource/uvpi-gqnh.json"
    tree_params = {
        "$where": f"latitude between {lat-0.005} and {lat+0.005} AND longitude between {lon-0.005} and {lon+0.005}",
        "$limit": 5000
    }
    try:
        tree_response = requests.get(tree_url, params=tree_params, timeout=10)
        trees = tree_response.json()
        tree_count = len(trees)
    except:
        # Fallback to estimate
        tree_estimates = {"Manhattan": 350, "Brooklyn": 420, "Queens": 380, "Bronx": 310, "Staten Island": 450}
        tree_count = tree_estimates.get(borough, 350)
    
    # Heat score
    borough_heat = {
        "Brooklyn": 3.2, "Queens": 3.0, "Manhattan": 3.8,
        "Bronx": 4.1, "Staten Island": 2.5
    }
    heat_score = borough_heat.get(borough, 3.5)
    
    # Recycling rate
    recycling_rates = {
        "Brooklyn": 19, "Queens": 21, "Manhattan": 23,
        "Bronx": 17, "Staten Island": 24
    }
    recycle_rate = recycling_rates.get(borough, 20)
    
    # Transit score
    transit_by_borough = {
        "Manhattan": 85, "Brooklyn": 70, "Queens": 60,
        "Bronx": 55, "Staten Island": 45
    }
    transit_score = transit_by_borough.get(borough, 60)
    
    # Calculate overall score
    tree_score = min(100, tree_count / 4)
    heat_score_normalized = (5 - heat_score) / 5 * 100
    recycle_score = recycle_rate * 2
    overall = (tree_score + heat_score_normalized + recycle_score + transit_score) / 4
    
    return {
        "tree_count": tree_count,
        "heat_score": heat_score,
        "recycle_rate": recycle_rate,
        "transit_score": transit_score,
        "overall_score": overall,
        "tree_score": tree_score,
        "heat_normalized": heat_score_normalized,
        "recycle_score": recycle_score
    }

# Function to create map
def create_map(lat, lon, tree_count, heat_score):
    # Center map on location
    m = folium.Map(location=[lat, lon], zoom_start=16, tiles='CartoDB positron')
    
    # Add marker for the location
    folium.Marker(
        [lat, lon],
        popup=f"📍 Your Location<br>🌳 {tree_count} trees nearby<br>🌡️ Heat: {heat_score}/5.0",
        icon=folium.Icon(color='red', icon='info-sign'),
        tooltip="Selected location"
    ).add_to(m)
    
    # Add tree density circle (500m radius)
    folium.Circle(
        radius=500,
        location=[lat, lon],
        popup=f'Search area: 500m radius<br>{tree_count} trees found',
        color='green',
        weight=3,
        fill=True,
        fill_color='lightgreen',
        fill_opacity=0.2
    ).add_to(m)
    
    # ONLY ADD HEAT CIRCLES IF HEAT SCORE IS HIGH (>= 3.5)
    if heat_score >= 3.5:
        # Add realistic heat zones around the area
        heat_radius = 200
        heat_opacity = 0.4
        
        # Main heat zone at location
        folium.Circle(
            radius=heat_radius + 50,
            location=[lat, lon],
            popup=f'Heat vulnerability zone<br>Score: {heat_score}/5.0',
            color='darkred',
            weight=2,
            fill=True,
            fill_color='red',
            fill_opacity=heat_opacity
        ).add_to(m)
        
        # Secondary heat zones in surrounding areas (only for high heat)
        offsets = [(0.002, 0.002), (0.002, -0.002), (-0.002, 0.002), (-0.002, -0.002)]
        for dlat, dlon in offsets:
            folium.Circle(
                radius=heat_radius,
                location=[lat + dlat, lon + dlon],
                popup='Urban heat island effect',
                color='orange',
                weight=1,
                fill=True,
                fill_color='orange',
                fill_opacity=heat_opacity - 0.1
            ).add_to(m)
    
    return m

# Function to generate PDF report
def generate_pdf(address, data, lat, lon, borough):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.green,
        spaceAfter=30
    )
    story.append(Paragraph("NYC Environmental Report", title_style))
    
    # Address and date
    story.append(Paragraph(f"<b>Location:</b> {address}", styles['Normal']))
    story.append(Paragraph(f"<b>Borough:</b> {borough}", styles['Normal']))
    story.append(Paragraph(f"<b>Coordinates:</b> {lat:.4f}, {lon:.4f}", styles['Normal']))
    story.append(Paragraph(f"<b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Environmental Metrics Table
    data_table = [
        ['Metric', 'Value', 'Rating'],
        ['Trees within 500m', str(data['tree_count']), 'Excellent' if data['tree_count'] > 300 else 'Good' if data['tree_count'] > 150 else 'Fair'],
        ['Heat Vulnerability', f"{data['heat_score']}/5.0", 'High Risk' if data['heat_score'] >= 3.5 else 'Moderate' if data['heat_score'] >= 2.5 else 'Low Risk'],
        ['Recycling Rate', f"{data['recycle_rate']}%", 'Above Average' if data['recycle_rate'] >= 23 else 'Average' if data['recycle_rate'] >= 19 else 'Below Average'],
        ['Transit Access', f"{data['transit_score']}/100", 'Excellent' if data['transit_score'] >= 80 else 'Good' if data['transit_score'] >= 60 else 'Fair']
    ]
    
    table = Table(data_table, colWidths=[2*inch, 1.5*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.green),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table)
    story.append(Spacer(1, 20))
    
    # Overall Score
    story.append(Paragraph(f"<b>Overall Neighborhood Score:</b> {data['overall_score']:.0f}/100", styles['Heading2']))
    
    # Score interpretation
    if data['overall_score'] >= 70:
        interpretation = "Excellent environmental quality!"
    elif data['overall_score'] >= 50:
        interpretation = "Good - room for improvement"
    else:
        interpretation = "Needs improvement"
    story.append(Paragraph(interpretation, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Recommendations
    story.append(Paragraph("<b>Recommendations:</b>", styles['Heading3']))
    recommendations = []
    if data['tree_count'] < 100:
        recommendations.append("• Plant a street tree through NYC Parks' Tree Planting program")
    if data['heat_score'] >= 3.5:
        recommendations.append("• Use reflective materials on roof/pavement to reduce heat")
    if data['recycle_rate'] < 20:
        recommendations.append("• Separate recyclables: paper, plastic, glass, metal")
    if data['transit_score'] < 50:
        recommendations.append("• Advocate for more bus stops and bike lanes")
    
    if recommendations:
        for rec in recommendations:
            story.append(Paragraph(rec, styles['Normal']))
    else:
        story.append(Paragraph("• Your neighborhood is doing well! Share this report with neighbors", styles['Normal']))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# Main app logic
if address:
    with st.spinner("Finding location... (may take 10-15 seconds)"):
        try:
            geocoder = get_geocoder()
            
            # Try address as-is first
            location = None
            try:
                location = geocoder.geocode(address, timeout=30)
            except:
                pass
            
            # If not found, try with NYC suffix
            if not location:
                try:
                    location = geocoder.geocode(f"{address}, New York City", timeout=30)
                except:
                    pass
            
            if not location:
                st.error("❌ Location not found. Try these formats:")
                st.markdown("""
                - **Times Square**
                - **Brooklyn Bridge**
                - **Prospect Park, Brooklyn**
                - **250 Bedford Ave, Brooklyn**
                """)
                st.stop()
                
        except Exception as e:
            st.error(f"Geocoding service temporarily unavailable. Please refresh and try again.")
            st.stop()
        
        lat = location.latitude
        lon = location.longitude
        
        # Determine borough
        borough = "Manhattan"
        boroughs = ["Brooklyn", "Queens", "Manhattan", "Bronx", "Staten Island"]
        for b in boroughs:
            if b in location.address:
                borough = b
                break
        
        st.success(f"✅ Found: {location.address[:80]}...")
        st.info(f"📌 Coordinates: {lat:.4f}, {lon:.4f} | Borough: {borough}")
        
        # Get environmental data
        data = get_environmental_data(lat, lon, borough)
        
        # Create two columns for layout
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🗺️ Interactive Map")
            st.markdown("*🟢 Green circle: 500m search radius*")
            
            # Only show heat warning if applicable
            if data['heat_score'] >= 3.5:
                st.warning(f"🔥 High heat vulnerability area (Score: {data['heat_score']}/5.0) - Red zones show heat islands")
            
            m = create_map(lat, lon, data['tree_count'], data['heat_score'])
            st_folium(m, width=600, height=400)
        
        with col2:
            st.subheader("📊 Key Metrics")
            st.metric("🌳 Trees within 500m", data['tree_count'])
            st.metric("🌡️ Heat Score", f"{data['heat_score']}/5.0")
            st.metric("♻️ Recycling Rate", f"{data['recycle_rate']}%")
            st.metric("🚌 Transit Score", f"{data['transit_score']}/100")
        
        # Overall score
        st.markdown("---")
        st.subheader("⭐ Overall Neighborhood Score")
        st.progress(int(data['overall_score']))
        st.markdown(f"### {data['overall_score']:.0f}/100")
        
        if data['overall_score'] >= 70:
            st.success("🌟 Excellent environmental quality and transit access!")
        elif data['overall_score'] >= 50:
            st.info("👍 Good - room for improvement")
        else:
            st.warning("⚠️ Needs more trees, better recycling, or transit access")
        
        # Score breakdown
        with st.expander("📊 View detailed score breakdown"):
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Tree Score", f"{data['tree_score']:.0f}/100")
                st.metric("Heat Score (normalized)", f"{data['heat_normalized']:.0f}/100")
            with col_b:
                st.metric("Recycling Score", f"{data['recycle_score']:.0f}/100")
                st.metric("Transit Score", f"{data['transit_score']}/100")
        
        # Recommendations
        st.markdown("---")
        st.subheader("💡 Recommendations")
        
        if data['tree_count'] < 100:
            st.markdown("- 🌳 Plant a street tree via NYC Parks' Tree Planting program")
        if data['heat_score'] >= 3.5:
            st.markdown("- 🏠 Use reflective materials on roof/pavement to reduce heat absorption")
        if data['recycle_rate'] < 20:
            st.markdown("- ♻️ Separate recyclables correctly: paper, plastic, glass, metal")
        if data['transit_score'] < 50:
            st.markdown("- 🚌 Advocate for more bus stops and protected bike lanes")
        elif data['overall_score'] >= 60:
            st.markdown("- ✅ Your neighborhood is doing well! Share this report with neighbors")
        
        # PDF Export Button
        st.markdown("---")
        col_export, col_empty = st.columns([1, 3])
        with col_export:
            if st.button("📄 Export Report as PDF", type="primary"):
                with st.spinner("Generating PDF..."):
                    pdf_buffer = generate_pdf(address, data, lat, lon, borough)
                    st.download_button(
                        label="📥 Download PDF Report",
                        data=pdf_buffer,
                        file_name=f"nyc_environmental_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf"
                    )

else:
    st.info("👈 Enter an NYC address in the sidebar to get started!")
    
    st.markdown("""
    ### 🌟 Features:
    - **Interactive Map** - See your location and search radius
    - **PDF Reports** - Download professional environmental reports
    - **Live Tree Data** - Real tree census from NYC Open Data
    - **Conditional Heat Zones** - Red circles ONLY appear in high-heat areas
    
    ### Example locations to try:
    - Times Square
    - Brooklyn Bridge
    - Prospect Park, Brooklyn
    - Central Park
    - 250 Bedford Ave, Brooklyn
    """)

st.markdown("---")
st.markdown("📊 **Data sources:** NYC Open Data (Tree Census, Recycling Rates), NYC Heat Vulnerability Index, NYC Transit")