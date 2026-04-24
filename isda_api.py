# iSDAsoil API Integration for FarmIQ Kenya
# Provides 30m precision soil data for ALL nutrients (pH, N, P, K, OC)
# Registration: https://www.isda-africa.com/api/registration

import requests
import os

# API Configuration
LOGIN_URL = "https://api.isda-africa.com/login"
SOIL_URL = "https://api.isda-africa.com/isdasoil/v2/soilproperty"

# Cache token to avoid re-authenticating on every property query
_cached_token = None

def _get_api_credentials():
    """Retrieve API credentials from Streamlit secrets or environment."""
    try:
        import streamlit as st
        username = st.secrets.get("ISDA_USERNAME", os.environ.get("ISDA_USERNAME"))
        password = st.secrets.get("ISDA_PASSWORD", os.environ.get("ISDA_PASSWORD"))
        return username, password
    except Exception:
        username = os.environ.get("ISDA_USERNAME")
        password = os.environ.get("ISDA_PASSWORD")
        return username, password

def _get_auth_token():
    """Authenticate with iSDAsoil API and return JWT token (cached for 1 hour)."""
    global _cached_token
    if _cached_token:
        return _cached_token
    
    username, password = _get_api_credentials()
    if not username or not password:
        return None
    
    try:
        response = requests.post(
            LOGIN_URL,
            data={"username": username, "password": password},
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        _cached_token = data.get("access_token")
        return _cached_token
    except Exception:
        return None

def _fetch_single_property(lat, lon, property_name, depth="0-20", token=None):
    """Fetch a single soil property value from the iSDAsoil API."""
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
        response = requests.get(SOIL_URL, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Response structure: {"property": {"ph": [{"value": {"value": 5.7, "unit": ...}, ...}]}}
        prop_data = data.get("property", {}).get(property_name, [])
        if prop_data and len(prop_data) > 0:
            return float(prop_data[0]["value"]["value"])
        return None
    except Exception:
        return None

def get_precision_soil_data(lat, lon):
    """
    Fetch ALL soil properties at 30m precision for a given GPS coordinate.
    
    Returns a dict compatible with FarmIQ's soil data format, or None if API unavailable.
    
    Fallback chain:
        1. iSDAsoil API (all nutrients at 30m)  <-- THIS FUNCTION
        2. Local GeoTIFF (pH only at 30m)        <-- existing get_high_res_ph()
        3. County CSV averages                   <-- existing get_county_data()
    """
    token = _get_auth_token()
    if not token:
        return None
    
    # Map API property names to FarmIQ internal column names
    property_map = {
        "ph":                       "pH",
        "nitrogen_total":           "Total Nitrogen (mg/kg)",
        "phosphorous_extractable":  "Extractable Phosphorus (mg/kg)",
        "potassium_extractable":    "Extractable Potassium (mg/kg)",
        "carbon_organic":           "Organic Carbon (g/kg)"
    }
    
    results = {}
    for api_name, farmiq_name in property_map.items():
        value = _fetch_single_property(lat, lon, api_name, token=token)
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
