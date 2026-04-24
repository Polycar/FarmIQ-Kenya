import pandas as pd
import numpy as np
import rasterio
import os
from isda_api import get_precision_soil_data, is_api_configured

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
                    "p_min": row["p_min"], "k_min": row["k_min"]
                }
        if not self.crop_reqs:
            # Fallback if CSV is missing
            self.crop_reqs = {"Maize": {"ph_min": 5.5, "n_min": 1.2, "p_min": 20, "k_min": 150}}
        
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
        
        self.raster_path = os.path.join(os.path.dirname(__file__), "data", "rasters", "kenya_ph.tif")
        
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
        if os.path.exists(prices_path):
            pr_df = pd.read_csv(prices_path)
            for _, row in pr_df.iterrows():
                self.PRICES["Subsidized"][row["Fertilizer"]] = int(row["Subsidized"])
                self.PRICES["Commercial"][row["Fertilizer"]] = int(row["Commercial"])
        if not self.PRICES["Subsidized"]:
            # Fallback
            self.PRICES = {
                "Subsidized": {"DAP": 2500, "CAN": 2500, "NPK": 2500, "Urea": 2500, "Lime": 1500, "Mavuno": 2500, "SSP": 2500, "NPK 17:17:17": 2500},
                "Commercial": {"DAP": 6500, "CAN": 4500, "NPK": 5500, "Urea": 5500, "Lime": 1800, "Mavuno": 5800, "SSP": 5200, "NPK 17:17:17": 5600}
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
        return best_county if min_dist < 1.0 else "Unknown"

    def get_high_res_ph(self, lat, lon):
        """Samples the local 30m iSDAsoil GeoTIFF for high-precision pH."""
        if not os.path.exists(self.raster_path):
            return None
        try:
            with rasterio.open(self.raster_path) as src:
                for val in src.sample([(lon, lat)]):
                    pixel_val = val[0]
                    # iSDAsoil NoData is 255. Valid pH is usually 3.0-9.5 (30-95 in deci-pH).
                    if pixel_val > 0 and pixel_val < 200:
                        return pixel_val / 10.0
                    return None
        except Exception:
            return None
        except Exception:
            return None
        return None
    
    def get_county_data(self, county_name):
        """Retrieve soil metrics for a given county."""
        data = self.soil_data[self.soil_data["County"] == county_name]
        if data.empty:
            return None
        return data.iloc[0].to_dict()

    def calculate_health_score(self, soil, reqs):
        """Calculates a scientifically realistic soil quality index (SQI)."""
        def sig(x, x_crit):
            return 1 / (1 + np.exp(-5 * (x/x_crit - 0.5)))
        ph = soil["pH"]
        s_ph = np.exp(-(ph - 6.5)**2 / 2.0) 
        s_n = sig(soil["Total Nitrogen (mg/kg)"], reqs["n_min"])
        s_p = sig(soil["Extractable Phosphorus (mg/kg)"], reqs["p_min"])
        s_k = sig(soil["Extractable Potassium (mg/kg)"], reqs["k_min"])
        s_oc = sig(soil["Organic Carbon (g/kg)"], 15.0)
        final_score = (s_ph * 0.4 + s_n * 0.15 + s_p * 0.15 + s_k * 0.15 + s_oc * 0.15) * 100
        return int(np.clip(final_score, 0, 100))

    def generate_recommendation(self, county, crop, current_fert, farm_size_acres=1.0, lang="English", lat=None, lon=None, overrides=None, price_mode="Subsidized", is_subcounty=False):
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
        
        reqs = self.crop_reqs.get(crop, self.crop_reqs["Maize"])

        # High-Resolution Override (3-tier fallback chain)
        data_source = "Regional Baseline (CSV)" if lang == "English" else "Msingi wa Eneo (CSV)"
        confidence = "Moderate 🟡 (Based on ~100+ historical regional samples)"
        
        if lat and lon:
            # TIER 1: iSDAsoil API — All nutrients at 30m precision
            if is_api_configured():
                api_soil = get_precision_soil_data(lat, lon)
                if api_soil:
                    for key, val in api_soil.items():
                        soil[key] = val
                    if is_subcounty:
                        data_source = "Sub-County Baseline (iSDAsoil API)" if lang == "English" else "Msingi wa Kaunti Ndogo (API)"
                        confidence = "High 🟢 (30m satellite data averaged for Sub-County)"
                    else:
                        data_source = "iSDAsoil API (30m Full Spectrum)" if lang == "English" else "API ya iSDAsoil (30m Kamili)"
                        confidence = "Very High 🟢 (All nutrients at 30m via iSDAsoil API)"
            
            # TIER 2: Local GeoTIFF — pH only at 30m (fallback if API not configured or failed)
            if "iSDAsoil" not in data_source:
                hi_res_ph = self.get_high_res_ph(lat, lon)
                if hi_res_ph:
                    soil["pH"] = hi_res_ph
                    data_source = "30m Satellite Precision (pH)" if lang == "English" else "Usahihi wa Satelaiti (30m pH)"
                    confidence = "High 🟢 (pH at 30m resolution, other nutrients from regional baseline)"

        if overrides:
            for key in ["pH", "Total Nitrogen (mg/kg)", "Extractable Phosphorus (mg/kg)", "Extractable Potassium (mg/kg)"]:
                if key in overrides and overrides[key] is not None:
                    soil[key] = overrides[key]
            data_source = "Lab Override (Ground Truth)" if lang == "English" else "Matokeo ya Maabara"
            confidence = "Maximum 🔵 (Ground truth lab data)"

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

        # Extract 3-Month Timeline from Crop Calendars CSV
        timeline = None
        if not self.crop_calendars.empty:
            cal_match = self.crop_calendars[(self.crop_calendars["Crop"] == crop) & (self.crop_calendars["Season"] == season_en)]
            if not cal_match.empty:
                r = cal_match.iloc[0]
                timeline = {
                    "season": season_en if lang == "English" else season_sw,
                    "month_1": r["Month_1"],
                    "month_2": r["Month_2"],
                    "month_3": r["Month_3"]
                }

        # 1. Acidity & Liming
        is_acidic = soil["pH"] < reqs["ph_min"]
        if soil["pH"] < 5.5:
            lime_bags = 2.0 * farm_size_acres
            breakdown.append(f"Basal Adj: {lime_bags:.1f} x bags Lime")
            total_cost += lime_bags * mp.get("Lime", 1800)
            if lang == "English": advice.append(f"🚨 **Critical Acidity**: pH {soil['pH']:.1f}. Apply Lime to unlock nutrients.")
            else: advice.append(f"🚨 **Asidi Kali**: pH {soil['pH']:.1f}. Tumia chokaa kurekebisha udongo.")
        else:
            if lang == "English": advice.append(f"✅ **pH**: Healthy ({soil['pH']:.1f}).")
            else: advice.append(f"✅ **pH**: Hali Sawa ({soil['pH']:.1f}).")

        # 2. Stage 1: Basal/Planting (Phosphorus & Potassium focus)
        p_val = soil["Extractable Phosphorus (mg/kg)"]
        k_val = soil["Extractable Potassium (mg/kg)"]
        ph_val = soil["pH"]
        
        # Dynamic Selection
        if k_val < reqs["k_min"]:
            p_type = "NPK 17:17:17"
        elif ph_val < 5.5:
            p_type = "SSP"
        else:
            p_type = "DAP"

        p_gap = max(0, reqs["p_min"] - p_val)
        p_bags = 0
        if p_gap > 20: p_bags = 2.0
        elif p_gap > 10: p_bags = 1.0
        elif p_gap > 0: p_bags = 0.5
        
        if p_bags > 0:
            qty = p_bags * farm_size_acres
            breakdown.append(f"Stage 1 (Basal): {qty:.1f} x bags {p_type}")
            total_cost += qty * mp.get(p_type, 2500)

        # 3. Stage 2: Top Dressing (Nitrogen focus)
        n_val = soil["Total Nitrogen (mg/kg)"]
        n_bags = 0
        n_type = "CAN" if ph_val < 5.5 else "Urea"
        
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
                if n_gap > 0.15: n_bags = 2.0
                elif n_gap > 0.1: n_bags = 1.0
                elif n_gap > 0: n_bags = 0.5
                
                if n_bags > 0:
                    if lang == "English":
                        advice.append(f"🚀 **Stage 2 (Top Dress)**: Apply {n_type} at **{rule['Timing']}**. {rule['Instruction']}")
                    else:
                        advice.append(f"🚀 **Hatua ya 2 (Kukuzia)**: Tumia {n_type} wakati wa **{rule['Timing']}**. {rule['Instruction']}")
        else:
            # Fallback
            n_gap = max(0, reqs["n_min"] - n_val)
            if n_gap > 0.15: n_bags = 2.0
            elif n_gap > 0.1: n_bags = 1.0
            elif n_gap > 0: n_bags = 0.5
        
        if n_bags > 0:
            qty = n_bags * farm_size_acres
            breakdown.append(f"Stage 2 (Top Dress): {qty:.1f} x bags {n_type}")
            total_cost += qty * mp.get(n_type, 2500)

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
        elif current_fert in ["None", "Manure"] and (p_bags > 0 or n_bags > 0):
            reason = get_reason("Low_Density")
        elif current_fert == "NPK":
            reason = get_reason("NPK_Generic")
        elif p_bags == 0 and n_bags == 0:
            reason = get_reason("Optimal")
            
        impact_rec = get_reason("Impact_Optimized")
        impact_cur = get_reason("Impact_Variable")
            
        # Nutrient Status Flags for Database Compatibility
        is_n_low = n_val < 0.2
        is_p_low = p_val < 30
        is_k_low = soil["Extractable Potassium (mg/kg)"] < 150

        return {
            "county_data": soil, "crop": crop, "current_fert": current_fert, "advice": advice, "timeline": timeline,
            "budget": {"breakdown": breakdown, "total_budget": int(total_cost), "farm_size": farm_size_acres},
            "is_acidic": is_acidic, "is_n_low": is_n_low, "is_p_low": is_p_low, "is_k_low": is_k_low,
            "health_score": health_score, "data_source": data_source, "confidence": confidence,
            "comparison": {"current": current_fert, "recommended": comp_rec, "current_flaw": reason, "impact": impact_rec, "current_outcome": impact_cur}
        }

    def generate_sms_summary(self, result, lang="English"):
        if lang == "English":
            return f"FarmIQ: {result['crop']} Report. Health: {result['health_score']}/100. Rec: {result['comparison']['recommended']}. Budget: KES {result['budget']['total_budget']:,} per acre."
        else:
            return f"FarmIQ: Ripoti ya {result['crop']}. Afya: {result['health_score']}/100. Pendekezo: {result['comparison']['recommended']}. Gharama: KES {result['budget']['total_budget']:,} kwa ekari."

if __name__ == "__main__":
    import os
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_PATH = os.path.join(BASE_DIR, "data", "kenya_county_soils.csv")
    engine = FarmIQRecommender(DATA_PATH)
    print(engine.generate_recommendation("Kakamega", "Maize", "DAP"))
