# iSDAsoil API Integration for FarmIQ Kenya
# Provides 30m precision soil data for ALL nutrients (pH, N, P, K, OC)
# Requires free registration at https://api.isda-africa.com

import requests
import streamlit as st
import os

# API Configuration
BASE_URL = "https://api.isda-africa.com/isdasoil/v2"

# Soil properties we need for FarmIQ recommendations
SOIL_PROPERTIES = [
    "ph",
    "nitrogen_total",
    "phosphorous_extractable",
    "potassium_extractable",
    "carbon_organic"
]

def _get_api_credentials():
    """Retrieve API credentials from Streamlit secrets or environment."""
    try:
        username = st.secrets.get("ISDA_USERNAME", os.environ.get("ISDA_USERNAME"))
        password = st.secrets.get("ISDA_PASSWORD", os.environ.get("ISDA_PASSWORD"))
        return username, password
    except Exception:
        return None, None

def _get_auth_token():
    """Authenticate with iSDAsoil API and return JWT token."""
    username, password = _get_api_credentials()
    if not username or not password:
        return None
    
    try:
        response = requests.post(
            f"{BASE_URL}/login",
            json={"username": username, "password": password},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data.get("token") or data.get("access_token")
    except Exception:
        return None

def fetch_soil_property(lat, lon, property_name, depth="0-20", token=None):
    """Fetch a single soil property from the iSDAsoil API."""
    if not token:
        return None
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "lat": lat,
            "lon": lon,
            "property": property_name,
            "depth": depth
        }
        response = requests.get(
            f"{BASE_URL}/soilproperty",
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        # Extract the predicted mean value
        if isinstance(data, dict):
            # API returns property data with mean/uncertainty
            for key, val in data.items():
                if "mean" in str(key).lower() or "value" in str(key).lower():
                    return float(val)
            # Try direct numeric extraction from response
            if property_name in data:
                prop_data = data[property_name]
                if isinstance(prop_data, dict):
                    return float(prop_data.get("mean", prop_data.get("value", 0)))
                return float(prop_data)
        return None
    except Exception:
        return None

def get_precision_soil_data(lat, lon):
    """
    Fetch ALL soil properties at 30m precision for a given GPS coordinate.
    
    Returns a dict compatible with FarmIQ's soil data format, or None if API unavailable.
    This is the main entry point used by recommender.py.
    
    Fallback chain:
        1. iSDAsoil API (all nutrients at 30m) ← THIS FUNCTION
        2. Local GeoTIFF (pH only at 30m)       ← existing get_high_res_ph()
        3. County CSV averages                   ← existing get_county_data()
    """
    token = _get_auth_token()
    if not token:
        return None
    
    results = {}
    property_map = {
        "ph": "pH",
        "nitrogen_total": "Total Nitrogen (mg/kg)",
        "phosphorous_extractable": "Extractable Phosphorus (mg/kg)",
        "potassium_extractable": "Extractable Potassium (mg/kg)",
        "carbon_organic": "Organic Carbon (g/kg)"
    }
    
    for api_name, farmiq_name in property_map.items():
        value = fetch_soil_property(lat, lon, api_name, token=token)
        if value is not None:
            results[farmiq_name] = value
    
    # Only return if we got at least pH (minimum viable data)
    if "pH" in results:
        return results
    return None

def is_api_configured():
    """Check if iSDAsoil API credentials are set up."""
    username, password = _get_api_credentials()
    return bool(username and password)
