import requests

def get_county_coordinates(county_name):
    # A quick mapping of major counties to rough center coordinates for weather fallback
    coords = {
        "Nakuru": (-0.3031, 36.0800), "Uasin Gishu": (0.5143, 35.2698), 
        "Trans Nzoia": (1.0191, 35.0023), "Narok": (-1.0889, 35.8749),
        "Kericho": (-0.3689, 35.2863), "Kiambu": (-1.1714, 36.8356),
        "Nyeri": (-0.4167, 36.9500), "Murang'a": (-0.7167, 37.1500),
        "Machakos": (-1.5167, 37.2667), "Meru": (0.0500, 37.6500),
        "Kakamega": (0.2833, 34.7500), "Bungoma": (0.5667, 34.5667),
        "Kisumu": (-0.1022, 34.7617), "Nairobi": (-1.2921, 36.8219),
        "Bomet": (-0.7813, 35.3416), "Busia": (0.4608, 34.1115),
        "Embu": (-0.5311, 37.4506), "Garissa": (-0.4532, 39.6461),
        "Isiolo": (0.3546, 37.5833), "Kajiado": (-1.8524, 36.7768),
        "Kilifi": (-3.5107, 39.9093), "Kirinyaga": (-0.5000, 37.2833),
        "Kisii": (-0.6817, 34.7667), "Kitui": (-1.3667, 38.0167),
        "Kwale": (-4.1816, 39.4606), "Laikipia": (0.3333, 36.8333),
        "Lamu": (-2.2717, 40.9020), "Makueni": (-1.8000, 37.6167),
        "Mandera": (3.9167, 41.8333), "Marsabit": (2.3333, 37.9833),
        "Migori": (-1.0667, 34.4667), "Mombasa": (-4.0435, 39.6682),
        "Nandi": (0.1833, 35.1333), "Nyandarua": (-0.1833, 36.3667),
        "Nyamira": (-0.5667, 34.9333), "Samburu": (1.3333, 36.8333),
        "Siaya": (0.0667, 34.2833), "Taita Taveta": (-3.3167, 38.4833),
        "Tana River": (-1.5000, 40.0000), "Tharaka Nithi": (-0.3000, 38.0000),
        "Turkana": (3.1167, 35.6000), "Vihiga": (0.0833, 34.7167),
        "Wajir": (1.7500, 40.0500), "West Pokot": (1.2500, 35.1167),
        "Homa Bay": (-0.5167, 34.4500), "Elgeyo Marakwet": (0.8000, 35.5333),
        "Baringo": (0.4667, 35.9833)
    }
    # Fallback to center of Kenya if somehow unknown
    return coords.get(county_name, (0.0236, 37.9062))



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
