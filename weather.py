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
        
        daily = data.get("daily", {})
        precip_list = daily.get("precipitation_sum", [])
        time_list = daily.get("time", [])
        
        if not precip_list or not time_list:
            return "⚠️ Weather forecast data is currently unavailable."
            
        total_rain = sum([p for p in precip_list if p is not None])
        
        # Scenario 1: Heavy Rain (Risk of Runoff)
        if total_rain > 50:
            # Find the first clear day (< 2mm rain) in the API forecast
            clear_day = None
            for t, p in zip(time_list, precip_list):
                if p is not None and p < 2.0:
                    clear_day = t
                    break
            
            if clear_day:
                # Format the date nicely
                try:
                    date_obj = pd.to_datetime(clear_day)
                    date_str = date_obj.strftime('%A, %b %d')
                except:
                    date_str = clear_day
                return f"🌧️ **Heavy rain expected** ({total_rain:.1f}mm) — hold off on fertilizer to avoid runoff. **Safe window opens on {date_str}**."
            else:
                return f"🌧️ **Heavy rain expected** ({total_rain:.1f}mm) — runoff risk is high for the next 7 days. Hold off application."

        # Scenario 2: Too Dry (Top dressing needs moisture to dissolve)
        elif total_rain < 5:
            # Look for the first rain day (> 2mm) to advise application
            rain_day = None
            for t, p in zip(time_list, precip_list):
                if p is not None and p >= 2.0:
                    rain_day = t
                    break
            
            if rain_day:
                try:
                    date_obj = pd.to_datetime(rain_day)
                    date_str = date_obj.strftime('%A, %b %d')
                except:
                    date_str = rain_day
                return f"⚠️ **Dry week ahead** ({total_rain:.1f}mm) — fertilizer may not dissolve. **Apply on {date_str}** when light rain is predicted."
            else:
                return f"⚠️ **Very dry week** ({total_rain:.1f}mm) — avoid top dressing as fertilizer will not dissolve. Wait for rain."

        # Scenario 3: Optimal
        else:
            return f"✅ **Optimal conditions** ({total_rain:.1f}mm expected). Good moisture for fertilizer absorption this week."
            
    except requests.exceptions.RequestException as e:
        return f"⚠️ Could not fetch weather forecast at this time (API Error: {str(e)})."
    except Exception as e:
        return f"⚠️ Error processing weather forecast ({str(e)})."
