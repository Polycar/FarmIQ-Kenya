"""
FarmIQ Kenya - Phase 1: Mock Soil Data Generator
==============================================================
Since downloading 30m resolution continent-scale COG rasters
takes too long for an MVP, we are generating realistic agronomic
baseline data based on Kenyan Agroecological Zones.

Output: data/kenya_county_soils.csv
"""

import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Define average soil baselines for each Agroecological Zone
# Based on typical Kenyan soil profiles
ZONE_BASELINES = {
    "Central Highlands": {"ph": 5.2, "n": 1.2, "p": 15, "k": 180, "oc": 25}, # Acidic, moderate organic
    "Rift Valley": {"ph": 6.1, "n": 1.5, "p": 25, "k": 220, "oc": 20},       # Volcanic, relatively fertile
    "Lake Victoria Basin": {"ph": 5.5, "n": 1.0, "p": 12, "k": 150, "oc": 18}, # Acidic, depleted
    "Western": {"ph": 5.4, "n": 1.1, "p": 14, "k": 160, "oc": 19},           # Acidic, similar to lake basin
    "Mt. Kenya": {"ph": 5.0, "n": 1.4, "p": 18, "k": 200, "oc": 28},         # Volcanic, very acidic, high C
    "Semi-arid Eastern": {"ph": 7.2, "n": 0.8, "p": 30, "k": 350, "oc": 10}, # Alkaline, low C, high K
    "Coastal": {"ph": 6.5, "n": 0.9, "p": 10, "k": 120, "oc": 12},           # Sandy, leached
    "Arid North": {"ph": 8.0, "n": 0.5, "p": 40, "k": 400, "oc": 5},          # Very alkaline, poor N
    "Arid North-East": {"ph": 8.1, "n": 0.5, "p": 38, "k": 410, "oc": 6},
    "Nairobi Metro": {"ph": 6.8, "n": 1.1, "p": 20, "k": 250, "oc": 15},     # Transition zone
    "Other": {"ph": 6.5, "n": 1.0, "p": 20, "k": 200, "oc": 15}
}

ZONE_MAP = {
    "Kiambu": "Central Highlands", "Kirinyaga": "Central Highlands",
    "Murang'a": "Central Highlands", "Nyeri": "Central Highlands",
    "Nyandarua": "Central Highlands", "Embu": "Central Highlands",
    "Nakuru": "Rift Valley", "Narok": "Rift Valley", "Baringo": "Rift Valley",
    "Kericho": "Rift Valley", "Bomet": "Rift Valley", "Nandi": "Rift Valley",
    "Uasin Gishu": "Rift Valley", "Elgeyo Marakwet": "Rift Valley",
    "Trans Nzoia": "Rift Valley", "West Pokot": "Rift Valley",
    "Kisumu": "Lake Victoria Basin", "Siaya": "Lake Victoria Basin",
    "Homa Bay": "Lake Victoria Basin", "Migori": "Lake Victoria Basin",
    "Kisii": "Lake Victoria Basin", "Nyamira": "Lake Victoria Basin",
    "Kakamega": "Western", "Vihiga": "Western",
    "Bungoma": "Western", "Busia": "Western",
    "Meru": "Mt. Kenya", "Tharaka Nithi": "Mt. Kenya",
    "Laikipia": "Mt. Kenya",
    "Machakos": "Semi-arid Eastern", "Makueni": "Semi-arid Eastern",
    "Kitui": "Semi-arid Eastern",
    "Mombasa": "Coastal", "Kilifi": "Coastal", "Kwale": "Coastal",
    "Lamu": "Coastal", "Taita Taveta": "Coastal", "Tana River": "Coastal",
    "Turkana": "Arid North", "Marsabit": "Arid North",
    "Samburu": "Arid North", "Isiolo": "Arid North",
    "Garissa": "Arid North-East", "Wajir": "Arid North-East",
    "Mandera": "Arid North-East",
    "Nairobi": "Nairobi Metro", "Kajiado": "Nairobi Metro",
}

def main():
    import random
    random.seed(42) # For reproducible mock data
    
    records = []
    
    for county, zone in ZONE_MAP.items():
        base = ZONE_BASELINES.get(zone, ZONE_BASELINES["Other"])
        
        # Add a tiny bit of random noise for realism
        ph = round(base["ph"] + random.uniform(-0.3, 0.3), 2)
        n = round(base["n"] + random.uniform(-0.2, 0.2), 2)
        p = round(base["p"] + random.uniform(-3, 3), 1)
        k = round(base["k"] + random.uniform(-20, 20), 0)
        oc = round(base["oc"] + random.uniform(-3, 3), 1)
        
        records.append({
            "County": county,
            "Agroecological Zone": zone,
            "pH": ph,
            "Total Nitrogen (mg/kg)": n,
            "Extractable Phosphorus (mg/kg)": p,
            "Extractable Potassium (mg/kg)": k,
            "Organic Carbon (g/kg)": oc
        })
        
    df = pd.DataFrame(records)
    
    output_path = os.path.join(DATA_DIR, "kenya_county_soils.csv")
    df.to_csv(output_path, index=False)
    
    print("=" * 60)
    print(f"✅ Created realistic baseline soil data for {len(df)} counties.")
    print(f"Saved to: {output_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
