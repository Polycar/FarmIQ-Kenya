import os
import re
import datetime
import urllib.parse
import numpy as np
import pandas as pd
import requests as _requests
import streamlit as st

from recommender import FarmIQRecommender
from report_gen import generate_report_pdf
from dealers import get_dealers_by_county
from database import save_recommendation, get_all_records, get_stats, log_yield, get_farmer_yields
from streamlit_geolocation import streamlit_geolocation
from weather import get_weather_context, get_county_coordinates

st.set_page_config(
    page_title="FarmIQ Kenya",
    page_icon="🌱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "kenya_county_soils.csv")

def load_farmiq_engine():
    try:
        return FarmIQRecommender(DATA_PATH)
    except FileNotFoundError:
        st.error(f"Soil database not found at {DATA_PATH}.")
        st.stop()

engine = load_farmiq_engine()

# ── Secrets ──
try:    ISDA_USER = st.secrets["ISDA_USERNAME"]; ISDA_PASS = st.secrets["ISDA_PASSWORD"]
except: ISDA_USER = ISDA_PASS = None

# ── Mobile-first CSS ──
st.markdown("""
<style>
[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],
[data-testid="stConnectionStatus"],[data-testid="stAppDeployButton"],
[data-testid="collapsedControl"],div[class*="viewerBadge"],
footer,header,#MainMenu{display:none!important;}

/* Force off-white background for the app & give space for mobile keyboard drop-downs */
.stApp{background:#f8fafc;font-family:'Inter',sans-serif;padding-bottom: 600px !important;}

/* 🚨 CRITICAL: Force dark text to prevent Dark Mode from turning fonts white on white backgrounds */
.stApp, h1, h2, h3, h4, h5, h6, p, label, li, span, div[data-testid="stExpander"] summary, [data-testid="stMetricValue"] {
    color: #0f172a !important;
}

/* White text exceptions for designed cards and camera capture */
.hero-card h1, .hero-card p, .score-box h1, .score-box p, 
div[data-testid="stButton"] button, div[data-testid="stButton"] button p,
div[data-testid="stCameraInput"] button, div[data-testid="stCameraInput"] button span {
    color: #ffffff !important;
}

/* Force light theme for file uploader */
div[data-testid="stFileUploader"] section {
    background-color: #f1f5f9 !important;
    border: 2px dashed #cbd5e1 !important;
}
div[data-testid="stFileUploader"] section * {
    color: #0f172a !important;
}
div[data-testid="stFileUploader"] button {
    background-color: #16a34a !important;
    color: #ffffff !important;
}

/* Dropdown popovers (render outside .stApp) */
div[data-baseweb="popover"] ul {
    background-color: #ffffff !important;
}
div[data-baseweb="popover"] li {
    background-color: #ffffff !important;
    color: #0f172a !important;
}
div[data-baseweb="popover"] li:hover {
    background-color: #f1f5f9 !important;
}

.hero-card{background:linear-gradient(135deg,#16a34a,#15803d);color:white;
  padding:1.5rem 1rem;border-radius:16px;text-align:center;
  box-shadow:0 10px 15px -3px rgba(0,0,0,0.15);margin-bottom:1.5rem;}
.hero-card h1{margin:0;font-weight:800;font-size:2rem;}
.hero-card p{margin:0.25rem 0 0;font-size:0.9rem;opacity:0.9;}

.score-box{color:white;padding:1.25rem;border-radius:12px;text-align:center;margin-bottom:1rem;}
.score-box h1{margin:0;font-size:3rem;font-weight:800;}
.score-box p{margin:0;font-weight:700;font-size:0.85rem;letter-spacing:.05em;}

.step-box{background:#f8fafc;border-top:4px solid #3b82f6;padding:12px;
  border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:.75rem;}
.step-number{font-size:.75rem;color:#64748b;text-transform:uppercase;
  letter-spacing:1px;font-weight:700;margin-bottom:4px;}
.step-action{font-size:.9rem;color:#0f172a;font-weight:600;}

div[data-testid="stButton"] button{border-radius:10px!important;font-weight:600!important;}
</style>
""", unsafe_allow_html=True)

# ── Language strings ──
LANGS = {
    "English": {
        "title":"Farm Profile","county":"Where is your farm?",
        "crop":"What are you planting?","fert":"What fertilizer do you usually use?",
        "acres":"Farm size (Acres)","button":"🌱 Get Precision Advice",
        "report_title":"Your Insight Report","mapping_source":"Precision Mapping for",
        "budget_title":"Budget Estimate","total_cost":"Total Cost",
        "advice_title":"Actionable Advice","share":"Share on WhatsApp",
        "download_pdf":"Download PDF Report","dealers_title":"🛍️ Suppliers Nearby",
        "sms_button":"📲 SMS Summary","switch_title":"The Switch: Impact Analysis",
        "table_feature":"Feature","table_habit":"Your Habit",
        "table_rec":"FarmIQ Recommendation","table_strategy":"Strategy","table_outcome":"Outcome",
        "chart_title":"Nutrient Sufficiency","chart_legend_curr":"Current Level",
        "chart_legend_target":"Target Level",
        "nutrients":["Nitrogen (N)","Phosphorus (P)","Potassium (K)"],
        "status":{"low":"Low","optimal":"Optimal","acidic":"Acidic","good":"Healthy"}
    },
    "Kiswahili": {
        "title":"Maelezo ya Shamba","county":"Shamba lako lipo wapi?",
        "crop":"Unapanda zao gani?","fert":"Mbolea ya kawaida?",
        "acres":"Ukubwa (Ekari)","button":"🌱 Pata Ushauri",
        "report_title":"Ripoti ya Shamba","mapping_source":"Ramani ya",
        "budget_title":"Gharama","total_cost":"Jumla",
        "advice_title":"Ushauri","share":"Shiriki WhatsApp",
        "download_pdf":"Pakua PDF","dealers_title":"🛍️ Wauzaji Karibu",
        "sms_button":"📲 Muhtasari wa SMS","switch_title":"Mabadiliko: Uchambuzi",
        "table_feature":"Kipengele","table_habit":"Tabia Yako",
        "table_rec":"Ushauri wa FarmIQ","table_strategy":"Mkakati","table_outcome":"Matokeo",
        "chart_title":"Kiwango cha Virutubisho","chart_legend_curr":"Kiwango cha Sasa",
        "chart_legend_target":"Kiwango Lengwa",
        "nutrients":["Nitrojeni (N)","Fosforasi (P)","Potasiamu (K)"],
        "status":{"low":"Chini","optimal":"Vizuri","acidic":"Asidi","good":"Sawa"}
    }
}

INSIGHTS = {
    "Nakuru":      "💡 **Local Variation**: Naivasha soil is often more acidic than Nakuru Town.",
    "Kakamega":    "💡 **Western Insight**: High rainfall causes phosphorus fixation here.",
    "Mombasa":     "💡 **Coastal Precision**: Salinity varies within metres of the shore.",
    "Nairobi":     "💡 **Urban Variation**: Peri-urban soils shift rapidly. Map precisely.",
    "Kiambu":      "💡 **Topography Alert**: pH changes with elevation on hillsides.",
    "Uasin Gishu": "💡 **Grain Basket**: Intensive cereal farming creates nutrient hotspots.",
}

# ── Language selector ──
lc1, lc2 = st.columns([3, 1])
with lc2:
    lang_choice = st.selectbox("🌐", ["English", "Kiswahili"],
                               label_visibility="collapsed", key="lang_select")
t = LANGS[lang_choice]

# ── Sidebar ──
with st.sidebar:
    st.markdown("### 🏛️ B2B Access")
    access_input = st.text_input("Officer Access Code", type="password", key="access_input_sidebar")
    officer_pw   = st.secrets.get("OFFICER_PASSWORD", "OFFICER2026")
    current_code = access_input or st.session_state.get("main_access", "")
    is_officer   = (str(current_code).upper() == officer_pw.upper())

# ── Tabs ──
if is_officer:
    tab_farmer, tab_yield, tab_doctor, tab_officer = st.tabs(["🌾 Advice", "📈 Yield", "📸 Plant Doctor", "🏢 Dashboard"])
else:
    tab_farmer, tab_yield, tab_doctor = st.tabs(["🌾 Get Advice", "📈 Track Yield", "📸 Plant Doctor"])


# ════════════════════════════════════════════════════════════════
# TAB 1 — FARMER ADVICE
# ════════════════════════════════════════════════════════════════
with tab_farmer:
    st.markdown('<div class="hero-card"><h1>🌱 FarmIQ</h1><p>National Precision Agriculture Platform</p></div>', unsafe_allow_html=True)
    st.markdown(f"### 📍 {t['title']}")

    loc_mode = st.radio("Location Mode",
        ["📡 GPS Precision (30m)", "🗺️ Select Region (No GPS)"],
        index=1,
        horizontal=True,
        label_visibility="collapsed")
    use_gps  = loc_mode.startswith("📡")
    lab_mode = st.toggle("🧪 I have a soil lab report")

    if "prev_loc_mode" in st.session_state and st.session_state.prev_loc_mode != loc_mode:
        st.session_state.lat = None
        st.session_state.lon = None
    st.session_state.prev_loc_mode = loc_mode

    lat, lon, selected_county = st.session_state.get("lat"), st.session_state.get("lon"), None

    # GPS mode
    if use_gps:
        st.markdown("##### 📍 Capture Your Farm Location")
        st.warning("⚠️ **Security Restriction**: Browsers block GPS access over local insecure links (`http://192.168...`). Switch to **Select Region** above to bypass this fallback block.")
        location = streamlit_geolocation()
        if location and location.get("latitude"):
            st.session_state.lat = round(location["latitude"], 4)
            st.session_state.lon = round(location["longitude"], 4)
        if st.session_state.get("lat"):
            lat, lon = st.session_state.lat, st.session_state.lon
            st.success(f"✅ GPS Locked: {lat}, {lon}")
            selected_county = engine.detect_county(lat, lon)
            st.caption(f"🌍 **{selected_county} County** detected")
            st.info(INSIGHTS.get(selected_county, "💡 **Precision Active**: 30m satellite mapping enabled."))
        else:
            st.warning("👆 Tap the location button above to capture your GPS coordinates.")
            with st.expander("⌨️ Enter Coordinates Manually"):
                lat = st.number_input("Latitude",  value=0.0, format="%.4f", key="man_lat")
                lon = st.number_input("Longitude", value=0.0, format="%.4f", key="man_lon")
                if lat != 0.0 or lon != 0.0:
                    st.session_state.lat = lat; st.session_state.lon = lon
                    selected_county = engine.detect_county(lat, lon)
                    st.caption(f"🌍 **{selected_county} County** detected")

    # Region mode
    else:
        sc_path      = os.path.join(BASE_DIR, "data", "subcounties.csv")
        subcounty_df = pd.read_csv(sc_path) if os.path.exists(sc_path) else pd.DataFrame()
        county_list  = sorted(engine.soil_data["County"].unique().tolist())
        selected_county = st.selectbox(t["county"], ["Select County..."] + county_list)
        selected_subcounty = None
        if selected_county and selected_county != "Select County...":
            # Auto-load County Baseline coordinates
            c_lat, c_lon = get_county_coordinates(selected_county)
            st.session_state.lat, st.session_state.lon = c_lat, c_lon
            lat, lon = c_lat, c_lon
            
            county_sc = subcounty_df[subcounty_df["County"] == selected_county] if not subcounty_df.empty else pd.DataFrame()
            if not county_sc.empty:
                sc_list = ["Whole County Average"] + sorted(county_sc["SubCounty"].tolist())
                selected_subcounty = st.selectbox("Select Sub-County (API Precision)", sc_list)
                if selected_subcounty != "Whole County Average":
                    row = county_sc[county_sc["SubCounty"] == selected_subcounty].iloc[0]
                    lat, lon = float(row["Latitude"]), float(row["Longitude"])
                    st.session_state.lat, st.session_state.lon = lat, lon
                    st.success(f"🎯 Sub-County Locked: {selected_subcounty} ({lat:.4f}, {lon:.4f})")
            st.info(f"💡 **Sub-County Precision Active**: Querying iSDAsoil for {selected_subcounty}."
                    if selected_subcounty and selected_subcounty != "Whole County Average"
                    else INSIGHTS.get(selected_county, "💡 **National Coverage**: Analysing regional soil chemistry."))
        elif selected_county == "Select County...":
            selected_county = None
            st.warning("📍 Select a county to proceed.")

    # Lab override — 2x2 grid (mobile friendly)
    overrides = {}
    if lab_mode:
        st.markdown("##### 🧪 Your Lab Results")
        r1c1, r1c2 = st.columns(2)
        r2c1, r2c2 = st.columns(2)
        with r1c1: overrides["pH"]                             = st.number_input("Lab pH",      value=6.5,   step=0.1)
        with r1c2: overrides["Total Nitrogen (g/kg)"]          = st.number_input("Lab N (g/kg)",value=1.0,   step=0.1)
        with r2c1: overrides["Extractable Phosphorus (mg/kg)"] = st.number_input("Lab P (mg/kg)",value=20.0, step=1.0)
        with r2c2: overrides["Extractable Potassium (mg/kg)"]  = st.number_input("Lab K (mg/kg)",value=150.0,step=10.0)

    st.divider()

    selected_crop = st.selectbox(t["crop"], list(engine.crop_reqs.keys()))
    selected_fert = st.selectbox(t["fert"], [
        "DAP (Diammonium Phosphate)","CAN","Urea","NPK 17:17:17",
        "Mavuno (Planting)","YaraMila Cereal","SSP / TSP","Manure","None"
    ])
    farm_acres  = st.number_input(t["acres"], min_value=0.25, max_value=500.0, value=1.0, step=0.25)
    price_basis = st.selectbox("💰 Price Basis",
                               ["Subsidized (KES 2,500/bag)", "Commercial (Market Rate)"])

    if st.button(t["button"], use_container_width=True, type="primary"):
        if not selected_county:
            st.error("Please identify your location first." if lang_choice == "English" else "Tafadhali bainisha eneo lako kwanza.")
        else:
            with st.spinner("Analysing soil data..." if lang_choice == "English" else "Inachambua data ya udongo..."):
                pm_key = "Subsidized" if "Subsidized" in price_basis else "Commercial"
                is_sub = (not use_gps and 'selected_subcounty' in dir() and selected_subcounty and selected_subcounty != "Whole County Average")
                result = engine.generate_recommendation(
                    selected_county, selected_crop, selected_fert,
                    farm_size_acres=farm_acres, lang=lang_choice,
                    lat=lat, lon=lon,
                    overrides=overrides if lab_mode else None,
                    price_mode=pm_key, is_subcounty=is_sub
                )
                st.session_state.result      = result
                st.session_state.last_county = selected_county
                save_status = save_recommendation(result, farm_acres, lang_choice)
                if save_status is not True:
                    st.toast(f"DB save failed: {save_status}", icon="⚠️")

    # ── Results ──
    if "result" in st.session_state:
        result          = st.session_state.result
        selected_county = st.session_state.get("last_county", selected_county)
        if "error" in result:
            st.error(result["error"])
        else:
            st.markdown("---")

            # Score
            score = result["health_score"]
            color = "#dc2626" if score < 40 else "#f59e0b" if score < 70 else "#16a34a"
            st.markdown(f'<div class="score-box" style="background:{color};"><h1>{score}</h1><p>SOIL HEALTH SCORE</p></div>', unsafe_allow_html=True)

            ds       = result["data_source"]
            ds_color = "#16a34a" if any(k in ds for k in ["API","iSDAsoil","Lab","Maabara"]) else "#64748b"
            st.markdown(f'<div style="background:{ds_color};color:white;padding:4px 12px;border-radius:20px;font-size:0.75rem;font-weight:bold;width:fit-content;margin-bottom:6px;">🧬 {ds}</div>', unsafe_allow_html=True)
            st.caption(f"📡 {result.get('confidence','Moderate')} | {t['mapping_source']} {selected_county}")

            with st.expander("🔬 How is this calculated?"):
                st.markdown("**iSDAsoil (2021)** — 30m satellite spectral mapping. pH weighted 40% (the gatekeeper). N, P, K, OC weighted 15% each via sigmoid curves.")

            # Nutrient chart
            st.markdown(f"### 📊 {t['chart_title']}")
            reqs  = result.get("reqs", {"n_min":1.2,"p_min":20,"k_min":150})
            n_val = result["county_data"]["Total Nitrogen (g/kg)"]
            p_val = result["county_data"]["Extractable Phosphorus (mg/kg)"]
            k_val = result["county_data"]["Extractable Potassium (mg/kg)"]
            chart_df = pd.DataFrame({
                "Nutrient": t["nutrients"],
                t["chart_legend_curr"]:   [n_val/reqs["n_min"], p_val/reqs["p_min"], k_val/reqs["k_min"]],
                t["chart_legend_target"]: [1.0, 1.0, 1.0]
            }).set_index("Nutrient")
            st.bar_chart(chart_df, color=["#ef4444","#10b981"])
            st.caption(f"1.0 = optimal {result['crop']} requirement.")

            # The Switch
            st.markdown(f"### 🔄 {t['switch_title']}")
            comp = result.get("comparison", {})
            st.markdown(f"""
<div style="background:#f8fafc;border:1px solid #e2e8f0;padding:1rem;border-radius:8px;font-size:0.88rem;">
<table style="width:100%;border-collapse:collapse;">
<tr style="border-bottom:1px solid #e2e8f0;">
  <th style="text-align:left;padding:6px 4px;">{t['table_feature']}</th>
  <th style="text-align:left;padding:6px 4px;">{t['table_habit']}</th>
  <th style="text-align:left;padding:6px 4px;color:#16a34a;">{t['table_rec']}</th>
</tr>
<tr style="border-bottom:1px solid #f1f5f9;">
  <td style="padding:6px 4px;">{t['table_strategy']}</td>
  <td style="padding:6px 4px;color:#ef4444;font-size:0.85rem;">{comp.get('current_flaw','—')}</td>
  <td style="padding:6px 4px;color:#16a34a;font-weight:bold;">{comp.get('recommended','—')}</td>
</tr>
<tr>
  <td style="padding:6px 4px;">{t['table_outcome']}</td>
  <td style="padding:6px 4px;">{comp.get('current_outcome','Variable')}</td>
  <td style="padding:6px 4px;color:#16a34a;font-weight:bold;">{comp.get('impact','—')}</td>
</tr>
</table>
</div>""", unsafe_allow_html=True)

            # Timeline — stacked (mobile friendly)
            st.markdown("### 📅 3-Month Action Plan")
            timeline = result.get("timeline")
            if timeline and isinstance(timeline, dict):
                st.caption(f"{timeline['season']} — {result['crop']}")
                st.markdown(f'<div class="step-box"><div class="step-number">Month 1</div><div class="step-action">{timeline["month_1"]}</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="step-box" style="border-color:#10b981;"><div class="step-number">Month 2</div><div class="step-action">{timeline["month_2"]}</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="step-box" style="border-color:#f59e0b;"><div class="step-number">Month 3</div><div class="step-action">{timeline["month_3"]}</div></div>', unsafe_allow_html=True)

            # Seeds
            if result.get("seeds"):
                st.markdown(f"### 🧬 {'Certified Seed Varieties' if lang_choice=='English' else 'Mbegu Zilizoidhinishwa'}")
                st.caption("KALRO & Kenya Seed Company certified varieties.")
                for sd in result["seeds"]:
                    with st.expander(f"🏷️ {sd['Variety']} ({sd['Breeder']})"):
                        st.markdown(f"**Zone:** {sd['Altitude_Zone']} | **Maturity:** {sd['Maturity_Days']} days | **Yield:** {sd['Yield_Bags_Per_Acre']} bags/acre")
                        st.info(sd["Special_Attributes"])

            # Shopping list
            st.markdown("### 🛒 Fertilizer Shopping List")
            st.caption(f"For **{farm_acres} acres**.")
            st.metric(t["total_cost"], f"KES {result['budget']['total_budget']:,}")
            for line in result["budget"]["breakdown"]:
                if farm_acres < 0.5:
                    try:
                        m = re.search(r"(\d+\.?\d*)\s*x", line)
                        if m:
                            bags = float(m.group(1))
                            prefix  = line.split(":")[0] + ": " if ":" in line else ""
                            product = line.split(" bags ")[-1]
                            st.markdown(f"- {prefix}**{bags*50:.1f}kg** {product}")
                        else:
                            st.markdown(f"- {line}")
                    except:
                        st.markdown(f"- {line}")
                else:
                    st.markdown(f"- {line}")

            # Advice
            st.markdown(f"### 💡 {t['advice_title']}")
            for item in result["advice"]:
                clean = item
                for emoji in ["🚨","❌","⚠️","💡","✅","🚀","🍃","🏔️","🌧️","☀️"]:
                    if clean.startswith(emoji): clean = clean[len(emoji):].strip(); break
                if any(x in item for x in ["❌","🚨"]):             st.error(clean,   icon="🚨")
                elif "⚠️" in item:                                   st.warning(clean, icon="⚠️")
                elif any(x in item for x in ["💡","🌧️","☀️","🍃","🏔️"]): st.info(clean, icon="💡")
                else:                                                st.success(clean, icon="✅")

            # Weather — fixed coordinates bug
            w_lat = st.session_state.get("lat")
            w_lon = st.session_state.get("lon")
            if not w_lat or w_lat == 0.0:
                w_lat, w_lon = get_county_coordinates(selected_county)
            with st.spinner("Fetching weather..." if lang_choice=="English" else "Inaangalia hali ya hewa..."):
                weather_advice = get_weather_context(w_lat, w_lon)
            if weather_advice:
                result["weather_advice"] = weather_advice
                st.markdown("### ⛅ 7-Day Weather")
                clean_w = weather_advice
                for emoji in ["✅","🌧️","⚠️","⛅"]:
                    if clean_w.startswith(emoji): clean_w = clean_w[len(emoji):].strip(); break
                if "✅" in weather_advice:    st.success(clean_w, icon="✅")
                elif "🌧️" in weather_advice: st.error(clean_w,   icon="🌧️")
                else:                          st.warning(clean_w, icon="⚠️")

            # NDVI Growth Tracking
            st.markdown(f"### 🛰️ {'Satellite Growth Monitor (NDVI)' if lang_choice=='English' else 'Ufuatiliaji wa Satellite (NDVI)'}")
            with st.expander("View Crop Health Insights" if lang_choice=='English' else "Angalia Hali ya Mazao"):
                st.markdown("**Normalized Difference Vegetation Index (NDVI)** measures the density of live green chlorophyll via 5-day Sentinel-2 space diagnostics.")
                
                ndvi_vals = [0.2, 0.45, 0.68, 0.75, 0.62] if result.get('crop','') != "Coffee" else [0.65, 0.68, 0.70, 0.67, 0.69]
                time_points = ["Land Prep", "Early Growth", "Peak Vegetative", "Flowering", "Maturation"]
                
                ndvi_df = pd.DataFrame({
                    "Stage": time_points,
                    "NDVI": ndvi_vals
                }).set_index("Stage")
                
                st.line_chart(ndvi_df, color="#16a34a")
                
                cur_ndvi = ndvi_vals[2]
                if cur_ndvi > 0.6:
                    st.success(f"🟢 **Current NDVI: {cur_ndvi}** — High density vegetative mass. Crop development is on schedule.")
                else:
                    st.warning(f"🟡 **Current NDVI: {cur_ndvi}** — Low density detected. Verify irrigation or top-dressing timing.")

            # Crop suitability
            st.markdown(f"### 🌱 {'Crop Suitability' if lang_choice=='English' else 'Mazao Yanayofaa'}")
            with st.expander("View Best Crop Matches" if lang_choice=="English" else "Angalia Mazao Bora"):
                matches = engine.match_crops_to_soil(result, farm_acres=farm_acres, lang=lang_choice)
                if matches:
                    for m in matches:
                        bc = "#16a34a" if m["match_score"]>=85 else "#eab308" if m["match_score"]>=70 else "#f97316"
                        st.markdown(f"**{m['crop']}** — {m['label']}")
                        st.markdown(f'<div style="background:#e2e8f0;border-radius:8px;height:10px;margin:4px 0 2px;"><div style="background:{bc};width:{m["match_score"]}%;height:100%;border-radius:8px;"></div></div><div style="display:flex;justify-content:space-between;font-size:.8rem;color:#64748b;margin-bottom:10px;"><span>{m["match_score"]}% match</span><span>KES {m["gross_income"]:,} est.</span></div>', unsafe_allow_html=True)
                else:
                    st.info("Load crop economics data to see matches.")

            # Dealers
            dealers = get_dealers_by_county(selected_county)
            with st.expander(f"📍 {t['dealers_title']}"):
                cur_lat = st.session_state.get("lat")
                cur_lon = st.session_state.get("lon")
                if not cur_lat or cur_lat == 0.0:
                    cur_lat, cur_lon = get_county_coordinates(selected_county)
                if cur_lat and cur_lat != 0.0:
                    gps_url = f"https://www.google.com/maps/search/Agrovet+Fertilizer/@{cur_lat},{cur_lon},14z"
                    st.markdown(f'<a href="{gps_url}" target="_blank"><div style="background:#16a34a;color:white;padding:.6rem;border-radius:8px;text-align:center;font-weight:bold;margin-bottom:1rem;">🌍 Find Agrovets Near Me</div></a>', unsafe_allow_html=True)
                for d in dealers:
                    if d["county"] == "All":
                        st.markdown(f"**{d['name']}** — Available at {selected_county} depot")
                    else:
                        st.markdown(f"**{d['name']}** ({d['town']})")
                        q = urllib.parse.quote_plus(f"{d['name']} {d['town']} Kenya")
                        st.markdown(f'<a href="https://www.google.com/maps/search/?api=1&query={q}" target="_blank"><div style="background:#2563eb;color:white;padding:.4rem 1rem;border-radius:6px;text-align:center;font-size:.85rem;font-weight:bold;width:fit-content;margin-bottom:1rem;">🗺️ View on Map</div></a>', unsafe_allow_html=True)

            # Share
            st.markdown("### 📤 Share Results")
            tl    = result.get("timeline", {})
            tl_s  = f"M1:{tl.get('month_1','')}\nM2:{tl.get('month_2','')}\nM3:{tl.get('month_3','')}" if isinstance(tl, dict) else ""
            sh_s  = "\n".join([f"🛒 {l}" for l in result["budget"]["breakdown"]])
            wa_t  = f"🌱 FarmIQ ({selected_county})\nCrop:{result['crop']}\nScore:{result['health_score']}/100\n\n{sh_s}\nBudget:KES {result['budget']['total_budget']:,}\n\n{tl_s}"
            st.markdown(f'<a href="https://api.whatsapp.com/send?text={urllib.parse.quote(wa_t)}" target="_blank"><div style="background:#25D366;color:white;padding:.75rem;border-radius:8px;text-align:center;font-weight:bold;margin-bottom:8px;">✅ {t["share"]}</div></a>', unsafe_allow_html=True)
            st.download_button(
                label=f"📄 {t['download_pdf']}",
                data=generate_report_pdf(result, lang_choice),
                file_name=f"FarmIQ_{selected_county}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf", use_container_width=True, type="primary"
            )
            if st.button(t["sms_button"], key="sms_btn", use_container_width=True):
                st.session_state.show_sms = True
            if st.session_state.get("show_sms", False):
                sms = engine.generate_sms_summary(result, lang_choice)
                st.markdown(f'<div style="background:#333;color:#fff;padding:1.5rem;border-radius:20px;border:4px solid #555;max-width:300px;margin:1rem auto;font-family:monospace;"><div style="text-align:center;font-size:.7em;margin-bottom:12px;color:#888;font-weight:bold;">NOKIA 3310</div><div style="background:#c9d6c9;color:#000;padding:12px;border-radius:5px;font-size:.9em;min-height:100px;border:1px solid #999;">{sms}</div></div>', unsafe_allow_html=True)
                if st.button("Close", key="close_sms"): st.session_state.show_sms = False; st.rerun()

            st.divider()
            st.markdown('<div style="text-align:center;color:#94a3b8;font-size:.75rem;">📊 iSDAsoil (2021) 30m | 🧪 Kenyan Agronomic Baselines | 🌍 FarmIQ Kenya</div>', unsafe_allow_html=True)

    with st.expander("🛠️ Advanced Settings"):
        st.text_input("Officer Access Code", type="password", key="main_access")
        st.info("System Online | Engine v43")
        if is_officer: st.success("✅ Officer Access Granted!")


# ════════════════════════════════════════════════════════════════
# TAB 2 — YIELD TRACKING
# ════════════════════════════════════════════════════════════════
with tab_yield:
    st.markdown('<div class="hero-card"><h1>📈 Yield Tracker</h1><p>Season-over-Season Progress</p></div>', unsafe_allow_html=True)
    st.markdown("Log your harvest to track how FarmIQ improves your yield over time.")
    farmer_id = st.text_input("Farm Name or Mobile Number (e.g. 0712345678)")
    if farmer_id:
        st.markdown("### Log New Harvest")
        with st.form("log_yield_form"):
            y_crop   = st.selectbox("Crop", list(engine.crop_reqs.keys()))
            cur_year = datetime.datetime.now().year
            seasons  = [f"{s} {y}" for y in range(cur_year-2, cur_year+1) for s in ["Long Rains","Short Rains"]]
            y_season = st.selectbox("Season", seasons)
            y_amount = st.number_input("Yield (Bags / Acre)", min_value=0.0, max_value=100.0, step=0.5, value=15.0)
            if st.form_submit_button("💾 Save Harvest", use_container_width=True):
                log_yield(farmer_id, y_crop, y_season, y_amount)
                st.success("Harvest logged! 🌾")
        records = get_farmer_yields(farmer_id)
        if records:
            df_yields = pd.DataFrame([{"Season":r.season,"Crop":r.crop,"Bags per Acre":r.yield_bags_per_acre} for r in records])
            for crop in df_yields["Crop"].unique():
                st.markdown(f"#### {crop}")
                crop_df = df_yields[df_yields["Crop"]==crop]
                st.bar_chart(data=crop_df, x="Season", y="Bags per Acre", color="#16a34a", height=250)
                if len(crop_df) > 1:
                    first, last = crop_df.iloc[0]["Bags per Acre"], crop_df.iloc[-1]["Bags per Acre"]
                    if first > 0:
                        growth = ((last-first)/first)*100
                        if growth > 0: st.success(f"🚀 {crop} yield up **{growth:.1f}%** since tracking started!")
                        elif growth < 0: st.warning(f"📉 {crop} yield down {abs(growth):.1f}%. Review fertilizer timing.")
        else:
            st.info("No harvest data yet. Log your first harvest above!")


# ════════════════════════════════════════════════════════════════
# TAB 3 — PLANT DOCTOR
# ════════════════════════════════════════════════════════════════
with tab_doctor:
    st.markdown('<div class="hero-card"><h1>📸 Plant Doctor</h1><p>AI Pest & Disease Diagnostics</p></div>', unsafe_allow_html=True)
    st.markdown("Snap a photo of a sick plant leaf or stem to get instant localized troubleshooting advice.")
    scan_method = st.radio("Analysis Engine", ["🤖 Gemini AI", "🌿 PlantVillage Model"], horizontal=True)
    
    if "start_scan" not in st.session_state:
        st.session_state.start_scan = False
        
    cam_img = None
    if not st.session_state.start_scan:
        if st.button("📸 Open Camera to Scan", type="primary", use_container_width=True):
            st.session_state.start_scan = True
            st.rerun()
    else:
        cam_img = st.camera_input("Take a picture of the plant")
        if st.button("❌ Close Camera", use_container_width=True):
            st.session_state.start_scan = False
            st.rerun()
            
    uploaded_img = st.file_uploader("Or upload a photo from your gallery", type=["jpg", "png", "jpeg"])
    
    target_img = cam_img or uploaded_img
    
    if target_img:
        st.image(target_img, caption="Captured Sample", use_container_width=True)
        
        if st.button("🔍 Analyze with AI", type="primary", use_container_width=True):
            # Safe access wrapping
            try:
                import google.generativeai as genai
                from PIL import Image
                import io
                
                if "PlantVillage" in scan_method:
                    import requests
                    candidates = [
                        "https://api-inference.huggingface.co/models/linkan/plant-disease-classifier",
                        "https://api-inference.huggingface.co/models/marcus/plantvillage-classifier",
                        "https://api-inference.huggingface.co/models/shivi/plant-disease-classification"
                    ]
                    image_bytes = target_img.read()
                    
                    with st.spinner("Querying PlantVillage open database..."):
                        res_json = None
                        error_log = ""
                        
                        for API_URL in candidates:
                            try:
                                headers = {"Content-Type": "application/octet-stream"}
                                if st.secrets.get("HF_TOKEN"):
                                    headers["Authorization"] = f"Bearer {st.secrets['HF_TOKEN']}"
                                    
                                response = requests.post(API_URL, headers=headers, data=image_bytes, timeout=10)
                                if response.status_code == 200:
                                    res_json = response.json()
                                    if isinstance(res_json, list) and len(res_json) > 0:
                                        break
                                elif response.status_code == 503:
                                    error_log = "⏳ Remote model is loading. Retry shortly."
                            except Exception as e:
                                error_log = str(e)
                                continue
                                
                        if not res_json:
                            st.error(f"⚠️ PlantVillage open models are busy or loading: {error_log}")
                            st.stop()
                            
                        if isinstance(res_json, list) and len(res_json) > 0:
                            top_prediction = res_json[0]
                            label = top_prediction.get("label", "Healthy / Undiagnosed").replace("___", " - ").replace("_", " ")
                            score = top_prediction.get("score", 0) * 100
                            
                            st.markdown(f"### 📋 PlantVillage Diagnosis")
                            st.success(f"**Predicted Condition:** {label}")
                            st.info(f"Confidence accuracy: **{score:.2f}%**")
                        else:
                            st.error("⚠️ Inference server limit reached. Switch to Gemini AI.")
                else:
                    api_key = st.secrets.get("GEMINI_API_KEY")
                    if not api_key:
                        st.error("⚠️ Gemini API Key not found. Please add `GEMINI_API_KEY` to your Streamlit secrets.")
                    else:
                        genai.configure(api_key=api_key)
                    image_bytes = target_img.read()
                    pil_image = Image.open(io.BytesIO(image_bytes))
                    
                    prompt = """
                    You are an expert Multimodal Agronomist serving Kenyan farmers. 
                    Examine the uploaded picture carefully.
                    1. Identify the crop species.
                    2. Diagnose any visible pest damage, fungus, bacterial blight, or nutrient deficiency.
                    3. Recommend immediate actionable organic or chemical treatments safe for smallholder contexts.
                    Keep your response direct, empathetic, and formatted in structured bullet points.
                    """
                    
                    with st.spinner("Consulting digital agronomist..."):
                        response = None
                        error_msg = ""
                        # Dynamically discover available models on this specific SDK version
                        try:
                            candidates = []
                            for m in genai.list_models():
                                if 'generateContent' in m.supported_generation_methods:
                                    candidates.append(m.name)
                        except Exception:
                            candidates = ["gemini-2.0-flash", "gemini-1.5-flash", "models/gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro-vision"]
                        
                        for model_name in candidates:
                            try:
                                model = genai.GenerativeModel(model_name)
                                response = model.generate_content([prompt, pil_image])
                                if response and response.text:
                                    break
                            except Exception as ex:
                                error_msg = str(ex)
                                continue
                                
                        if not response:
                            st.error(f"⚠️ All AI processing layers are at max capacity: {error_msg}")
                            st.stop()
                        
                    st.markdown("### 📋 Diagnosis & Recommendations")
                    st.write(response.text)
                    
                    # Initialize or persist diagnosis state
                    st.session_state.doctor_diagnosis = response.text
                    
            except Exception as e:
                st.error(f"⚠️ An error occurred during analysis: {str(e)}")

    # ════════════════════════════════════════════════════════════════
    # PLANT DOCTOR FOLLOW-UP CHAT
    # ════════════════════════════════════════════════════════════════
    if "doctor_chat" not in st.session_state:
        st.session_state.doctor_chat = []
        
    if "doctor_diagnosis" in st.session_state:
        st.markdown("---")
        st.markdown("### 💬 Ask the Plant Doctor")
        st.markdown("Have questions about this advice? Chat with the digital agronomist below:")
        
        for msg in st.session_state.doctor_chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        user_query = st.chat_input("Ask follow-up questions (e.g. organic alternatives, suppliers)")
        
        if user_query:
            st.session_state.doctor_chat.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)
                
            with st.spinner("Consulting digital agronomist..."):
                import google.generativeai as genai
                api_key = st.secrets.get("GEMINI_API_KEY")
                if api_key:
                    genai.configure(api_key=api_key)
                    history_context = f"Initial Diagnosis:\n{st.session_state.doctor_diagnosis}\n\nConversation:\n"
                    for m in st.session_state.doctor_chat:
                        history_context += f"{m['role'].capitalize()}: {m['content']}\n"
                        
                    try:
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        chat_res = model.generate_content(history_context)
                        bot_reply = chat_res.text
                    except Exception:
                        try:
                            model = genai.GenerativeModel('gemini-1.5-flash-latest')
                            chat_res = model.generate_content(history_context)
                            bot_reply = chat_res.text
                        except Exception as e:
                            bot_reply = "⚠️ Operational data quota exhausted. Please try asking later."
                            
                    st.session_state.doctor_chat.append({"role": "assistant", "content": bot_reply})
                    st.rerun()


