import os
import streamlit as st
import datetime
import numpy as np
import pandas as pd
from recommender import FarmIQRecommender
from report_gen import generate_report_pdf
from dealers import get_dealers_by_county
from database import save_recommendation, get_all_records, get_stats, log_yield, get_farmer_yields
from streamlit_geolocation import streamlit_geolocation
from weather import get_weather_context, get_county_coordinates

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
def load_farmiq_engine_v35():
    try:
        return FarmIQRecommender(DATA_PATH)
    except FileNotFoundError:
        st.error(f"Soil database not found at {DATA_PATH}.")
        st.stop()

engine = load_farmiq_engine_v35()

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
    
    /* Ultimate owner-view suppression: hide everything that isn't the app itself */
    [data-testid="stHeader"], [data-testid="stAppDeployButton"], footer, header, #MainMenu { display: none !important; }
    
    /* Target the 'Manage app' button and bottom toolbar badges using wildcards */
    div[class*="viewerBadge"], [data-testid="stStatusWidget"], [data-testid="stConnectionStatus"] { display: none !important; }
    .stAppDeployButton { display: none !important; }
    button[data-testid="stBaseButton-secondary"] { display: none !important; }
    div[class*="viewerBadge"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# --- Language Mapping ---
LANGS = {
    "English": {
        "title": "Farm Profile", "county": "Where is your farm?", "crop": "What are you planting?", "fert": "What fertilizer do you usually use?",
        "acres": "Farm size (Acres)", "button": "Get Precision Advice", "report_title": "Your Insight Report",
        "mapping_source": "Precision Mapping for", "budget_title": "Budget Estimate", "total_cost": "Total Cost",
        "advice_title": "Actionable Advice", "share": "Share WhatsApp", "download_pdf": "Download PDF",
        "dealers_title": "🛍️ Suppliers Nearby", "directions": "Directions", "sms_button": "SMS Fallback",
        "switch_title": "The Switch: Impact Analysis",
        "table_feature": "Feature", "table_habit": "Your Habit", "table_rec": "FarmIQ Recommendation",
        "table_strategy": "Strategy", "table_outcome": "Outcome",
        "chart_title": "Nutrient Sufficiency Dashboard",
        "chart_legend_curr": "Current Level", "chart_legend_target": "Target Level",
        "nutrients": ["Nitrogen (N)", "Phosphorus (P)", "Potassium (K)"],
        "status": {"low": "Low", "optimal": "Optimal", "acidic": "Acidic", "good": "Healthy"}
    },
    "Kiswahili": {
        "title": "Maelezo ya Shamba", "county": "Zao gani?", "crop": "Unapanda zao gani?", "fert": "Mbolea ya kawaida?",
        "acres": "Ekari", "button": "Pata Ushauri", "report_title": "Ripoti ya Shamba",
        "mapping_source": "Ramani ya", "budget_title": "Gharama", "total_cost": "Gharama Jumla",
        "advice_title": "Ushauri", "share": "Shiriki WhatsApp", "download_pdf": "Pakua PDF",
        "dealers_title": "🛍️ Wauzaji", "directions": "Maelekezo", "sms_button": "SMS",
        "switch_title": "Mabadiliko: Uchambuzi wa Matokeo",
        "table_feature": "Kipengele", "table_habit": "Tabia Yako", "table_rec": "Ushauri wa FarmIQ",
        "table_strategy": "Mkakati", "table_outcome": "Matokeo",
        "chart_title": "Dashibodi ya Kutosha kwa Virutubisho",
        "chart_legend_curr": "Kiwango cha Sasa", "chart_legend_target": "Kiwango Lengwa",
        "nutrients": ["Nitrojeni (N)", "Fosforasi (P)", "Potasiamu (K)"],
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
    # Support both Sidebar and Main Page inputs via Session State
    access_input = st.text_input("Officer Access Code", type="password", key="access_input_sidebar")
    officer_pw = st.secrets.get("OFFICER_PASSWORD", "OFFICER2026")
    
    # Check all possible sources of the code
    current_code = access_input or st.session_state.get("main_access", "")
    is_officer = (str(current_code).upper() == officer_pw.upper())
    
    st.markdown("---")
    st.markdown("### 👨‍🌾 AI Agronomist Settings")
    ai_input = st.text_input("Gemini API Key", type="password", key="ai_input_sidebar")
    ai_key = ai_input or st.session_state.get("main_ai") or st.secrets.get("GEMINI_API_KEY")

# Main Navigation
if is_officer:
    tab_farmer, tab_yield, tab_officer = st.tabs(["🌾 Get Advice", "📈 Track Yield", "🏢 Dashboard"])
else:
    tab_farmer, tab_yield = st.tabs(["🌾 Get Advice", "📈 Track Yield"])

with tab_farmer:
    st.markdown(f'<div class="hero-card"><h1>🌱 FarmIQ</h1><p>National Precision Agriculture Platform</p></div>', unsafe_allow_html=True)
    st.markdown(f"### 📍 {t['title']}")

    # --- PHASE 21: NATIONAL NEUTRALITY UI ---
    col_mode1, col_mode2 = st.columns(2)
    with col_mode1:
        loc_mode = st.radio("Location Mode", ["GPS Precision (30m)", "Select Region (No GPS)"], horizontal=True)
    with col_mode2:
        lab_mode = st.toggle("🧪 Add My Soil Test Results (Optional)", help="Enable if you have a recent laboratory report.")

    if "prev_loc_mode" in st.session_state and st.session_state.prev_loc_mode != loc_mode:
        st.session_state.lat = None
        st.session_state.lon = None
    st.session_state.prev_loc_mode = loc_mode

    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")
    selected_county = None

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
        st.markdown("##### 📍 Satellite Localization")
        
        # UI Tweak: Wrap in columns to add a text label next to the icon
        geo_col1, geo_col2 = st.columns([1, 10])
        with geo_col1:
            location = streamlit_geolocation()
        with geo_col2:
            st.markdown(f"""
                <div style="padding-top: 5px; font-weight: bold; color: #16a34a; cursor: pointer;" 
                     onclick="document.querySelector('button[kind=secondary] span').click();">
                    📍 Use My Current Location
                </div>
            """, unsafe_allow_html=True)
        
        if location and location.get("latitude"):
            st.session_state.lat = round(location["latitude"], 4)
            st.session_state.lon = round(location["longitude"], 4)
        
        if st.session_state.get("lat"):
            lat = st.session_state.lat
            lon = st.session_state.lon
            st.success(f"✅ GPS Signal Locked: {lat}, {lon}")
            selected_county = engine.detect_county(lat, lon)
            st.caption(f"🌍 Detected: **{selected_county} County**")
            insight = INSIGHTS.get(selected_county, "💡 **Precision Active**: Satellite mapping at 30m resolution is active for this location.")
            st.info(insight)
        else:
            st.warning("👆 Click the button above to capture your farm's GPS coordinates.")
            # Manual fallback
            with st.expander("⌨️ Enter Coordinates Manually"):
                g_col1, g_col2 = st.columns(2)
                with g_col1: lat = st.number_input("Latitude", value=0.0, format="%.4f")
                with g_col2: lon = st.number_input("Longitude", value=0.0, format="%.4f")
                if lat != 0.0 or lon != 0.0:
                    st.session_state.lat = lat
                    st.session_state.lon = lon
                    selected_county = engine.detect_county(lat, lon)
                    st.caption(f"🌍 Detected: **{selected_county} County**")
    else:
        # Load Sub-Counties
        import pandas as pd
        sc_path = os.path.join(BASE_DIR, "data", "subcounties.csv")
        subcounty_df = pd.DataFrame()
        if os.path.exists(sc_path):
            subcounty_df = pd.read_csv(sc_path)

        county_list = sorted(engine.soil_data["County"].unique().tolist())
        selected_county = st.selectbox(t["county"], ["Select County..."] + county_list, index=0)
        
        selected_subcounty = None
        if selected_county != "Select County...":
            # Check if we have subcounties for this county
            county_sc = subcounty_df[subcounty_df["County"] == selected_county] if not subcounty_df.empty else pd.DataFrame()
            if not county_sc.empty:
                sc_list = ["Whole County Average"] + sorted(county_sc["SubCounty"].tolist())
                selected_subcounty = st.selectbox("Select Sub-County (API Precision)", sc_list)
                
                if selected_subcounty != "Whole County Average":
                    # Extract coordinates for the API to hook into
                    row = county_sc[county_sc["SubCounty"] == selected_subcounty].iloc[0]
                    lat = float(row["Latitude"])
                    lon = float(row["Longitude"])
                    st.session_state.lat = lat
                    st.session_state.lon = lon
                    st.success(f"🎯 Sub-County API Locked: {selected_subcounty} ({lat}, {lon})")

        if selected_county == "Select County...":
            selected_county = None
            st.warning("📍 Select a county to proceed.")
        else:
            if selected_subcounty and selected_subcounty != "Whole County Average":
                insight = f"💡 **Sub-County Precision Active**: Querying iSDAsoil API for {selected_subcounty}."
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
    with col2: selected_fert = st.selectbox(t["fert"], [
        "DAP (Diammonium Phosphate)", "CAN", "Urea", "NPK 17:17:17", 
        "Mavuno (Planting)", "YaraMila Cereal", "SSP / TSP", "Manure", "None"
    ])

    f_col1, f_col2 = st.columns(2)
    with f_col1: farm_acres = st.number_input(t["acres"], min_value=0.25, max_value=500.0, value=1.0, step=0.25)
    with f_col2: price_basis = st.radio("💰 Price Basis", ["Subsidized", "Commercial"], horizontal=True, help="Govt Subsidized (KES 2,500) vs Market Rate (KES 6,500)")

    if st.button(t["button"], use_container_width=True, type="primary"):
        if not selected_county:
            st.error("Please identify your location first.")
        else:
            with st.spinner("Analyzing high-resolution data..."):
                pm_key = "Subsidized" if price_basis == "Subsidized" else "Commercial"
                is_sub = False
                if loc_mode == "Select Region (No GPS)" and selected_subcounty and selected_subcounty != "Whole County Average":
                    is_sub = True

                result = engine.generate_recommendation(
                    selected_county, selected_crop, selected_fert, 
                    farm_size_acres=farm_acres, lang=lang_choice, 
                    lat=lat, lon=lon, overrides=overrides if lab_mode else None,
                    price_mode=pm_key, is_subcounty=is_sub
                )
                st.session_state.result = result
                st.session_state.last_county = selected_county
                
                # Save to DB exactly once when generated
                save_status = save_recommendation(result, farm_acres, lang_choice)
                if save_status is not True:
                    st.toast(f"Database save failed: {save_status}", icon="⚠️")
            
    # Persistence: If result exists in session state, always show it
    if "result" in st.session_state:
        result = st.session_state.result
        selected_county = st.session_state.get("last_county", selected_county)
        
        if "error" in result:
            st.error(result["error"])
        else:
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
                # Display Data Source for Transparency
                ds_color = "#16a34a" if "Satellite" in result["data_source"] or "Satelaiti" in result["data_source"] else "#64748b"
                st.markdown(f"""
                <div style="background-color: {ds_color}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: bold; width: fit-content; margin-bottom: 5px;">
                    🧬 Source: {result['data_source']}
                </div>
                <div style="font-size: 0.8rem; color: #475569; margin-bottom: 10px;">
                    📡 {result.get('confidence', 'Moderate 🟡 (Based on regional averages)')}
                </div>
                """, unsafe_allow_html=True)
                st.caption(f"{t['mapping_source']} {selected_county} County")

            # Warning if Precision Mode is falling back
            if loc_mode == "GPS Precision (30m)" and "Baseline" in result["data_source"]:
                st.info("💡 **Transparency Note**: High-resolution (30m) raster layer not found. App is using the validated Regional Baseline (CSV) as fallback.")

            with st.expander("🔬 How is this score calculated?"):
                st.markdown("""
                **Data Basis**: 
                Results are sampled from the **iSDAsoil (2021)** spectral mapping dataset, which provides machine-learning predictions of soil chemistry at 30m resolution across Africa.
                
                **Rating Algorithm (SQI)**:
                We use a **Soil Quality Index (SQI)** that weights parameters based on their scientific impact on yield:
                - **pH (40% Weight)**: Weighted highest because it's the "Gatekeeper"—if pH is low, nutrients are locked in the soil and unavailable to the plant.
                - **Nutrients (60% Weight)**: N, P, K, and Organic Carbon are measured using sigmoidal (S-curve) logic to account for 'Diminishing Returns' (excessive nutrients don't help once sufficiency is reached).
                """)

            # Nutrient Impact Visualization
            st.markdown(f"### 📈 {t['chart_title']}")
            
            # Scientific Normalization against Crop Requirements
            reqs = result.get('reqs', {"n_min": 1.2, "p_min": 20, "k_min": 150})
            p_val = result['county_data']['Extractable Phosphorus (mg/kg)']
            n_val = result['county_data']['Total Nitrogen (g/kg)']
            k_val = result['county_data']['Extractable Potassium (mg/kg)']
            
            # Create a comparison dataframe
            # We normalize everything so that '1.0' is exactly what the crop needs.
            chart_df = pd.DataFrame({
                "Nutrient": t["nutrients"],
                t["chart_legend_curr"]: [n_val/reqs['n_min'], p_val/reqs['p_min'], k_val/reqs['k_min']],
                t["chart_legend_target"]: [1.0, 1.0, 1.0]
            }).set_index("Nutrient")
            
            # Render grouped bar chart (side-by-side is more scientific for comparison)
            st.bar_chart(chart_df, color=["#ef4444", "#10b981"]) # Red (Current) vs Green (Target)
            st.caption(f"📊 **Scientific Basis**: 1.0 on the scale represents the optimal {result['crop']} requirement for this nutrient.")

            # The Switch (Comparison)
            st.markdown(f"### 🔄 {t['switch_title']}")
            comp = result.get('comparison', {})
            current_flaw = comp.get("current_flaw", "Analysis pending")
            st.markdown(f"""
                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 1rem; border-radius: 8px;">
                    <table style="width: 100%;">
                        <tr>
                            <th>{t['table_feature']}</th>
                            <th>{t['table_habit']} ({comp.get("current", "")})</th>
                            <th style="color: #16a34a;">{t['table_rec']}</th>
                        </tr>
                        <tr>
                            <td>{t['table_strategy']}</td>
                            <td style="color: #ef4444; font-size:0.9rem;">{current_flaw}</td>
                            <td style="color: #16a34a; font-weight:bold;">{comp.get("recommended", "")}</td>
                        </tr>
                        <tr>
                            <td>{t['table_outcome']}</td>
                            <td>{comp.get("current_outcome", "Variable Yield")}</td>
                            <td style="color: #16a34a; font-weight:bold;">{comp.get("impact", "")}</td>
                        </tr>
                    </table>
                </div>
            """, unsafe_allow_html=True)

            # Crop Calendar Timeline
            st.markdown("### 📅 3-Month Action Plan")
            timeline = result.get("timeline")
            if timeline and isinstance(timeline, dict):
                st.caption(f"Based on **{timeline['season']}** for **{result['crop']}**")
                
                # Visual Stepper UI
                st.markdown("""
                <style>
                .step-box {
                    background-color: #f8fafc;
                    border-top: 4px solid #3b82f6;
                    padding: 15px;
                    border-radius: 5px;
                    height: 100%;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }
                .step-number {
                    font-size: 0.8rem;
                    color: #64748b;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    font-weight: 700;
                    margin-bottom: 5px;
                }
                .step-action {
                    font-size: 0.95rem;
                    color: #0f172a;
                    font-weight: 600;
                }
                </style>
                """, unsafe_allow_html=True)
                
                t_col1, t_col2, t_col3 = st.columns(3)
                with t_col1:
                    st.markdown(f'<div class="step-box"><div class="step-number">Month 1</div><div class="step-action">{timeline["month_1"]}</div></div>', unsafe_allow_html=True)
                with t_col2:
                    st.markdown(f'<div class="step-box" style="border-color: #10b981;"><div class="step-number">Month 2</div><div class="step-action">{timeline["month_2"]}</div></div>', unsafe_allow_html=True)
                with t_col3:
                    st.markdown(f'<div class="step-box" style="border-color: #f59e0b;"><div class="step-number">Month 3</div><div class="step-action">{timeline["month_3"]}</div></div>', unsafe_allow_html=True)
            else:
                st.info("Calendar data not currently available for this crop.")

            # Budget -> Shopping List
            st.markdown(f"### 🛒 Fertilizer Shopping List")
            st.caption(f"Exact quantities required for your **{farm_acres} acres**.")
            cbA, cbB = st.columns([1, 2])
            with cbA: st.metric(t["total_cost"], f"KES {result['budget']['total_budget']:,}")
            with cbB:
                for line in result['budget']['breakdown']:
                    if farm_acres < 0.5:
                        try:
                            import re
                            # Match quantity like "1.0 x" anywhere in the string
                            match = re.search(r"(\d+\.?\d*)\s*x", line)
                            if match:
                                bags = float(match.group(1))
                                # Keep prefix (e.g. Stage 1) if present
                                prefix = line.split(":")[0] + ": " if ":" in line else ""
                                product = line.split(" bags ")[-1]
                                st.markdown(f"- {prefix}**{bags*50:.1f}kg** {product}")
                            else:
                                st.markdown(f"- {line}")
                        except: st.markdown(f"- {line}")
                    else: st.markdown(f"- {line}")

            # Advice
            st.markdown(f"### 💡 {t['advice_title']}")
            for item in result["advice"]:
                if any(x in item for x in ["❌", "🚨", "Ukosefu"]): st.error(item, icon="🚨")
                elif any(x in item for x in ["⚠️", "Tahadhari"]): st.warning(item, icon="⚠️")
                elif any(x in item for x in ["💡", "Msimu"]): st.info(item, icon="💡")
                else: st.success(item, icon="✅")

            # Weather Context
            saved_lat = st.session_state.get('saved_lat')
            saved_lon = st.session_state.get('saved_lon')
            
            # If no GPS provided, fallback to the county's central coordinates
            if not saved_lat or not saved_lon or saved_lat == 0.0 or saved_lon == 0.0:
                weather_lat, weather_lon = get_county_coordinates(selected_county)
            else:
                weather_lat, weather_lon = saved_lat, saved_lon
                
            with st.spinner("Fetching 7-day weather forecast..."):
                weather_advice = get_weather_context(weather_lat, weather_lon)
            if weather_advice:
                st.markdown("### ⛅ 7-Day Weather Context")
                if "✅" in weather_advice:
                    st.success(weather_advice, icon="✅")
                elif "🌧️" in weather_advice:
                    st.error(weather_advice, icon="🌧️")
                else:
                    st.warning(weather_advice, icon="⚠️")

            # --- Reverse Recommendation (Best Crop Matches) ---
            st.markdown(f"### 🌱 {('Crop Suitability Match' if lang_choice == 'English' else 'Mazao Yanayofaa Zaidi')}")
            with st.expander("🧐 View Best Matches for Your Soil", expanded=False):
                matches = engine.match_crops_to_soil(result, farm_acres=farm_acres, lang=lang_choice)
                if matches:
                        st.write("Based on your soil's pH and nutrient levels, here are the crops with the highest success probability:")
                        for m in matches:
                            col_m1, col_m2 = st.columns([2, 1])
                            with col_m1:
                                st.markdown(f"**{m['crop']}**")
                                # Color bar for match score
                                color = "#16a34a" if m['match_score'] >= 85 else "#eab308" if m['match_score'] >= 70 else "#f97316"
                                st.markdown(f"""
                                <div style="background-color: #e2e8f0; border-radius: 10px; width: 100%; height: 8px; margin: 5px 0;">
                                    <div style="background-color: {color}; width: {m['match_score']}%; height: 100%; border-radius: 10px;"></div>
                                </div>
                                """, unsafe_allow_html=True)
                                st.caption(f"{m['label']} ({m['match_score']}% Match)")
                            with col_m2:
                                st.metric("Est. Gross", f"KES {m['gross_income']:,}")
                else:
                    st.info("Optimization engine is still loading data...")

            # --- AI Agronomist Layer ---
            if ai_key:
                st.markdown(f"### 👨‍🌾 {('AI Expert Briefing' if lang_choice == 'English' else 'Ushauri wa Mtaalamu wa AI')}")
                with st.expander("📖 Read Your Expert Advisory Note", expanded=True):
                    with st.spinner("Expert agronomist is analyzing your data..."):
                        # Use a cached generation to avoid repeated API calls on every re-render
                        if "ai_note" not in st.session_state or st.session_state.get("last_result_id") != id(result):
                            ai_note = engine.generate_ai_advisory(result, api_key=ai_key, lang=lang_choice)
                            st.session_state.ai_note = ai_note
                            st.session_state.last_result_id = id(result)
                        else:
                            ai_note = st.session_state.ai_note
                        
                        if ai_note:
                            st.markdown(f"""
                            <div style="background-color: #f8fafc; padding: 1.5rem; border-radius: 10px; border-left: 5px solid #16a34a; font-family: 'Inter', sans-serif; line-height: 1.6; color: #1e293b;">
                                {ai_note}
                            </div>
                            """, unsafe_allow_html=True)
                            st.caption("🤖 *Note: This briefing is generated by AI based on scientific soil parameters. Always cross-verify with local extension officers.*")
            else:
                st.info("👨‍🌾 **Want an Expert Briefing?** Open the sidebar (top-left arrow) and enter a Gemini API Key to enable the AI Agronomist layer.")

            # Shared Components (Dealers)
            dealers = get_dealers_by_county(selected_county)
            with st.expander(f"📍 {t['dealers_title']}"):
                import urllib.parse
                
                current_lat = st.session_state.get('lat')
                current_lon = st.session_state.get('lon')
                
                # Fallback to county center for directions if no farm precision coordinates exist
                if not current_lat or current_lat == 0.0:
                    current_lat, current_lon = get_county_coordinates(selected_county)
                
                # Dynamic GPS-based local search if coordinates exist
                if current_lat and current_lon and current_lat != 0.0 and current_lon != 0.0:
                    gps_search = f"https://www.google.com/maps/search/Agrovet+Fertilizer/@{current_lat},{current_lon},14z"
                    st.markdown(f'<a href="{gps_search}" target="_blank" style="text-decoration: none;"><div style="background-color: #16a34a; color: white; padding: 0.6rem 1rem; border-radius: 8px; text-align: center; font-size: 0.9rem; font-weight: bold; margin-bottom: 1.5rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">🌍 Search All Agrovets Near My Location</div></a>', unsafe_allow_html=True)
                
                for d in dealers:
                    if d['county'] == "All":
                        # National distributors: We do not have their exact addresses in the DB. 
                        # Providing a map link for them gives wrong directions, so we just list them.
                        st.markdown(f"**{d['name']}** (Available at {selected_county} County Depot)")
                    else:
                        # Specific local dealers: Provide a precise pin on the map with Place Details
                        st.markdown(f"**{d['name']}** ({d['town']})")
                        
                        # Rich Map Search: Name + Town to trigger the Business Card sidebar
                        search_query = f"{d['name']} {d['town']} Kenya"
                        maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(search_query)}"
                        st.markdown(f'<a href="{maps_url}" target="_blank" style="text-decoration: none;"><div style="background-color: #007bff; color: white; padding: 0.4rem 1rem; border-radius: 5px; text-align: center; font-size: 0.8rem; font-weight: bold; width: fit-content; margin-bottom: 1.5rem;">🗺️ View on Map</div></a>', unsafe_allow_html=True)
                        st.write("")
            
            # --- Action Buttons: WhatsApp & PDF & SMS ---
            st.write("")
            st.markdown("### 📤 Share Results")
            # Build timeline string for WhatsApp
            tl = result.get("timeline", {})
            if isinstance(tl, dict):
                timeline_str = f"📅 M1: {tl.get('month_1', '')}\n📅 M2: {tl.get('month_2', '')}\n📅 M3: {tl.get('month_3', '')}"
            else:
                timeline_str = ""
            
            shopping_str = "\n".join([f"🛒 {line}" for line in result['budget']['breakdown']])
            
            detailed_summary = f"🌱 FarmIQ Soil Report ({selected_county})\n📊 Crop: {result['crop']}\n🧪 Health Score: {result['health_score']}/100\n\n🚜 Shopping List ({farm_acres} Acres):\n{shopping_str}\n💰 Est. Budget: KES {result['budget']['total_budget']:,}\n\n📅 Calendar:\n{timeline_str}"
            import urllib.parse
            st.markdown(f'<a href="https://api.whatsapp.com/send?text={urllib.parse.quote(detailed_summary)}" target="_blank" style="text-decoration:none;"><div style="background-color: #25D366; color: white; padding: 0.75rem; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 10px;">✅ {t["share"]}</div></a>', unsafe_allow_html=True)
            
            # PDF Download
            pdf_bytes = generate_report_pdf(result, lang_choice)
            st.download_button(
                label=f"📄 {t['download_pdf']}",
                data=pdf_bytes,
                file_name=f"FarmIQ_Report_{selected_county}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

            # SMS Fallback Simulator Toggle (Using a unique key to prevent errors)
            if st.button(f"📲 {t['sms_button']}", key="sms_sim_trigger", use_container_width=True):
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
                if st.button("Close SMS", key="close_sms_sim"):
                    st.session_state.show_sms = False
                    st.rerun()

            # Attribution Footer
            st.divider()
            st.markdown('<div style="text-align: center; color: #64748b; font-size: 0.8rem;">📊 Data Source: iSDAsoil (2021) 30m Map | 🧪 Scientific Basis: Kenyan Agronomic Baselines</div>', unsafe_allow_html=True)

    # --- SETTINGS & ACCESS (Main Page) ---
    st.write("")
    with st.expander("🛠️ Advanced Settings & Officer Login"):
        sf1, sf2 = st.columns(2)
        with sf1:
            st.markdown("### 🏛️ B2B Login")
            st.text_input("Officer Access Code", type="password", key="main_access", help="Enter password to unlock B2B Dashboard")
        with sf2:
            st.markdown("### 👨‍🌾 AI Setup")
            st.text_input("Gemini API Key", type="password", key="main_ai", help="Enter API key to unlock AI Agronomist")
        
        if is_officer:
            st.success("✅ Officer Access Granted!")
        if ai_key and len(str(ai_key)) > 10:
            st.success("✅ AI Engine Connected!")



# --- YIELD TRACKING TAB ---
with tab_yield:
    st.markdown("## 📈 Season-over-Season Yield Tracking")
    st.markdown("Log your actual harvest to see how FarmIQ recommendations are improving your yield over time.")
    
    st.markdown("### 1. Identify Your Farm")
    farmer_id = st.text_input("Enter Farm Name or Mobile Number (e.g. 0712345678)")
    
    if farmer_id:
        st.markdown("### 2. Log New Harvest")
        with st.form("log_yield_form"):
            colA, colB, colC = st.columns(3)
            with colA:
                y_crop = st.selectbox("Crop", list(engine.crop_reqs.keys()))
            with colB:
                # Generate seasons dynamically based on current year
                import datetime as dt
                current_year = dt.datetime.now().year
                seasons = []
                for yr in range(current_year - 2, current_year + 1):
                    seasons.append(f"Long Rains {yr}")
                    seasons.append(f"Short Rains {yr}")
                y_season = st.selectbox("Season", seasons)
            with colC:
                y_amount = st.number_input("Yield (Bags / Acre)", min_value=0.0, max_value=100.0, step=0.5, value=15.0)
                
            submitted = st.form_submit_button("💾 Save Harvest Data", use_container_width=True)
            if submitted:
                log_yield(farmer_id, y_crop, y_season, y_amount)
                st.success("Harvest logged successfully! 🌾")
        
        st.markdown("### 3. Your Yield Growth")
        records = get_farmer_yields(farmer_id)
        if records:
            import pandas as pd
            df_yields = pd.DataFrame([{
                "Season": r.season,
                "Crop": r.crop,
                "Bags per Acre": r.yield_bags_per_acre
            } for r in records])
            
            # Pivot if they have multiple crops, or just plot if one
            crops_logged = df_yields["Crop"].unique()
            for crop in crops_logged:
                st.markdown(f"#### 🌽 {crop} Yield History")
                crop_df = df_yields[df_yields["Crop"] == crop]
                # Bar chart
                st.bar_chart(data=crop_df, x="Season", y="Bags per Acre", color="#16a34a", height=300)
                
                # Show percentage growth if multiple seasons
                if len(crop_df) > 1:
                    first_yield = crop_df.iloc[0]["Bags per Acre"]
                    last_yield = crop_df.iloc[-1]["Bags per Acre"]
                    if first_yield > 0:
                        growth = ((last_yield - first_yield) / first_yield) * 100
                        if growth > 0:
                            st.success(f"🚀 **Awesome!** Your {crop} yield has increased by **{growth:.1f}%** since you started tracking!")
                        elif growth < 0:
                            st.warning(f"📉 Your {crop} yield decreased by **{abs(growth):.1f}%**. Make sure to follow the precise fertilizer timelines.")
        else:
            st.info("No harvest data found for this Farm ID. Log your first harvest above!")

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
                label="📥 Download Data CSV" if lang_choice == "English" else "📥 Pakua Data CSV",
                data=csv,
                file_name="farmiq_dashboard.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
            st.markdown("### 💰 Market Pricing Management")
            st.write("Update current market prices and expected yields to keep farmer ROI estimates accurate.")
            
            if not engine.crop_econ.empty:
                # Use columns to put the save button in a prominent place
                btn_col1, btn_col2 = st.columns([3, 1])
                with btn_col2:
                    save_clicked = st.button("💾 SAVE UPDATES", use_container_width=True, type="primary")
                
                edited_df = st.data_editor(engine.crop_econ, use_container_width=True, hide_index=True, key="econ_editor")
                
                if save_clicked:
                    econ_path = os.path.join(os.path.dirname(__file__), "data", "crop_economics.csv")
                    edited_df.to_csv(econ_path, index=False)
                    # Manually update the engine's memory so it doesn't use the old cached data
                    engine.crop_econ = edited_df
                    st.success("✅ Market data updated successfully! Values refreshed.")
                    st.rerun()
        else:
            st.info("No queries have been made yet. The dashboard will populate once farmers start using the platform.")
