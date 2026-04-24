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
def load_farmiq_engine_v3():
    try:
        return FarmIQRecommender(DATA_PATH)
    except FileNotFoundError:
        st.error(f"Soil database not found at {DATA_PATH}.")
        st.stop()

engine = load_farmiq_engine_v3()

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
    [data-testid="collapsedControl"] { display: none !important; } /* Hide the sidebar toggle check */
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
            lat = round(location["latitude"], 4)
            lon = round(location["longitude"], 4)
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
                    selected_county = engine.detect_county(lat, lon)
                    st.caption(f"🌍 Detected: **{selected_county} County**")
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
                st.session_state.saved_lat = lat
                st.session_state.saved_lon = lon
            
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
            st.markdown("### 📈 Nutrient Impact Dashboard")
            # Calculate deficiency gaps for chart
            p_val = result['county_data']['Extractable Phosphorus (mg/kg)']
            n_val = result['county_data']['Total Nitrogen (mg/kg)']
            k_val = result['county_data']['Extractable Potassium (mg/kg)']
            
            # Simple Normalized sufficiency levels for chart (0.0 to 1.0)
            chart_data = pd.DataFrame({
                "Nutrient": ["Phosphorus (P)", "Nitrogen (N)", "Potassium (K)"],
                "Current Level": [min(p_val/30, 1.0), min(n_val/0.2, 1.0), min(k_val/250, 1.0)],
                "Recommended": [1.0, 1.0, 1.0]
            }).set_index("Nutrient")
            
            st.bar_chart(chart_data, color=["#f87171", "#34d399"]) # Red (Current) vs Green (Target)
            st.caption("🔴 Red: Current Deficiency | 🟢 Green: Recommended Target Hub")

            # The Switch (Comparison)
            st.markdown("### 🔄 The Switch: Impact Analysis")
            comp = result.get('comparison', {})
            current_flaw = comp.get("current_flaw", "Analysis pending")
            st.markdown(f'<div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 1rem; border-radius: 8px;"><table style="width: 100%;"><tr><th>Feature</th><th>Your Habit ({comp.get("current", "")})</th><th style="color: #16a34a;">FarmIQ Recommendation</th></tr><tr><td>Strategy</td><td style="color: #ef4444; font-size:0.9rem;">{current_flaw}</td><td style="color: #16a34a; font-weight:bold;">{comp.get("recommended", "")}</td></tr><tr><td>Outcome</td><td>Variable Yield</td><td style="color: #16a34a; font-weight:bold;">{comp.get("impact", "")}</td></tr></table></div>', unsafe_allow_html=True)

            # Crop Calendar Timeline
            st.markdown("### 📅 Application Calendar")
            if result.get("timeline"):
                for t_item in result["timeline"]:
                    st.info(f"**{t_item['week']}**: {t_item['action']}")
            else:
                st.success("Soil is optimally balanced. No major amendments required.")

            # Budget -> Shopping List
            st.markdown(f"### 🛒 Fertilizer Shopping List")
            st.caption(f"Exact quantities required for your **{farm_acres} acres**.")
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


            # Shared Components (Dealers)
            dealers = get_dealers_by_county(selected_county)
            with st.expander(f"📍 {t['dealers_title']}"):
                import urllib.parse
                
                saved_lat = st.session_state.get('saved_lat')
                saved_lon = st.session_state.get('saved_lon')
                
                # Dynamic GPS-based local search if coordinates exist
                if saved_lat and saved_lon and saved_lat != 0.0 and saved_lon != 0.0:
                    gps_search = f"https://www.google.com/maps/search/Agrovet+Fertilizer/@{saved_lat},{saved_lon},14z"
                    st.markdown(f'<a href="{gps_search}" target="_blank" style="text-decoration: none;"><div style="background-color: #16a34a; color: white; padding: 0.6rem 1rem; border-radius: 8px; text-align: center; font-size: 0.9rem; font-weight: bold; margin-bottom: 1.5rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">🌍 Search All Agrovets Near My Location</div></a>', unsafe_allow_html=True)
                
                for d in dealers:
                    if d['county'] == "All":
                        # National distributors: We do not have their exact addresses in the DB. 
                        # Providing a map link for them gives wrong directions, so we just list them.
                        st.markdown(f"**{d['name']}** (Available at {selected_county} County Depot)")
                    else:
                        # Specific local dealers: Provide a simple, reliable Google Maps search
                        st.markdown(f"**{d['name']}** ({d['town']})")
                        search_query = f"{d['name']} {d['town']} Kenya"
                        maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(search_query)}"
                        st.markdown(f'<a href="{maps_url}" target="_blank" style="text-decoration: none;"><div style="background-color: #007bff; color: white; padding: 0.4rem 1rem; border-radius: 5px; text-align: center; font-size: 0.8rem; font-weight: bold; width: fit-content; margin-bottom: 1rem;">📍 Search on Map</div></a>', unsafe_allow_html=True)
            
            # --- Action Buttons: WhatsApp & PDF & SMS ---
            st.write("")
            st.markdown("### 📤 Share Results")
            # Build timeline string for WhatsApp
            timeline_str = "\n".join([f"🗓️ {t['week']}: {t['action']}" for t in result.get("timeline", [])])
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
                "📥 Export Full Activity Log (CSV)", 
                csv, "farmiq_analytics.csv", 
                "text/csv", 
                use_container_width=True
            )
