import pandas as pd
import os
import numpy as np
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEALERS_CSV = os.path.join(BASE_DIR, "data", "dealers.csv")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi / 2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2)**2
    return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

def get_live_osm_dealers(lat, lon, radius_km=30):
    """
    Queries OpenStreetMap (Overpass API) for live Agrovets nearby.
    Completely free and location-accurate.
    """
    if lat is None or lon is None: return []
    
    # Overpass QL: Search for nodes/ways with 'agrovet' or 'farm' tags within radius
    radius_meters = radius_km * 1000
    query = f"""
    [out:json][timeout:25];
    (
      node["shop"~"agronomist|farm|hardware"](around:{radius_meters},{lat},{lon});
      node["name"~"Agrovet|Farm",i](around:{radius_meters},{lat},{lon});
      way["shop"~"agronomist|farm|hardware"](around:{radius_meters},{lat},{lon});
    );
    out center;
    """
    url = "https://overpass-api.de/api/interpreter"
    
    try:
        resp = requests.get(url, params={'data': query}, timeout=20)
        if resp.status_code == 200:
            data = resp.json().get('elements', [])
            results = []
            for e in data:
                e_lat = e.get('lat') or e.get('center', {}).get('lat')
                e_lon = e.get('lon') or e.get('center', {}).get('lon')
                if e_lat and e_lon:
                    dist = haversine(lat, lon, e_lat, e_lon)
                    tags = e.get('tags', {})
                    results.append({
                        "name": tags.get('name', 'Local Agrovet'),
                        "town": tags.get('addr:city', tags.get('addr:town', 'Nearby')),
                        "lat": e_lat, "lon": e_lon,
                        "distance": round(dist, 1),
                        "source": "OpenStreetMap (Live)"
                    })
            return sorted(results, key=lambda x: x["distance"])
    except: pass
    return []

def get_dealers_by_proximity(lat, lon, radius_km=50):
    """Tier 2: Search internal CSV for specific dealers."""
    if lat is None or lon is None: return []
    if not os.path.exists(DEALERS_CSV): return []
    
    df = pd.read_csv(DEALERS_CSV)
    results = []
    for _, row in df.iterrows():
        d_lat, d_lon = row.get("lat"), row.get("lon")
        if pd.notnull(d_lat) and pd.notnull(d_lon):
            dist = haversine(lat, lon, float(d_lat), float(d_lon))
            if dist <= radius_km:
                results.append({
                    "name": row["name"], "town": row["town"],
                    "lat": float(d_lat), "lon": float(d_lon),
                    "distance": round(dist, 1),
                    "source": "Verified Database"
                })
    return sorted(results, key=lambda x: x["distance"])

def get_dealers_by_county(county_name):
    if not os.path.exists(DEALERS_CSV): return []
    df = pd.read_csv(DEALERS_CSV)
    res = df[df["county"].str.lower() == county_name.lower()]
    return res.to_dict('records') if not res.empty else []
