import pandas as pd
import os
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEALERS_CSV = os.path.join(BASE_DIR, "data", "dealers.csv")

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on the earth."""
    R = 6371  # Earth radius in kilometers
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2)**2
    return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

def _load_dealers():
    if os.path.exists(DEALERS_CSV):
        df = pd.read_csv(DEALERS_CSV)
        dealers = []
        for _, row in df.iterrows():
            dealers.append({
                "name": row["name"],
                "county": row["county"],
                "town": row["town"],
                "lat": float(row["lat"]) if pd.notnull(row.get("lat")) else None,
                "lon": float(row["lon"]) if pd.notnull(row.get("lon")) else None,
                "phone": str(row["phone"]) if pd.notnull(row.get("phone")) else "",
                "stocks": [s.strip() for s in str(row.get("stocks", "")).split(",")]
            })
        return dealers
    return []

DEALERS = _load_dealers()

def get_dealers_by_proximity(lat, lon, radius_km=50):
    """Returns dealers sorted by distance, filtered by radius."""
    if lat is None or lon is None:
        return []
        
    results = []
    for d in DEALERS:
        if d["lat"] is not None and d["lon"] is not None:
            dist = haversine(lat, lon, d["lat"], d["lon"])
            if dist <= radius_km:
                d_with_dist = d.copy()
                d_with_dist["distance"] = round(dist, 1)
                results.append(d_with_dist)
    
    # Sort by distance (closest first)
    return sorted(results, key=lambda x: x["distance"])

def get_dealers_by_county(county_name):
    """Original county-level fallback."""
    results = [d for d in DEALERS if str(d["county"]).lower() == str(county_name).lower()]
    if not results:
        results = [d for d in DEALERS if d["county"] == "All"]
    return results
