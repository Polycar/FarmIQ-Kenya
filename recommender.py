import pandas as pd
import numpy as np
import rasterio
import os

class FarmIQRecommender:
    def __init__(self, soil_data_path):
        """Initialize with path to the county soil dataset."""
        self.soil_data = pd.read_csv(soil_data_path)
        
        # General crop nutrient requirements threshold
        self.crop_reqs = {
            "Maize": {"ph_min": 5.5, "n_min": 1.2, "p_min": 20, "k_min": 150},
            "Beans": {"ph_min": 6.0, "n_min": 1.0, "p_min": 15, "k_min": 120},
            "Potatoes": {"ph_min": 5.2, "n_min": 1.5, "p_min": 25, "k_min": 250},
            "Tomatoes": {"ph_min": 6.0, "n_min": 1.5, "p_min": 25, "k_min": 250},
            "Kale (Sukuma)": {"ph_min": 5.5, "n_min": 1.5, "p_min": 15, "k_min": 150},
            "Wheat": {"ph_min": 6.0, "n_min": 1.3, "p_min": 18, "k_min": 160},
            "Sorghum": {"ph_min": 5.5, "n_min": 1.0, "p_min": 12, "k_min": 130},
            "Avocado": {"ph_min": 5.5, "n_min": 1.5, "p_min": 20, "k_min": 300},
            "Tea": {"ph_min": 4.5, "n_min": 2.0, "p_min": 15, "k_min": 200}
        }
        self.raster_path = os.path.join(os.path.dirname(__file__), "data", "rasters", "kenya_ph.tif")
        
        # Approximate centroids for 47 counties to enable auto-detection from GPS
        self.COUNTY_CENTROIDS = {
            "Baringo": [0.48, 35.58], "Bomet": [-0.78, 35.35], "Bungoma": [0.57, 34.56], "Busia": [0.46, 34.11],
            "Elgeyo-Marakwet": [0.81, 35.50], "Embu": [-0.54, 37.45], "Garissa": [-0.45, 39.64], "Homa Bay": [-0.53, 34.45],
            "Isiolo": [0.35, 37.58], "Kajiado": [-2.09, 36.78], "Kakamega": [0.28, 34.75], "Kericho": [-0.37, 35.28],
            "Kiambu": [-1.17, 36.83], "Kilifi": [-3.51, 39.91], "Kirinyaga": [-0.66, 37.31], "Kisii": [-0.68, 34.78],
            "Kisumu": [-0.10, 34.75], "Kitui": [-1.37, 38.01], "Kwale": [-4.17, 39.45], "Laikipia": [0.36, 37.07],
            "Lamu": [-2.27, 40.90], "Machakos": [-1.52, 37.26], "Makueni": [-1.79, 37.62], "Mandera": [3.94, 41.86],
            "Marsabit": [2.33, 37.99], "Meru": [0.05, 37.65], "Migori": [-1.06, 34.47],
            "Mombasa": [-4.05, 39.67], "Murang'a": [-0.72, 37.15], "Nairobi": [-1.29, 36.82], "Nakuru": [-0.30, 36.06],
            "Nandi": [0.18, 35.12], "Narok": [-1.08, 35.87], "Nyamira": [-0.58, 34.93], "Nyandarua": [-0.33, 36.42],
            "Nyeri": [-0.42, 36.95], "Samburu": [1.21, 36.76], "Siaya": [0.06, 34.29], "Taita-Taveta": [-3.31, 38.48],
            "Tana River": [-1.51, 39.15], "Tharaka-Nithi": [-0.30, 37.95], "Trans Nzoia": [1.02, 34.95], "Turkana": [3.11, 35.60],
            "Uasin Gishu": [0.52, 35.27], "Vihiga": [0.01, 34.72], "Wajir": [1.75, 40.06], "West Pokot": [1.53, 35.11]
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

    def generate_recommendation(self, county, crop, current_fert, farm_size_acres=1.0, lang="English", lat=None, lon=None, overrides=None, price_mode="Subsidized"):
        """
        Main recommendation engine. Merges spatial data with crop requirements 
        to calculate a nutrient-gap based recommendation.
        """
        import datetime
        if lat and lon and (not county or county == "Detecting..."):
            county = self.detect_county(lat, lon)
        
        soil = self.get_county_data(county)
        if not soil:
            return {"error": "Location data not found." if lang == "English" else "Data ya eneo haijapatikana."}
        
        reqs = self.crop_reqs.get(crop, self.crop_reqs["Maize"])

        # High-Resolution Override
        if lat and lon:
            hi_res_ph = self.get_high_res_ph(lat, lon)
            if hi_res_ph:
                soil["pH"] = hi_res_ph

        if overrides:
            for key in ["pH", "Total Nitrogen (mg/kg)", "Extractable Phosphorus (mg/kg)", "Extractable Potassium (mg/kg)"]:
                if key in overrides and overrides[key] is not None:
                    soil[key] = overrides[key]

        # --- SCIENTIFIC LOGIC: NUTRIENT GAP CALCULATION ---
        # Baseline Prices (2026 Est. KES per 50kg bag)
        PRICES = {
            "Subsidized": {"DAP": 2500, "CAN": 2500, "NPK": 2500, "Urea": 2500, "Lime": 1500, "Mavuno": 2500},
            "Commercial": {"DAP": 6500, "CAN": 4500, "NPK": 5500, "Urea": 5500, "Lime": 1800, "Mavuno": 5800}
        }
        mp = PRICES.get(price_mode, PRICES["Subsidized"])

        advice = []
        breakdown = []
        total_cost = 0

        # Seasonal Context
        month = datetime.datetime.now().month
        if lang == "English":
            if 3 <= month <= 5: advice.append("🌧️ **Season**: Long Rains. Plan for early planting.")
            elif 10 <= month <= 12: advice.append("🌧️ **Season**: Short Rains. Fast maturing recommended.")
            else: advice.append("☀️ **Season**: Dry period. Land preparation phase.")
        else:
            if 3 <= month <= 5: advice.append("🌧️ **Msimu**: Mvua za masika. Panda mapema.")
            elif 10 <= month <= 12: advice.append("🌧️ **Msimu**: Mvua fupi. Mbegu zinazokomaa haraka.")
            else: advice.append("☀️ **Msimu**: Kiangazi. Tayarisha shamba sasa.")

        # 1. Acidity & Liming
        is_acidic = soil["pH"] < reqs["ph_min"]
        if soil["pH"] < 5.5:
            lime_bags = 2.0 * farm_size_acres
            breakdown.append(f"{lime_bags:.1f} x bags Lime")
            total_cost += lime_bags * mp["Lime"]
            if lang == "English": advice.append(f"🚨 **Critical Acidity**: pH {soil['pH']:.1f}. Apply Lime to unlock nutrients.")
            else: advice.append(f"🚨 **Asidi Kali**: pH {soil['pH']:.1f}. Tumia chokaa kurekebisha udongo.")
        else:
            if lang == "English": advice.append(f"✅ **pH**: Healthy ({soil['pH']:.1f}).")
            else: advice.append(f"✅ **pH**: Hali Sawa ({soil['pH']:.1f}).")

        # 2. Phosphorus Gap (Planting)
        p_val = soil["Extractable Phosphorus (mg/kg)"]
        p_bags = 0
        p_type = "DAP" if soil["pH"] >= 5.5 else "Mavuno" # Use specialized blends for acidic soils
        
        if p_val < 10: p_bags = 1.5 # Severe deficit
        elif p_val < 20: p_bags = 1.0 # Moderate
        elif p_val < 30: p_bags = 0.5 # Low maintenance
        
        if p_bags > 0:
            qty = p_bags * farm_size_acres
            breakdown.append(f"{qty:.1f} x bags {p_type}")
            total_cost += qty * mp.get(p_type, 2500)

        # 3. Nitrogen Gap (Top Dressing)
        n_val = soil["Total Nitrogen (mg/kg)"]
        n_bags = 0
        n_type = "CAN"
        
        if n_val < 0.1: n_bags = 1.5
        elif n_val < 0.2: n_bags = 1.0
        
        if n_bags > 0:
            qty = n_bags * farm_size_acres
            breakdown.append(f"{qty:.1f} x bags {n_type}")
            total_cost += qty * mp.get(n_type, 2500)

        health_score = self.calculate_health_score(soil, reqs)
        
        # Comparison logic
        comp_rec = f"{p_type} + {n_type}" if p_bags > 0 and n_bags > 0 else p_type if p_bags > 0 else n_type
        
        # Nutrient Status Flags for Database Compatibility
        is_n_low = n_val < 0.2
        is_p_low = p_val < 30
        is_k_low = soil["Extractable Potassium (mg/kg)"] < 150

        return {
            "county_data": soil, "crop": crop, "current_fert": current_fert, "advice": advice,
            "budget": {"breakdown": breakdown, "total_budget": int(total_cost), "farm_size": farm_size_acres},
            "is_acidic": is_acidic, "is_n_low": is_n_low, "is_p_low": is_p_low, "is_k_low": is_k_low,
            "health_score": health_score,
            "comparison": {"current": current_fert, "recommended": comp_rec, "impact": "Optimized Recovery"}
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
