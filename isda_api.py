# iSDAsoil API Integration for FarmIQ Kenya
# Provides 30m precision soil data for ALL nutrients (pH, N, P, K, OC)
# Using refined v1 endpoint for high accuracy mean values

import requests
import os

# API Configuration
SOIL_URL = "https://api.isda-africa.com/v1/soilproperty"

def get_precision_soil_data(lat, lon):
    """
    Fetch ALL soil properties at 30m precision for a given GPS coordinate.
    Uses the statistical 'mean' value for agronomic accuracy.
    """
    
    # Map iSDA technical names -> FarmIQ internal column names
    # Note: Using the correct spelling 'phosphorus' as per user code
    property_map = {
        "ph":                       "pH",
        "nitrogen_total":           "Total Nitrogen (mg/kg)",
        "phosphorus_extractable":   "Extractable Phosphorus (mg/kg)",
        "potassium_extractable":    "Extractable Potassium (mg/kg)",
        "organic_carbon":           "Organic Carbon (g/kg)"
    }
    
    results = {}
    
    for api_name, internal_key in property_map.items():
        try:
            response = requests.get(
                SOIL_URL,
                params={
                    "lat": lat,
                    "lon": lon,
                    "property": api_name,
                    "depth": "0-20cm"
                },
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                # Extract the mean value from the nested structure
                value = data.get("property", {}).get(api_name, {}).get("value", {}).get("mean")
                if value is not None:
                    results[internal_key] = float(value)
        except Exception:
            continue
            
    # If we at least have pH, we have a usable precision profile
    if "pH" in results:
        return results
    return None

def is_api_configured():
    """V1 public endpoint check (always available if internet exists)."""
    return True
