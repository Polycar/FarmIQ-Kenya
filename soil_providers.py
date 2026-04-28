import requests
import numpy as np
import os
import pandas as pd
import datetime

class SoilDataProvider:
    def get_soil_properties(self, lat, lon):
        raise NotImplementedError

class iSDAProvider(SoilDataProvider):
    def get_soil_properties(self, lat, lon):
        url = "https://api.isda-africa.com/v1/soilproperty"
        prop_map = {
            "ph": "pH",
            "nitrogen_total": "Total Nitrogen (g/kg)",
            "phosphorus_extractable": "Extractable Phosphorus (mg/kg)",
            "potassium_extractable": "Extractable Potassium (mg/kg)",
            "organic_carbon": "Organic Carbon (g/kg)"
        }
        results = {}
        for api_name, internal_key in prop_map.items():
            try:
                resp = requests.get(url, params={"lat": lat, "lon": lon, "property": api_name, "depth": "0-20cm"}, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    val = data.get("property", {}).get(api_name, {}).get("value", {}).get("mean")
                    if val is not None:
                        results[internal_key] = float(val)
            except Exception:
                continue
        
        if "pH" in results:
            return results
        raise Exception("iSDA data incomplete")

class SoilGridsProvider(SoilDataProvider):
    def get_soil_properties(self, lat, lon):
        url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
        params = {
            "lat": lat,
            "lon": lon,
            "property": ["phh2o", "nitrogen", "soc"],
            "depth": "0-30cm",
            "value": "mean"
        }
        try:
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                props = data.get("properties", {}).get("layers", [])
                results = {}
                for layer in props:
                    name = layer.get("name")
                    depths = layer.get("depths", [])
                    if not depths: continue
                    val = depths[0].get("values", {}).get("mean")
                    if val is None: continue
                    
                    if name == "phh2o":
                        results["pH"] = float(val) / 10.0
                    elif name == "nitrogen":
                        results["Total Nitrogen (g/kg)"] = float(val) / 100.0
                    elif name == "soc":
                        results["Organic Carbon (g/kg)"] = float(val) / 10.0
                
                if "pH" in results:
                    return results
        except Exception:
            pass
        raise Exception("SoilGrids data unavailable")

class FallbackProvider(SoilDataProvider):
    def __init__(self):
        self.providers = [
            iSDAProvider(),
            SoilGridsProvider()
        ]
    
    def get_soil_properties(self, lat, lon):
        for provider in self.providers:
            try:
                res = provider.get_soil_properties(lat, lon)
                if res:
                    try:
                        cache_path = os.path.join(os.path.dirname(__file__), "data", "satellite_cache.csv")
                        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                        
                        cache_row = {
                            "timestamp": datetime.datetime.now().isoformat(),
                            "latitude": lat,
                            "longitude": lon,
                            **res
                        }
                        df = pd.DataFrame([cache_row])
                        if not os.path.exists(cache_path):
                            df.to_csv(cache_path, index=False)
                        else:
                            df.to_csv(cache_path, mode='a', header=False, index=False)
                    except Exception:
                        pass
                    return res
            except Exception:
                continue
        raise Exception("All data sources unavailable")
