import os
import streamlit as st
import datetime
import numpy as np
from recommender import FarmIQRecommender
from report_gen import generate_report_pdf
from dealers import get_dealers_by_county
from database import save_recommendation, get_all_records, get_stats

# Set page config for mobile-friendly responsive layout
st.set_page_config(
    page_title="FarmIQ Kenya",
    page_icon="平衡",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Initialize Recommender
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "kenya_county_soils.csv")

@st.cache_resource
def load_farmiq_engine():
    try:
        return FarmIQRecommender(DATA_PATH)
    except FileNotFoundError:
        st.error(f"Soil database not found at {DATA_PATH}.")
        st.stop()

engine = load_farmiq_engine()

# --- Custom Styling for Premium Look ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
    .hero-card { background: linear-gradient(135deg, #16a34a, #15803d); color: white; padding: 2rem; border-radius: 16px; text-align: center; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); margin-bottom: 2rem; }
    .hero-card h1 { color: white; margin: 0; font-weight: 800; }
    .advice-card { background: white; padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem; border-left: 5px solid #16a34a; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    .data-pill { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.875rem; font-weight: 600; margin: 0.25rem; }
    .pill-bad { background: #fee2e2; color: #b91c1c; }
    .pill-good { background: #dcfce3; color: #15803d; }
    
    /* Aggressively hide all Streamlit elements for a professional look */
    [data-testid="stHeader"] { display: none !important; }
    [data-testid="stAppDeployButton"] { display: none !important; }
    footer { visibility: hidden !important; }
    #MainMenu { visibility: hidden !important; }
    header { display: none !important; }
    
    /* Target the 'Manage app' button and bottom toolbar badges specifically */
    [data-testid="stStatusWidget"], [data-testid="stConnectionStatus"], .viewerBadge_v1 { display: none !important; }
    .stAppDeployButton { display: none !important; }
    button[data-testid="stBaseButton-secondary"] { display: none !important; }
    div[class*="viewerBadge"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# --- Geolocation Helper (Query Params) ---
qp = st.query_params
try:
    q_lat = float(qp.get("lat", 0.0))
    q_lon = float(qp.get("lon", 0.0))
except (ValueError, TypeError):
    q_lat, q_lon = 0.0, 0.0

# --- Language Mapping ---
LANGS = {
    "English": {
        "title": "Farm Profile", "county": "Where is your farm?", "crop": "What are you planting?", "fert": "What fertilizer do you usually use?",
        "acres": "Farm size (Acres)", "button": "Get Precision Advice", "report_title": "Your Insight Report",
        "mapping_source": "Precision Mapping for", "budget_title": "Budget Estimate", "total_cost": "Total Cost",
        "advice_title": "Actionable Advice", "share": "Share WhatsApp", "download_pdf": "Download PDF",
        "dealers_title": "🛍️ Suppliers Nearby", "directions": "Directions", "sms_button": "SMS Fallback",
        "status": {"low": "Low", "optimal": "Optimal", "acidic": "Acidic", "good": "Healthy"}
    },
    "Kiswahili": {
        "title": "Maelezo ya Shamba", "county": "Zao gani?", "crop": "Unapanda zao gani?", "fert": "Mbolea ya kawaida?",
        "acres": "Ekari", "button": "Pata Ushauri", "report_title": "Ripoti ya Shamba",
        "mapping_source": "Ramani ya", "budget_title": "Gharama", "total_cost": "Gharama Jumla",
        "advice_title": "Ushauri", "share": "Shiriki WhatsApp", "download_pdf": "Pakua PDF",
        "dealers_title": "🛍️ Wauzaji", "directions": "Maelekezo", "sms_button": "SMS",
        "status": {"low": "Chini", "optimal": "Vizuri", "acidic": "Asidi", "good": "Sawa"}
    }
}

# --- Main App ---
lang_col1, lang_col2 = st.columns([4, 1])
with lang_col2:
    lang_choice = st.radio("Lugha", ["English", "Kiswahili"], horizontal=True, label_visibility="collapsed")
t = LANGS[lang_choice]

with st.sidebar:
    st.markdown("### 🏛️ B2B Access")
    access_code = st.text_input("Officer Access Code", type="password")
    is_officer = (access_code == "OFFICER2026")

if is_officer:
    tab_farmer, tab_officer = st.tabs(["🌱 Farmer Advice", "📊 Extension Dashboard"])
else:
    tab_farmer = st.container()

with tab_farmer:
    st.markdown(f'<div class="hero-card"><h1>🌱 FarmIQ</h1><p>National Precision Agriculture Platform</p></div>', unsafe_allow_html=True)
    st.markdown(f"### 📍 {t['title']}")

    # --- PHASE 21: NATIONAL NEUTRALITY UI ---
    col_mode1, col_mode2 = st.columns(2)
    with col_mode1:
        loc_mode = st.radio("Location Mode", ["GPS Precision (30m)", "County Average"], horizontal=True)
    with col_mode2:
        lab_mode = st.toggle("🧪 Add My Soil Test Results (Optional)", help="Enable if you have a recent laboratory report.")

    lat, lon, selected_county = None, None, None

    # Dynamic Insights Collection
    INSIGHTS = {
        "Nakuru": "💡 **Local Variation**: Naivasha soil is often more acidic than Nakuru Town. Compare -0.717, 36.435 with -0.303, 36.080.",
        "Kakamega": "💡 **Western Insight**: High rainfall causes phosphorus fixation here. Try -0.28, 34.75 for town-specific data.",
        "Mombasa": "💡 **Coastal Precision**: Salinity varies within meters of the shore. Use GPS for exact shamba data.",
        "Nairobi": "💡 **Urban Variation**: Peri-urban soils shift rapidly. Map your shamba precisely.",
        "Kiambu": "💡 **Topography Alert**: pH levels change with elevation on hillsides. Use 30m precision.",
        "Uasin Gishu": "💡 **Grain Basket**: Intensive cereal farming creates nutrient hotspots. GPS mapping identifies them."
    }

    if loc_mode == "GPS Precision (30m)":
        # JavaScript for Dynamic Geolocation (Plan C: Robust Reload)
        st.markdown("""
            <script>
            function getLocation() {
                const btn = document.getElementById("loc-btn");
                if (btn) {
                    btn.innerHTML = "⏳ Scanning Satellites...";
                    btn.style.opacity = "0.7";
                }
                
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(function(position) {
                        const lat = position.coords.latitude;
                        const lon = position.coords.longitude;
                        
                        alert("📍 Location Detected! Clicking OK will reload your farm profile with high-precision data.");
                        
                        // Robust redirect: Tries to update query params manually
                        const baseUrl = window.location.origin + window.location.pathname;
                        const newUrl = baseUrl + "?lat=" + lat + "&lon=" + lon;
                        window.location.assign(newUrl);
                    }, function(error) {
                        if (btn) btn.innerHTML = "📍 Use My Current Location";
                        let msg = "Location error: " + error.message;
                        if (error.code === 1) msg = "Permission Denied. Please enable Location/GPS in your browser settings.";
                        alert(msg);
                    }, {
                        enableHighAccuracy: true,
                        timeout: 10000,
                        maximumAge: 0
                    });
                } else {
                    alert("Geolocation is not supported by this browser.");
                }
            }
            </script>
            <button id="loc-btn" onclick="getLocation()" style="
                background: linear-gradient(135deg, #e74c3c, #c0392b); color:white; border:none;
                padding:15px 20px; border-radius:12px;
                font-size:16px; width:100%; cursor:pointer; font-weight: bold;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px;
                transition: all 0.3s ease;">
                📍 Use My Current Location
            </button>
            <div style="text-align: center; margin-bottom: 20px;">
                <a href="/" style="color: #64748b; font-size: 0.8rem; text-decoration: none;">🔄 Reset Location</a>
            </div>
        """, unsafe_allow_html=True)

        g_col1, g_col2 = st.columns(2)
        with g_col1: lat = st.number_input("Latitude", value=q_lat if q_lat != 0.0 else 0.0, format="%.4f")
        with g_col2: lon = st.number_input("Longitude", value=q_lon if q_lon != 0.0 else 0.0, format="%.4f")
        
        if lat != 0.0 or lon != 0.0:
            selected_county = engine.detect_county(lat, lon)
            st.caption(f"🌍 Detected: **{selected_county} County**")
            insight = INSIGHTS.get(selected_county, "💡 **Precision Active**: Satellite mapping at 30m resolution is active for this location.")
            st.info(insight)
        else:
            st.warning("📍 Enter GPS coordinates or use the button above to begin.")
    else:
        county_list = sorted(engine.soil_data["County"].unique().tolist())
        selected_county = st.selectbox(t["county"], ["Select County..."] + county_list, index=0)
        if selected_county == "Select County...":
            selected_county = None
            st.warning("📍 Select a county to proceed.")
        else:
            insight = INSIGHTS.get(selected_county, "💡 **National Coverage**: Analyzing baseline soil chemistry for this zone.")
            st.info(insight)

    # Expert Lab Overrides
    overrides = {}
    if lab_mode:
        st.markdown("##### 🧪 Lab Results (Meter-Level Override)")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1: overrides["pH"] = st.number_input("Lab pH", value=6.5, step=0.1)
        with m_col2: overrides["Total Nitrogen (mg/kg)"] = st.number_input("Lab N", value=1.0, step=0.1)
        with m_col3: overrides["Extractable Phosphorus (mg/kg)"] = st.number_input("Lab P", value=20.0, step=1.0)
        with m_col4: overrides["Extractable Potassium (mg/kg)"] = st.number_input("Lab K", value=150.0, step=10.0)

    st.divider()
    
    col1, col2 = st.columns(2)
    with col1: selected_crop = st.selectbox(t["crop"], list(engine.crop_reqs.keys()))
    with col2: selected_fert = st.selectbox(t["fert"], ["DAP (Diammonium Phosphate)", "CAN", "NPK", "Urea", "Manure", "None"])

    f_col1, f_col2 = st.columns(2)
    with f_col1: farm_acres = st.number_input(t["acres"], min_value=0.25, max_value=500.0, value=1.0, step=0.25)
    with f_col2: price_basis = st.radio("💰 Price Basis", ["Subsidized", "Commercial"], horizontal=True, help="Govt Subsidized (KES 2,500) vs Market Rate (KES 6,500)")

    if st.button(t["button"], use_container_width=True, type="primary"):
        if not selected_county:
            st.error("Please identify your location first.")
        else:
            with st.spinner("Analyzing high-resolution data..."):
                pm_key = "Subsidized" if price_basis == "Subsidized" else "Commercial"
                st.session_state.result = engine.generate_recommendation(
                    selected_county, selected_crop, selected_fert, 
                    farm_size_acres=farm_acres, lang=lang_choice, 
                    lat=lat, lon=lon, overrides=overrides if lab_mode else None,
                    price_mode=pm_key
                )
                st.session_state.last_county = selected_county
            
    # Persistence: If result exists in session state, always show it
    if "result" in st.session_state:
        result = st.session_state.result
        selected_county = st.session_state.get("last_county", selected_county)
        
        if "error" in result:
            st.error(result["error"])
        else:
            save_recommendation(result, farm_acres, lang_choice)
            st.markdown("---")
            
            # Report Section
            h_col1, h_col2 = st.columns([1, 2])
            with h_col1:
                score = result['health_score']
                color = "#dc2626" if score < 40 else "#f59e0b" if score < 70 else "#16a34a"
                st.markdown(f'<div style="background-color: {color}; color: white; padding: 1.5rem; border-radius: 10px; text-align: center;"><h1 style="margin:0; font-size: 3rem;">{score}</h1><p style="margin:0; font-weight: bold;">SOIL HEALTH SCORE</p></div>', unsafe_allow_html=True)
            with h_col2:
                st.markdown(f"## 📊 {t['report_title']}")
                soil = result["county_data"]
                st.caption(f"{t['mapping_source']} {selected_county} County")

            with st.expander("🔬 How is this score calculated?"):
                st.markdown("""
                **Data Basis**: 
                Results are sampled from the **iSDAsoil (2021)** spectral mapping dataset, which provides machine-learning predictions of soil chemistry at 30m resolution across Africa.
                
                **Rating Algorithm (SQI)**:
                We use a **Soil Quality Index (SQI)** that weights parameters based on their scientific impact on yield:
                - **pH (40% Weight)**: Weighted highest because it's the "Gatekeeper"—if pH is low, nutrients are locked in the soil and unavailable to the plant.
                - **Nutrients (60% Weight)**: N, P, K, and Organic Carbon are measured using sigmoidal (S-curve) logic to account for 'Diminishing Returns' (excessive nutrients don't help once sufficiency is reached).
                """)

            # The Switch (Comparison)
            st.markdown("### 🔄 The Switch: Impact Analysis")
            comp = result['comparison']
            st.markdown(f'<div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 1rem; border-radius: 8px;"><table style="width: 100%;"><tr><th>Feature</th><th>Current Habit</th><th style="color: #16a34a;">FarmIQ Recommendation</th></tr><tr><td>Fertilizer</td><td>{comp["current"]}</td><td style="color: #16a34a; font-weight:bold;">{comp["recommended"]}</td></tr><tr><td>Outcome</td><td>Variable</td><td style="color: #16a34a; font-weight:bold;">{comp["impact"]}</td></tr></table></div>', unsafe_allow_html=True)

            # Budget
            st.markdown(f"### 💰 {t['budget_title']}")
            cbA, cbB = st.columns([1, 2])
            with cbA: st.metric(t["total_cost"], f"KES {result['budget']['total_budget']:,}")
            with cbB:
                for line in result['budget']['breakdown']:
                    if farm_acres < 0.5:
                        try:
                            bags = float(line.split(" x ")[0])
                            st.markdown(f"- **{bags*50:.1f}kg** {line.split(' bag ')[-1]}")
                        except: st.markdown(f"- {line}")
                    else: st.markdown(f"- {line}")

            # Advice
            st.markdown(f"### 💡 {t['advice_title']}")
            for item in result["advice"]:
                if any(x in item for x in ["❌", "🚨", "Ukosefu"]): st.error(item, icon="🚨")
                elif any(x in item for x in ["⚠️", "Tahadhari"]): st.warning(item, icon="⚠️")
                elif any(x in item for x in ["💡", "Msimu"]): st.info(item, icon="💡")
                else: st.success(item, icon="✅")

            # Shared Components (PDF, WhatsApp, SMS)
            dealers = get_dealers_by_county(selected_county)
            with st.expander(f"📍 {t['dealers_title']}"):
                for d in dealers:
                    st.markdown(f"**{d['name']}** ({d['town']})")
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={d['name'].replace(' ', '+')}+{d['town'].replace(' ', '+')}+Kenya"
                    st.markdown(f'<a href="{maps_url}" target="_blank" style="text-decoration: none;"><div style="background-color: #007bff; color: white; padding: 0.4rem 1rem; border-radius: 5px; text-align: center; font-size: 0.8rem; font-weight: bold; width: fit-content; margin-bottom: 1rem;">📍 Directions</div></a>', unsafe_allow_html=True)
            
            # WhatsApp Share
            detailed_summary = f"🌱 FarmIQ Soil Report ({selected_county})\n📊 Crop: {result['crop']}\n🧪 Health Score: {result['health_score']}/100\n🚜 Rec: {result['comparison']['recommended']}\n💰 Budget: KES {result['budget']['total_budget']:,}"
            import urllib.parse
            st.markdown(f'<a href="https://api.whatsapp.com/send?text={urllib.parse.quote(detailed_summary)}" target="_blank" style="text-decoration:none;"><div style="background-color: #25D366; color: white; padding: 0.75rem; border-radius: 8px; text-align: center; font-weight: bold;">{t["share"]}</div></a>', unsafe_allow_html=True)

            # PDF Download
            st.write("")
            pdf_bytes = generate_report_pdf(result, lang_choice)
            st.download_button(
                label=f"📄 {t['download_pdf']}",
                data=pdf_bytes,
                file_name=f"FarmIQ_Report_{selected_county}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

            # SMS Fallback Simulator
            st.write("")
            if st.button(f"📲 {t['sms_button']}", key="sms_btn", use_container_width=True):
                st.session_state.show_sms = True
            
            if st.session_state.get('show_sms', False):
                sms_text = engine.generate_sms_summary(result, lang_choice)
                st.markdown(f"""
                <div style="background-color: #333; color: #fff; padding: 1.5rem; border-radius: 20px; border: 4px solid #555; max-width: 300px; margin: 1rem auto; font-family: monospace; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.2);">
                    <div style="text-align: center; font-size: 0.7em; margin-bottom: 15px; color: #888; font-weight: bold;">NOKIA 3310 - MESSAGE RECEIVED</div>
                    <div style="background-color: #c9d6c9; color: #000; padding: 15px; border-radius: 5px; font-size: 0.9em; min-height: 120px; border: 1px solid #999;">
                        {sms_text}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Close SMS", key="close_sms"):
                    st.session_state.show_sms = False
                    st.rerun()

                # Attribution Footer
                st.divider()
                st.markdown('<div style="text-align: center; color: #64748b; font-size: 0.8rem;">📊 Data Source: iSDAsoil (2021) 30m Map | 🧪 Scientific Basis: Kenyan Agronomic Baselines</div>', unsafe_allow_html=True)

# Extension Dashboard
if is_officer:
    with tab_officer:
        st.title("📊 Dashboard")
        stats = get_stats()
        if stats:
            st.metric("Total Queries", stats["total_queries"])
            st.bar_chart(stats["soil_health"])
            records = get_all_records()
            import pandas as pd
            df = pd.DataFrame([{"Time": r.timestamp.strftime("%Y-%m-%d"), "County": r.county, "Crop": r.crop} for r in records])
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Export Full Activity Log (CSV)", 
                csv, "farmiq_analytics.csv", 
                "text/csv", 
                use_container_width=True
            )
