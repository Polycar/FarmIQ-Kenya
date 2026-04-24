import requests
import pandas as pd
import os

def get_county_coordinates(county_name):
    """Load county coordinates from CSV. Single source of truth: data/county_coordinates.csv"""
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "county_coordinates.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        match = df[df["County"] == county_name]
        if not match.empty:
            row = match.iloc[0]
            return (row["Latitude"], row["Longitude"])
    # Fallback to center of Kenya if unknown
    return (0.0236, 37.9062)



def get_weather_context(lat, lon):
    if lat is None or lon is None or (lat == 0.0 and lon == 0.0):
        return None
        
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum",
        "timezone": "Africa/Nairobi",
        "forecast_days": 7
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        daily_precipitation = data.get("daily", {}).get("precipitation_sum", [])
        # Filter out None values in case of missing data
        valid_precipitation = [p for p in daily_precipitation if p is not None]
        
        if not valid_precipitation:
            return "⚠️ Weather forecast data is currently unavailable."
            
        total_rain = sum(valid_precipitation)
        
        if total_rain < 5:
            return f"⚠️ Dry week ahead ({total_rain:.1f}mm expected) — delay top dressing until after rain."
        elif total_rain > 50:
            return f"🌧️ Heavy rain expected ({total_rain:.1f}mm expected) — hold off on fertilizer application to avoid runoff."
        else:
            return f"✅ Good conditions for fertilizer application this week ({total_rain:.1f}mm expected)."
            
    except requests.exceptions.RequestException as e:
        return "⚠️ Could not fetch weather forecast at this time (API Error)."
    except Exception as e:
        return "⚠️ Error processing weather forecast."
