import pandas as pd
import numpy as np
import os
import requests
import datetime
import streamlit as st

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_isda_data(lat, lon, token):
    properties = [
        "nitrogen_total",
        "phosphorus_extractable",
        "potassium_extractable",
        "ph",
        "organic_carbon",
        "aluminium_extractable",
        "zinc_extractable",
        "sulphur_extractable",
        "calcium_extractable",
        "magnesium_extractable",
        "cation_exchange_capacity",
        "texture_class"
    ]

    base_url = "https://api.isda-africa.com/isdasoil/v2/soilproperty"
    headers = {"Authorization": f"Bearer {token}"}
    results = {}

    for prop in properties:
        try:
            response = requests.get(
                base_url,
                headers=headers,
                params={
                    "lat": lat,
                    "lon": lon,
                    "property": prop,
                    "depth": "0-20"
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                prop_data = data.get("property", {}).get(prop, [])
                if prop_data and len(prop_data) > 0:
                    value = prop_data[0].get("value", {}).get("value")
                    if value is not None:
                        results[prop] = value if isinstance(value, str) else float(value)
                    
                    # Extract uncertainty (90% confidence)
                    uncertainty = prop_data[0].get("uncertainty")
                    if uncertainty and isinstance(uncertainty, list):
                        for uc in uncertainty:
                            if uc.get("confidence_interval") == "90%":
                                results[f"{prop}_lower"] = uc.get("lower_bound")
                                results[f"{prop}_upper"] = uc.get("upper_bound")
        except Exception:
            continue

    return results if results else None


class FarmIQRecommender:
    def __init__(self, soil_data_path):
        """Initialize with path to the county soil dataset."""
        self.soil_data = pd.read_csv(soil_data_path)
        self.data_dir = os.path.dirname(soil_data_path)
        
        # Load crop requirements from CSV (editable without touching code)
        crop_req_path = os.path.join(self.data_dir, "crop_requirements.csv")
        self.crop_reqs = {}
        if os.path.exists(crop_req_path):
            cr_df = pd.read_csv(crop_req_path)
            for _, row in cr_df.iterrows():
                self.crop_reqs[row["Crop"]] = {
                    "ph_min": row["ph_min"], "n_min": row["n_min"],
                    "p_min": row["p_min"], "k_min": row["k_min"],
                    "oc_min": row.get("oc_min", 15.0),
                    "foliar": int(row.get("foliar", 0)),
                    "zn_min": row.get("zn_min", 1.0)
                }
        if not self.crop_reqs:
            self.crop_reqs = {"Maize": {"ph_min": 5.5, "n_min": 1.2, "p_min": 20, "k_min": 150, "oc_min": 15.0, "foliar": 0, "zn_min": 1.0}}
        
        # Load Crop Calendars
        self.crop_calendars = pd.DataFrame()
        cal_path = os.path.join(self.data_dir, 'crop_calendars.csv')
        if os.path.exists(cal_path):
            self.crop_calendars = pd.read_csv(cal_path)

        # Load Top Dressing Rules
        self.top_dress_rules = pd.DataFrame()
        td_path = os.path.join(self.data_dir, 'top_dressing.csv')
        if os.path.exists(td_path):
            self.top_dress_rules = pd.read_csv(td_path)
            
        # Load Comparison Reasons
        self.comp_reasons = pd.DataFrame()
        cr_path = os.path.join(self.data_dir, 'comparison_reasons.csv')
        if os.path.exists(cr_path):
            self.comp_reasons = pd.read_csv(cr_path)
        
        
        # Load county centroids from CSV (editable without touching code)
        coords_path = os.path.join(self.data_dir, "county_coordinates.csv")
        self.COUNTY_CENTROIDS = {}
        if os.path.exists(coords_path):
            cc_df = pd.read_csv(coords_path)
            for _, row in cc_df.iterrows():
                self.COUNTY_CENTROIDS[row["County"]] = [row["Latitude"], row["Longitude"]]
        
        # Load prices from CSV (editable without touching code)
        prices_path = os.path.join(self.data_dir, "prices.csv")
        self.PRICES = {"Subsidized": {}, "Commercial": {}}
        
        # Load Crop Economics for Reverse Recommendation
        self.crop_econ = pd.DataFrame()
        econ_path = os.path.join(self.data_dir, "crop_economics.csv")
        if os.path.exists(econ_path):
            self.crop_econ = pd.read_csv(econ_path)

        if os.path.exists(prices_path):
            pr_df = pd.read_csv(prices_path)
            for _, row in pr_df.iterrows():
                self.PRICES["Subsidized"][row["Fertilizer"]] = int(row["Subsidized"])
                self.PRICES["Commercial"][row["Fertilizer"]] = int(row["Commercial"])
        if not self.PRICES["Subsidized"]:
            # Fallback
            self.PRICES = {
                "Subsidized": {"DAP": 2500, "CAN": 2500, "NPK 17:17:17": 2500, "Urea": 2500, "Lime": 1500, "Mavuno": 2500, "SSP": 2500, "YaraMila Cereal": 3500, "Ammonium Sulphate": 2500, "TSP": 2800, "Foliar Feed (1L)": 1000},
                "Commercial": {"DAP": 6500, "CAN": 4500, "NPK 17:17:17": 5600, "Urea": 5500, "Lime": 1800, "Mavuno": 5800, "SSP": 5200, "YaraMila Cereal": 7200, "Ammonium Sulphate": 4800, "TSP": 6200, "Foliar Feed (1L)": 1400}
            }
    
    def detect_county(self, lat, lon):
        """Finds the nearest county centroid for a given lat/lon."""
        best_county = None
        min_dist = float('inf')
        for c, coords in self.COUNTY_CENTROIDS.items():
            dist = np.sqrt((lat - coords[0])**2 + (lon - coords[1])**2)
            if dist < min_dist:
                min_dist = dist
                best_county = c
        
        if min_dist > 5.0:
            return "Outside Kenya"
        return best_county if best_county else "Unknown"
    
    def get_county_data(self, county_name):
        data = self.soil_data[self.soil_data["County"] == county_name]
        if data.empty:
            return None
        return data.iloc[0].to_dict()

    def _get_isda_token(self):
        """Authenticate with iSDA API and return a JWT token."""
        username, password = None, None
        try:
            import streamlit as st
            username = st.secrets["ISDA_USERNAME"]
            password = st.secrets["ISDA_PASSWORD"]
        except Exception:
            username = os.environ.get("ISDA_USERNAME")
            password = os.environ.get("ISDA_PASSWORD")

        if not username or not password:
            return None

        try:
            resp = requests.post(
                "https://api.isda-africa.com/login",
                data={"username": username, "password": password},
                timeout=15
            )
            if resp.status_code == 200:
                return resp.json().get("access_token")
        except Exception:
            pass
        return None

    def get_isda_nutrients(self, lat, lon):
        """
        Fetches real-time soil properties.
        PRIORITY: ISRIC/SoilGrids (for verification) -> iSDA fallback.
        """
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            return None

        # TIER 1: ISRIC/SoilGrids (Now Primary for Verification)
        try:
            from soil_providers import FallbackProvider
            provider = FallbackProvider()
            # Explicitly use SoilGridsProvider if we want to ensure ISRIC
            from soil_providers import SoilGridsProvider
            isric = SoilGridsProvider()
            pub = isric.get_soil_properties(lat, lon)
            if pub:
                return {
                    "ph": pub.get("pH"),
                    "nitrogen_total": pub.get("Total Nitrogen (g/kg)"),
                    "phosphorus_extractable": pub.get("Extractable Phosphorus (mg/kg)"),
                    "potassium_extractable": pub.get("Extractable Potassium (mg/kg)"),
                    "organic_carbon": pub.get("Organic Carbon (g/kg)"),
                    "data_source_override": "ISRIC/SoilGrids (Global 250m)"
                }
        except Exception:
            pass

        # TIER 2: iSDA V2 (Fallback)
        token = self._get_isda_token()
        if token:
            res = _fetch_isda_data(lat, lon, token)
            if res and "ph" in res:
                return res

        return None

    def calculate_health_score(self, soil, reqs):
        """Calculates a scientifically realistic soil quality index (SQI)."""
        def sig(x, x_crit):
            return 1 / (1 + np.exp(-5 * (x/x_crit - 0.5)))
        ph = soil["pH"]
        s_ph = np.exp(-(ph - 6.5)**2 / 2.0) 
        s_n = sig(soil["Total Nitrogen (g/kg)"], reqs["n_min"])
        s_p = sig(soil["Extractable Phosphorus (mg/kg)"], reqs["p_min"])
        s_k = sig(soil["Extractable Potassium (mg/kg)"], reqs["k_min"])
        s_oc = sig(soil["Organic Carbon (g/kg)"], reqs["oc_min"])
        final_score = (s_ph * 0.4 + s_n * 0.15 + s_p * 0.15 + s_k * 0.15 + s_oc * 0.15) * 100
        return int(np.clip(final_score, 0, 100))

    def generate_recommendation(self, county, crop, current_fert, farm_size_acres=1.0, lang="English", lat=None, lon=None, overrides=None, price_mode="Subsidized", is_subcounty=False, yield_target=1.0):
        """Generates localized advice with cost modeling and iSDAsoil fallback"""
        # Ensure we have data for the county
        if county not in self.soil_data["County"].values:
            return {"error": f"County {county} not found in database."}
        
        import datetime
        if lat and lon and (not county or county == "Detecting..."):
            county = self.detect_county(lat, lon)
        
        soil = self.get_county_data(county)
        if not soil:
            return {"error": "Location data not found." if lang == "English" else "Data ya eneo haijapatikana."}
        
        # Apply yield target scaling securely
        base_reqs = self.crop_reqs.get(crop, self.crop_reqs["Maize"])
        reqs = base_reqs.copy()
        reqs["n_min"] = base_reqs.get("n_min", 0.0) * yield_target
        reqs["p_min"] = base_reqs.get("p_min", 0.0) * yield_target
        reqs["k_min"] = base_reqs.get("k_min", 0.0) * yield_target

        # High-Resolution Override (3-tier fallback chain)
        data_source = "Regional Baseline (CSV)" if lang == "English" else "Msingi wa Eneo (CSV)"
        confidence = "Moderate 🟡 (Based on ~100+ historical regional samples)"
        
        # TIER 1: iSDAsoil API — High Resolution Override
        if lat and lon:
            isda_data = self.get_isda_nutrients(lat, lon)
            if isda_data:
                # Explicit Bridge (API Keys -> Engine Keys)
                if "ph" in isda_data:
                    soil["pH"] = isda_data["ph"]
                    soil["pH_bounds"] = (isda_data.get("ph_lower"), isda_data.get("ph_upper"))
                if "nitrogen_total" in isda_data:
                    soil["Total Nitrogen (g/kg)"] = isda_data["nitrogen_total"]
                    soil["N_bounds"] = (isda_data.get("nitrogen_total_lower"), isda_data.get("nitrogen_total_upper"))
                if "phosphorus_extractable" in isda_data:
                    soil["Extractable Phosphorus (mg/kg)"] = isda_data["phosphorus_extractable"]
                if "potassium_extractable" in isda_data:
                    soil["Extractable Potassium (mg/kg)"] = isda_data["potassium_extractable"]
                if "organic_carbon" in isda_data:
                    soil["Organic Carbon (g/kg)"] = isda_data["organic_carbon"]
                if "aluminium_extractable" in isda_data:
                    soil["Aluminium (ppm)"] = isda_data["aluminium_extractable"]
                if "zinc_extractable" in isda_data:
                    soil["Zinc (ppm)"] = isda_data["zinc_extractable"]
                if "sulphur_extractable" in isda_data:
                    soil["Sulfur (ppm)"] = isda_data["sulphur_extractable"]
                if "calcium_extractable" in isda_data:
                    soil["Calcium (ppm)"] = isda_data["calcium_extractable"]
                if "magnesium_extractable" in isda_data:
                    soil["Magnesium (ppm)"] = isda_data["magnesium_extractable"]
                if "cation_exchange_capacity" in isda_data:
                    soil["CEC (meq/100g)"] = isda_data["cation_exchange_capacity"]
                if "texture_class" in isda_data:
                    soil["Texture"] = isda_data["texture_class"]
                
                data_source = isda_data.get("data_source_override", "iSDAsoil API (30m Full Spectrum)") if lang == "English" else isda_data.get("data_source_override", "API ya iSDAsoil (30m Kamili)")
                confidence = "High 🟢 (Precision Satellite mapping)" if "ISRIC" in data_source else "Very High 🟢 (All nutrients at 30m via iSDAsoil API)"
            
        if overrides:
            for key in ["pH", "Total Nitrogen (g/kg)", "Extractable Phosphorus (mg/kg)", "Extractable Potassium (mg/kg)"]:
                if key in overrides and overrides[key] is not None:
                    soil[key] = overrides[key]
            data_source = "Lab Override (Ground Truth)" if lang == "English" else "Matokeo ya Maabara"
            confidence = "Maximum 🔵 (Ground truth lab data)"

        # --- SCIENTIFIC CONSTANTS: FERTILIZER ANALYSIS (%) ---
        # Used to convert mg/kg gaps into exact bag counts (50kg)
        ANALYSIS = {
            "DAP": {"N": 0.18, "P": 0.46, "K": 0.0},
            "CAN": {"N": 0.26, "P": 0.0, "K": 0.0},
            "Urea": {"N": 0.46, "P": 0.0, "K": 0.0},
            "NPK 17:17:17": {"N": 0.17, "P": 0.17, "K": 0.17},
            "Mavuno": {"N": 0.10, "P": 0.26, "K": 0.10},
            "SSP": {"N": 0.0, "P": 0.20, "K": 0.0},
            "YaraMila Cereal": {"N": 0.23, "P": 0.23, "K": 0.0},
            "NPK 26:5:5": {"N": 0.26, "P": 0.05, "K": 0.05},
            "Ammonium Sulphate": {"N": 0.21, "P": 0.0, "K": 0.0}
        }

        # --- SCIENTIFIC LOGIC: NUTRIENT GAP CALCULATION ---
        mp = self.PRICES.get(price_mode, self.PRICES["Subsidized"])

        advice = []
        breakdown = []
        total_cost = 0

        # Seasonal Context
        month = datetime.datetime.now().month
        season_en = "Dry Season"
        season_sw = "Kiangazi"
        if 3 <= month <= 5: 
            season_en = "Long Rains"
            season_sw = "Mvua za masika"
            advice.append("🌧️ **Season**: Long Rains. Plan for early planting." if lang == "English" else "🌧️ **Msimu**: Mvua za masika. Panda mapema.")
        elif 10 <= month <= 12:
            season_en = "Short Rains"
            season_sw = "Mvua fupi"
            advice.append("🌧️ **Season**: Short Rains. Fast maturing recommended." if lang == "English" else "🌧️ **Msimu**: Mvua fupi. Mbegu zinazokomaa haraka.")
        else:
            advice.append("☀️ **Season**: Dry period. Land preparation phase." if lang == "English" else "☀️ **Msimu**: Kiangazi. Tayarisha shamba sasa.")

        # 1. Base Strategy (calculated early for action plan)
        ph_val = soil["pH"]
        k_val = soil["Extractable Potassium (mg/kg)"]
        s_val = soil.get("Sulfur (ppm)", 15.0)
        s_low = s_val < reqs.get("s_min", 10.0)
        
        if crop == "Tea":
            p_type = "NPK 26:5:5"
            n_type = "Ammonium Sulphate"
        elif k_val < reqs["k_min"]:
            p_type = "NPK 17:17:17"
        elif s_low:
            p_type = "Mavuno" if crop in ["Maize", "Sorghum", "Wheat"] else "NPK 15:15:15+S"
        elif ph_val < 5.5:
            p_type = "Mavuno" if crop in ["Maize", "Sorghum", "Wheat"] else "SSP"
        else:
            p_type = "DAP"
        
        if crop != "Tea":
            if s_low:
                n_type = "Ammonium Sulphate" 
            else:
                n_type = "CAN" if ph_val < reqs["ph_min"] else "Urea"

        # --- Dynamic Biological Action Plan (Timeline) ---
        # Instead of static, we build this based on the crop's growth rate (Weeks)
        if crop == "Tea":
            timeline = {
                "season": season_en if lang == "English" else season_sw,
                "month_1": f"Pruning & General Maintenance",
                "month_2": f"First Feeding ({p_type})",
                "month_3": f"Plucking Cycle & Late Feeding ({n_type})"
            }
            if lang == "Kiswahili":
                timeline["month_1"] = "Kupogoa na Matengenezo ya Jumla"
                timeline["month_2"] = f"Kulisha kwa Kwanza ({p_type})"
                timeline["month_3"] = f"Mzunguko wa Kuchuma na Kulisha kwa Pili ({n_type})"
        elif crop == "Avocado":
            timeline = {
                "season": season_en if lang == "English" else season_sw,
                "month_1": f"Tree Maintenance & Manuring",
                "month_2": f"Basal Application ({p_type})",
                "month_3": f"Foliar Feeding & Pest Scouting"
            }
            if lang == "Kiswahili":
                timeline["month_1"] = "Utunzaji wa Miti na Mbolea ya Samadi"
                timeline["month_2"] = f"Kuweka Mbolea ya Kupandia ({p_type})"
                timeline["month_3"] = f"Kulisha kwa Majani na Kuangalia Wadudu"
        else:
            timeline = {
                "season": season_en if lang == "English" else season_sw,
                "month_1": f"Land Prep, Sowing & Basal Fertilizer ({p_type})",
                "month_2": "1st Weeding & Growth Monitoring",
                "month_3": "Scouting & Crop Protection"
            }
            if lang == "Kiswahili":
                timeline["month_1"] = f"Tayarisha Shamba, Panda na Mbolea ya Kupandia ({p_type})"
                timeline["month_2"] = "Palizi ya kwanza na Kuangalia Ukuaji"
                timeline["month_3"] = "Kuangalia Wadudu na Kulinda Mazao"

        # Cross-reference the Top Dressing Rules (Biological Timing)
        td_rule = self.top_dress_rules[self.top_dress_rules["Crop"] == crop] if not self.top_dress_rules.empty else pd.DataFrame()
        if not td_rule.empty:
            rule = td_rule.iloc[0]
            timing = str(rule["Timing"]).lower()
            product = str(rule["Product"])
            
            # Month 1 (Weeks 1-4)
            if any(x in timing for x in ["week 3", "week 4", "emergence", "planting"]):
                if product != "None":
                    timeline["month_1"] += f" + Top Dressing ({n_type})"
                else:
                    timeline["month_1"] += " (No N-Top Dress needed)"

            # Month 2 (Weeks 5-8)
            if any(x in timing for x in ["week 5", "week 6", "week 7", "week 8", "knee-high", "tillering"]):
                if product != "None":
                    timeline["month_2"] = f"Top Dressing ({n_type}) & Weeding" if lang == "English" else f"Mbolea ya Kukuzia ({n_type}) na Palizi"
                else:
                    timeline["month_2"] += " (No N-Top Dress needed)"

            # Month 3 (Weeks 9-12+)
            if any(x in timing for x in ["week 9", "week 10", "week 11", "week 12", "fruiting", "continuous"]):
                if product != "None":
                    timeline["month_3"] = f"Late Stage Top Dressing ({n_type}) & Protection" if lang == "English" else f"Mbolea ya Kukuzia na Ulinzi wa Mazao"

        # 3. Acidity & Liming (Scientific: Only if below crop-specific ph_min)
        is_acidic = soil["pH"] < reqs["ph_min"]
        
        # Format pH display with uncertainty if available
        ph_display = f"{ph_val:.1f}"
        if "pH_bounds" in soil and soil["pH_bounds"][0] is not None:
            ph_display += f" (90% Confidence Range: {soil['pH_bounds'][0]:.1f}-{soil['pH_bounds'][1]:.1f})"

        if is_acidic:
            al_val = soil.get("Aluminium (ppm)", 0)
            mg_val = soil.get("Magnesium (ppm)", 100.0)
            lime_type = "Dolomitic Lime" if mg_val < 50.0 else "Calcitic Lime"
            
            # Buffering Capacity based on Texture
            texture = soil.get("Texture", "Loam")
            if "Clay" in texture:
                buff_factor = 15.0
            elif "Sand" in texture:
                buff_factor = 6.0
            else:
                buff_factor = 10.0
                
            gap = reqs["ph_min"] - ph_val
            lime_bags = gap * buff_factor * farm_size_acres
            lower_lime = max(0.5, lime_bags * 0.8)
            upper_lime = lime_bags * 1.2
            
            breakdown.append(f"Basal Adj: {lime_bags:.1f} x bags {lime_type}")
            total_cost += lime_bags * mp.get("Lime", 500)
            
            if al_val > 50:
                if lang == "English": advice.append(f"🚨 **Aluminium Toxicity Detected**: Al is {al_val:.1f} ppm — actively poisoning roots. pH {ph_display} is too low. Apply **{lower_lime:.1f} to {upper_lime:.1f} bags** of {lime_type} immediately.")
                else: advice.append(f"🚨 **Sumu ya Alumini**: Al ni {al_val:.1f} ppm. Tumia **mifuko {lower_lime:.1f} hadi {upper_lime:.1f}** za {lime_type} mara moja.")
            else:
                if lang == "English": advice.append(f"🚨 **Critical Acidity**: pH {ph_display} is too low for {crop}. Apply **{lower_lime:.1f} to {upper_lime:.1f} bags** of {lime_type}.")
                else: advice.append(f"🚨 **Asidi Kali**: pH {ph_display} ni ya chini sana. Tumia **mifuko {lower_lime:.1f} hadi {upper_lime:.1f}** za {lime_type}.")
        else:
            al_val = soil.get("Aluminium (ppm)", 0)
            ca_val = soil.get("Calcium (ppm)", 1000.0)
            status = "Healthy" if lang == "English" else "Hali Sawa"
            al_status = "Safe" if (al_val < 50 or ph_val >= 5.5) else "High"
            if lang == "English": 
                al_str = "Bound/Inert" if (al_val >= 50 and ph_val >= 5.5) else al_status
                advice.append(f"✅ **pH & Aluminium**: pH is {status} ({ph_display}). Aluminium is {al_str} ({al_val:.1f} ppm).")
                if ca_val < 300.0:
                    gyp_bags = 2.0 * farm_size_acres
                    advice.append(f"⚠️ **Calcium Deficiency**: Ca is low ({ca_val:.1f} ppm). Apply **1.5 to 2.5 bags** of Gypsum.")
            else: 
                al_str = "Salama" if (al_val >= 50 and ph_val >= 5.5) else "Salama" if al_status=="Safe" else "Juu"
                advice.append(f"✅ **pH na Alumini**: pH iko {status} ({ph_display}). Alumini iko {al_str} ({al_val:.1f} ppm).")
                if ca_val < 300.0:
                    advice.append(f"⚠️ **Upungufu wa Kalsiamu**: Ca iko chini ({ca_val:.1f} ppm). Tumia **mifuko 1.5 hadi 2.5** za Gypsum.")

        # 4. Stage 1: Basal Calculation (1 mg/kg gap = 1 kg/acre nutrient needed)
        p_val = soil["Extractable Phosphorus (mg/kg)"]
        p_gap = max(0, reqs["p_min"] - p_val)
        
        # Calculate bags based on product concentration
        # Formula: Gap / (Analysis * 50kg)
        fert_p_analysis = ANALYSIS.get(p_type, {"P": 0.46})["P"]
        p_bags = (p_gap / (fert_p_analysis * 50)) if fert_p_analysis > 0 else 0
        
        if p_bags >= 0.05:
            qty = p_bags * farm_size_acres
            p_lower = max(0.25, qty * 0.75)
            p_upper = qty * 1.25
            breakdown.append(f"Stage 1 (Basal): {qty:.2f} x bags {p_type}")
            total_cost += qty * mp.get(p_type, 0)
            if lang == "English": advice.append(f"⚠️ **Phosphorus Deficiency**: P is low ({p_val:.1f} mg/kg). Recommended: **{p_lower:.1f} to {p_upper:.1f} bags** of {p_type}.")
            else: advice.append(f"⚠️ **Upungufu wa Fosforasi**: P iko chini. Pendekezo: **mifuko {p_lower:.1f} hadi {p_upper:.1f}** za {p_type}.")
        else:

            p_bags = 0
            if lang == "English": advice.append(f"✅ **Phosphorus**: Sufficient ({p_val:.1f} mg/kg). No basal P required.")
            else: advice.append(f"✅ **Fosforasi**: Inatosha ({p_val:.1f} mg/kg). Hakuna mbolea ya P inayohitajika.")

        # 5. Stage 2: Top Dressing Calculation
        n_val = soil["Total Nitrogen (g/kg)"]
        n_display = f"{n_val:.2f} g/kg"
        if "N_bounds" in soil and soil["N_bounds"][0] is not None:
            n_display += f" (90% Confidence Range: {soil['N_bounds'][0]:.2f}-{soil['N_bounds'][1]:.2f})"
        
        n_bags = 0
        
        # Check Top Dressing Rules
        td_rule = self.top_dress_rules[self.top_dress_rules["Crop"] == crop] if not self.top_dress_rules.empty else pd.DataFrame()
        
        if not td_rule.empty:
            rule = td_rule.iloc[0]
            if pd.isna(rule["Product"]) or str(rule["Product"]) == "None":
                n_bags = 0
                if lang == "English": advice.append(f"💡 **Top Dress**: {rule['Instruction']}")
                else: advice.append(f"💡 **Mbolea ya Kukuzia**: {rule['Instruction']}")
            else:
                n_gap = max(0, reqs["n_min"] - n_val)
                fert_n_analysis = ANALYSIS.get(n_type, {"N": 0.26})["N"]
                n_bags = (n_gap / (fert_n_analysis * 50)) if fert_n_analysis > 0 else 0
                
                if crop == "Maize" and n_bags < 1.0:
                    n_bags = 1.0
                
                if n_bags >= 0.05:
                    qty = n_bags * farm_size_acres
                    n_lower = max(0.5, qty * 0.8)
                    n_upper = qty * 1.2
                    if lang == "English":
                        advice.append(f"🚀 **Stage 2 (Top Dress)**: Apply **{n_lower:.1f} to {n_upper:.1f} bags** of {n_type} at **{rule['Timing']}**. {rule['Instruction']}")
                    else:
                        advice.append(f"🚀 **Hatua ya 2 (Kukuzia)**: Tumia **mifuko {n_lower:.1f} hadi {n_upper:.1f}** za {n_type} wakati wa **{rule['Timing']}**. {rule['Instruction']}")
                else:
                    n_bags = 0
                    if lang == "English": advice.append(f"✅ **Nitrogen**: Sufficient ({n_display}). No top dress required.")
                    else: advice.append(f"✅ **Nitrojeni**: Inatosha ({n_val:.2f} g/kg). Hakuna mbolea ya kukuzia inayohitajika.")
        else:
            # Fallback
            n_gap = max(0, reqs["n_min"] - n_val)
            fert_n_analysis = ANALYSIS.get(n_type, {"N": 0.26})["N"]
            n_bags = (n_gap / (fert_n_analysis * 50)) if fert_n_analysis > 0 else 0
            
            if crop == "Maize" and n_bags < 1.0:
                n_bags = 1.0
        
        if n_bags >= 0.05:
            qty = n_bags * farm_size_acres
            breakdown.append(f"Stage 2 (Top Dress): {qty:.2f} x bags {n_type}")
            total_cost += qty * mp.get(n_type, 0)
            if td_rule.empty:
                if lang == "English": advice.append(f"🚀 **Stage 2 (Top Dress)**: Apply {qty:.1f} bags {n_type} at the vegetative stage.")
                else: advice.append(f"🚀 **Hatua ya 2 (Kukuzia)**: Tumia mifuko {qty:.1f} za {n_type} wakati wa ukuaji.")
        elif td_rule.empty:

            n_bags = 0
            if lang == "English": advice.append(f"✅ **Nitrogen**: Sufficient ({n_display}). No top dress required.")
            else: advice.append(f"✅ **Nitrojeni**: Inatosha ({n_val:.2f} g/kg). Hakuna mbolea ya kukuzia inayohitajika.")

        # 6. Foliar Feed (Data-driven from crop_requirements.csv)
        if reqs.get("foliar", 0) == 1:
            foliar_qty = 1.0 * farm_size_acres
            breakdown.append(f"Foliar Feed: {foliar_qty:.1f} x Liters")
            total_cost += foliar_qty * mp.get("Foliar Feed (1L)", 0)
            if lang == "English": advice.append(f"🍃 **Foliar Tip**: Apply Foliar Feed during flowering/fruiting for maximum quality.")
            else: advice.append(f"🍃 **Kidokezo**: Tumia mbolea ya majani wakati wa kutoa maua/matunda.")

        # 6b. Potassium (K) Advice
        k_val = soil.get("Extractable Potassium (mg/kg)", 0)
        k_min = reqs.get("k_min", 150.0)
        if k_val < k_min:
            if lang == "English": advice.append(f"⚠️ **Potassium Deficiency**: K is low ({k_val:.1f} mg/kg). Supplement with Muriate of Potash (MOP).")
            else: advice.append(f"⚠️ **Upungufu wa Potasiamu**: K iko chini ({k_val:.1f} mg/kg). Ongeza mbolea ya MOP.")
        else:
            if lang == "English": advice.append(f"✅ **Potassium**: Sufficient ({k_val:.1f} mg/kg).")
            else: advice.append(f"✅ **Potasiamu**: Inatosha ({k_val:.1f} mg/kg).")

        # 6c. Sulfur (S) Advice
        s_val = soil.get("Sulfur (ppm)", 15.0)
        s_min = reqs.get("s_min", 10.0)
        if s_val < s_min:
            if current_fert == "Urea":
                if lang == "English": advice.append(f"⚠️ **Sulfur Deficiency**: S is low ({s_val:.1f} ppm). Switch from Urea to Ammonium Sulphate to supply vital sulfur.")
                else: advice.append(f"⚠️ **Upungufu wa Salfa**: S iko chini ({s_val:.1f} ppm). Badili kutoka Urea hadi Ammonium Sulphate.")
            elif "None" not in str(current_fert):
                if lang == "English": advice.append(f"⚠️ **Sulfur Deficiency**: S is low ({s_val:.1f} ppm). Consider supplementing with Ammonium Sulphate instead of standard top-dress.")
                else: advice.append(f"⚠️ **Upungufu wa Salfa**: S iko chini ({s_val:.1f} ppm). Ongeza Ammonium Sulphate.")
            else:
                if lang == "English": advice.append(f"⚠️ **Sulfur Deficiency**: S is low ({s_val:.1f} ppm). Choose a sulfur-enriched fertilizer option.")
                else: advice.append(f"⚠️ **Upungufu wa Salfa**: S iko chini ({s_val:.1f} ppm). Tumia mbolea yenye salfa.")
        else:
            if lang == "English": advice.append(f"✅ **Sulfur**: Sufficient ({s_val:.1f} ppm).")
            else: advice.append(f"✅ **Salfa**: Inatosha ({s_val:.1f} ppm).")

        # 7. Zinc Deficiency
        zn_val = soil.get("Zinc (ppm)")
        if zn_val is not None:
            zn_min = reqs.get("zn_min", 1.0)
            if zn_val < zn_min:
                qty = 1.0 * farm_size_acres
                breakdown.append(f"Zinc Supplement: {qty:.1f} x Acre Doses Zinc Sulphate Foliar")
                total_cost += qty * mp.get("Zinc Sulphate Foliar", 200)
                if lang == "English": advice.append(f"⚠️ **Zinc Deficiency**: Zn is {zn_val:.1f} ppm (below {zn_min:.1f}). Apply Zinc Sulphate foliar spray at vegetative stage for 15–25% yield boost.")
                else: advice.append(f"⚠️ **Upungufu wa Zinki**: Zn ni {zn_val:.1f} ppm (chini ya {zn_min:.1f}). Tumia dawa ya Zinki kupitia majani kwa ongezeko la mavuno.")
            else:
                if lang == "English": advice.append(f"✅ **Zinc**: Sufficient ({zn_val:.1f} ppm).")
                else: advice.append(f"✅ **Zinki**: Inatosha ({zn_val:.1f} ppm).")

        # 7b. Organic Carbon
        oc_val = soil.get("Organic Carbon (g/kg)")
        if oc_val is not None:
            oc_status = "Good" if oc_val > 15 else "Low"
            if lang == "English": advice.append(f"{'✅' if oc_status=='Good' else '⚠️'} **Organic Carbon**: {oc_status} ({oc_val:.1f} g/kg). {'Encourage composting.' if oc_status=='Low' else ''}")
            else: advice.append(f"{'✅' if oc_status=='Good' else '⚠️'} **Kaboni Hai**: {oc_val:.1f} g/kg.")

        # 7c. Cation Exchange Capacity (CEC)
        cec_val = soil.get("CEC (meq/100g)")
        if cec_val is not None:
            if cec_val < 12.0:
                if lang == "English": advice.append(f"⚠️ **Low Nutrient Retention (CEC)**: {cec_val:.1f} meq/100g. Soil cannot hold high doses. Apply split, smaller fertilizer portions to prevent leaching.")
                else: advice.append(f"⚠️ **Uwezo mdogo wa kuhifadhi mbolea (CEC)**: {cec_val:.1f} meq/100g. Weka mbolea kwa awamu ndogo ndogo.")
            else:
                if lang == "English": advice.append(f"✅ **CEC (Retention)**: Good capacity ({cec_val:.1f} meq/100g).")
                else: advice.append(f"✅ **CEC**: Uwezo mzuri wa kuhifadhi virutubisho ({cec_val:.1f} meq/100g).")

        # 8. Texture Context
        texture = soil.get("Texture")
        if texture:
            tex_advice = f"Your soil texture is {texture}."
            if "Sand" in texture:
                tex_advice += " It drains quickly. Use split, lighter fertilizer applications to prevent leaching."
            elif "Clay" in texture:
                tex_advice += " It holds nutrients well but may drain poorly. Ensure good field drainage."
            elif "Loam" in texture:
                tex_advice += " Excellent texture with balanced drainage and nutrient retention."
            
            if lang == "English": advice.append(f"🏔️ **Soil Texture**: {tex_advice}")
            else: advice.append(f"🏔️ **Umbile la Udongo**: Aina ya udongo wako ni {texture}.")

        health_score = self.calculate_health_score(soil, reqs)
            
        # Comparison logic helper
        def get_reason(cond_key):
            if self.comp_reasons.empty: return cond_key
            row = self.comp_reasons[self.comp_reasons["Condition"] == cond_key]
            if row.empty: return cond_key
            return row.iloc[0]["Reason_SW"] if lang == "Kiswahili" else row.iloc[0]["Reason_EN"]

        if p_bags == 0 and n_bags == 0:
            comp_rec = get_reason("Rec_Optimal")
        else:
            comp_rec = f"{p_type} + {n_type}" if p_bags > 0 and n_bags > 0 else p_type if p_bags > 0 else n_type
        
        reason = get_reason("Default")
        if "CAN" in current_fert and p_bags > 0:
            reason = get_reason("P_Deficit_with_CAN")
        elif "DAP" in current_fert and n_bags > 0:
            reason = get_reason("N_Deficit_with_DAP")
        elif ("DAP" in current_fert or "NPK" in current_fert) and ph_val < 5.5:
            reason = get_reason("Acidic_with_DAP")
        elif "DAP" in current_fert and k_val < reqs["k_min"]:
            reason = get_reason("K_Deficit_with_DAP")
        elif current_fert in ["None", "Manure"] and (p_bags > 0 or n_bags > 0):
            reason = get_reason("Low_Density")
        elif current_fert == "NPK":
            reason = get_reason("NPK_Generic")
        elif p_bags == 0 and n_bags == 0:
            reason = get_reason("Optimal")
            
        impact_rec = get_reason("Impact_Optimized")
        impact_cur = get_reason("Impact_Variable")
            
        # 9. Fix Timeline Contradictions dynamically based on exact calculated requirements
        if p_bags == 0 and n_bags == 0:
            if lang == "English":
                timeline["month_1"] = "Land Prep & Sowing (No basal needed)"
                timeline["month_2"] = "1st Weeding & Growth Monitoring"
                timeline["month_3"] = "Scouting & Harvesting Prep"
            else:
                timeline["month_1"] = "Tayarisha Shamba na Panda (Mbolea haihitajiki)"
                timeline["month_2"] = "Palizi ya kwanza na Kuangalia Ukuaji"
                timeline["month_3"] = "Ulinzi na Kuangalia Mazao"
        elif p_bags == 0 and n_bags > 0:
            if lang == "English":
                timeline["month_1"] = "Land Prep & Sowing"
                timeline["month_2"] = f"Top Dressing ({n_type}) & Weeding"
                timeline["month_3"] = "Late Stage Protection"
            else:
                timeline["month_1"] = "Tayarisha Shamba na Panda"
                timeline["month_2"] = f"Mbolea ya Kukuzia ({n_type}) na Palizi"
                timeline["month_3"] = "Kuangalia Wadudu na Kuvuna"
        elif p_bags > 0 and n_bags == 0:
            if lang == "English":
                timeline["month_1"] = f"Land Prep, Sowing & Basal ({p_type})"
                timeline["month_2"] = "1st Weeding & Growth Monitoring"
                timeline["month_3"] = "Scouting & Crop Protection"
            else:
                timeline["month_1"] = f"Tayarisha Shamba, Panda na Mbolea ({p_type})"
                timeline["month_2"] = "Palizi ya kwanza na Kuangalia Ukuaji"
                timeline["month_3"] = "Ulinzi na Kuangalia Mazao"

        # Nutrient Status Flags for Database Compatibility
        is_n_low = n_val < reqs["n_min"]
        is_p_low = p_val < reqs["p_min"]
        is_k_low = k_val < reqs["k_min"]

        # 10. Match officially certified seeds
        seeds = self.get_seed_recommendations(crop, soil.get("Agroecological Zone", "Medium"), lang=lang)

        return {
            "county_data": soil, "crop": crop, "current_fert": current_fert, "advice": advice, "timeline": timeline, "reqs": reqs,
            "budget": {"breakdown": breakdown, "total_budget": int(total_cost), "farm_size": farm_size_acres},
            "is_acidic": is_acidic, "is_n_low": is_n_low, "is_p_low": is_p_low, "is_k_low": is_k_low,
            "health_score": health_score, "data_source": data_source, "confidence": confidence,
            "latitude": lat, "longitude": lon,
            "comparison": {"current": current_fert, "recommended": comp_rec, "current_flaw": reason, "impact": impact_rec, "current_outcome": impact_cur},
            "seeds": seeds
        }

    def get_seed_recommendations(self, crop, agro_zone, lang="English"):
        """
        Retrieves official certified seed varieties from KALRO/Kenya Seed databases.
        """
        seeds_path = os.path.join(self.data_dir, "seeds.csv")
        if not os.path.exists(seeds_path):
            return []
            
        try:
            df = pd.read_csv(seeds_path)
            # Map complicated agroecological zones to target Altitude definitions
            zone_str = str(agro_zone).lower()
            if any(x in zone_str for x in ["highland", "tea"]):
                mapped_altitude = "Highland"
            elif any(x in zone_str for x in ["dryland", "semi-arid", "coastal", "savannah", "lowland"]):
                mapped_altitude = "Dryland"
            else:
                mapped_altitude = "Medium"
                
            # Filter
            filtered = df[(df["Crop"].str.lower() == crop.lower())]
            
            # Try precise altitude match first
            zone_match = filtered[filtered["Altitude_Zone"].str.lower().str.contains(mapped_altitude.lower())]
            if not zone_match.empty:
                return zone_match.to_dict('records')
            
            # Fallback to overall crop matches
            return filtered.to_dict('records') if not filtered.empty else []
        except Exception:
            return []

    def generate_sms_summary(self, result, lang="English"):
        if lang == "English":
            return f"FarmIQ: {result['crop']} Report. Health: {result['health_score']}/100. Rec: {result['comparison']['recommended']}. Budget: KES {result['budget']['total_budget']:,} per acre."
        else:
            return f"FarmIQ: Ripoti ya {result['crop']}. Afya: {result['health_score']}/100. Pendekezo: {result['comparison']['recommended']}. Gharama: KES {result['budget']['total_budget']:,} kwa ekari."


    def match_crops_to_soil(self, result, farm_acres=1.0, lang="English"):
        """
        Global Precision Agronomist (V42).
        Aggressively discriminates between crops based on Chemical (pH, NPK) 
        and Physical (Texture, OC) parameters + Weather.
        """
        if self.crop_econ.empty:
            return []
            
        soil = result.get("county_data", {})
        ph = soil.get("pH", 7.0)
        texture = soil.get("Texture", "Loam")
        oc_val = soil.get("Organic Carbon (g/kg)", 20)
        
        # Current Weather Factor
        rain_val = 0.0
        try:
            advice_text = result.get("weather_advice", "")
            if "(" in advice_text and "mm)" in advice_text:
                rain_val = float(advice_text.split("(")[1].split("mm")[0])
        except: pass

        # Nutrient values
        n_val = soil.get("Total Nitrogen (g/kg)", 0) 
        p_val = soil.get("Extractable Phosphorus (mg/kg)", 0)
        k_val = soil.get("Extractable Potassium (mg/kg)", 0)
        al_val = soil.get("Aluminium (ppm)", 0)

        results = []
        for _, row in self.crop_econ.iterrows():
            crop = row["Crop"]
            
            # 1. Chemical Fit: pH (Aggressive Gaussian Penalty)
            ph_min, ph_max = row["ph_min"], row["ph_max"]
            ph_ideal = (ph_min + ph_max) / 2
            # dist of 0.5 results in ~60% score. dist of 1.0 results in ~10% score.
            ph_score = max(0, 1.0 - (abs(ph - ph_ideal) / 0.7)**2)
            
            # 2. Physical Fit: Texture Affinity
            # If the soil texture matches the crop's preferred texture, it gets a massive boost.
            pref_tex = row.get("pref_texture", "Loam")
            texture_score = 0.6 # Base
            if pref_tex in texture or texture in pref_tex:
                texture_score = 1.0
            elif ("Sandy" in pref_tex and "Clay" in texture) or ("Clay" in pref_tex and "Sandy" in texture):
                texture_score = 0.2 # Massive mismatch (e.g. Rice in Sand or Groundnuts in Heavy Clay)
            
            # 3. Nutrient & Organic Fit
            def n_fit(val, level):
                target = 2.0 if level == "high" else (1.0 if level == "medium" else 0.5)
                return min(val / target, 1.2) if val > 0 else 0.4
            
            nut_score = (n_fit(n_val, row["n_need"]) + n_fit(p_val/20, row["p_need"]) + n_fit(k_val/200, row["k_need"])) / 3
            
            # OC Bonus: High organic carbon boosts scores for high-value crops (Coffee/Tea)
            oc_bonus = 1.0
            if oc_val > 25 and row["n_need"] == "high": oc_bonus = 1.1
            if oc_val < 10: oc_bonus = 0.8
            
            # 4. Toxicity & Weather Risk
            risk_factor = 1.0
            
            # Sulfur penalty for high sulfur requirement crops (e.g. Coffee, Brassicas, Onions)
            s_val = soil.get("Sulfur (ppm)", 15.0)
            if s_val < 10.0 and crop in ["Coffee", "Coffee (Arabica)", "Onions", "Cabbages", "Brassicas"]:
                risk_factor *= 0.8
                
            if al_val > 40 and ph < 5.5:
                if crop not in ["Tea", "Potatoes", "Cassava", "Coffee (Arabica)"]: risk_factor *= 0.4
            if rain_val > 120 and "Clay" in texture:
                if crop in ["Maize", "Beans", "Sorghum"]: risk_factor *= 0.6
            
            # Final Multi-Factor Score
            # Weighting: pH (30%), Texture (30%), Nutrients (20%), Risk (20%)
            match_score = (ph_score * 0.3 + texture_score * 0.3 + nut_score * 0.2 + risk_factor * 0.2) * oc_bonus * 100
            
            # Clamp and format
            match_score = min(max(match_score, 5), 99.0)
            
            gross_income = row["yield_per_acre"] * row["price_per_kg"] * farm_acres
            
            if match_score >= 88: label = "🥇 EXCELLENT" if lang == "English" else "🥇 BORA SANA"
            elif match_score >= 70: label = "🥈 VERY GOOD" if lang == "English" else "🥈 NZURI SANA"
            elif match_score >= 45: label = "🥉 GOOD" if lang == "English" else "🥉 NZURI"
            else: label = "⚠️ POOR" if lang == "English" else "⚠️ MBAYA"
            
            results.append({
                "crop": crop,
                "match_score": round(match_score),
                "label": label,
                "gross_income": int(gross_income)
            })
            
        results.sort(key=lambda x: x["match_score"], reverse=True)
        return results[:5]


if __name__ == "__main__":
    import os
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_PATH = os.path.join(BASE_DIR, "data", "kenya_county_soils.csv")
    engine = FarmIQRecommender(DATA_PATH)
    print(engine.generate_recommendation("Kakamega", "Maize", "DAP"))