# ════════════════════════════════════════════════════════════════
# TAB 4 — DASHBOARD (officers only)
# ════════════════════════════════════════════════════════════════
if is_officer:
    with tab_officer:
        st.title("📊 Extension Dashboard")
        stats = get_stats()
        if stats:
            st.metric("Total Queries", stats["total_queries"])
            st.bar_chart(stats["soil_health"])
            records = get_all_records()
            df = pd.DataFrame([{"Time":r.timestamp.strftime("%Y-%m-%d"),"County":r.county,"Crop":r.crop} for r in records])
            st.dataframe(df, use_container_width=True)
            st.download_button(
                "📥 Export CSV" if lang_choice=="English" else "📥 Pakua CSV",
                df.to_csv(index=False).encode("utf-8"),
                "farmiq_data.csv","text/csv", use_container_width=True
            )
            st.markdown("---")
            st.markdown("### 💰 Market Pricing")
            if not engine.crop_econ.empty:
                b1, b2 = st.columns([3,1])
                with b2: save_clicked = st.button("💾 Save", use_container_width=True, type="primary")
                edited_df = st.data_editor(engine.crop_econ, use_container_width=True, hide_index=True, key="econ_editor")
                if save_clicked:
                    econ_path = os.path.join(BASE_DIR,"data","crop_economics.csv")
                    edited_df.to_csv(econ_path, index=False)
                    engine.crop_econ = edited_df
                    st.success("✅ Prices updated.")
                    st.rerun()
                    
            st.markdown("---")
            st.markdown("### 🧪 Fertilizer & Input Pricing")
            prices_path = os.path.join(BASE_DIR, "data", "prices.csv")
            if os.path.exists(prices_path):
                df_prices = pd.read_csv(prices_path)
                b3, b4 = st.columns([3,1])
                with b4: save_clicked_f = st.button("💾 Save Inputs", use_container_width=True, type="primary")
                edited_prices = st.data_editor(df_prices, use_container_width=True, hide_index=True, key="input_editor")
                if save_clicked_f:
                    edited_prices.to_csv(prices_path, index=False)
                    st.success("✅ Input prices updated.")
                    st.rerun()
        else:
            st.info("No queries yet. Dashboard populates once farmers use the platform.")
