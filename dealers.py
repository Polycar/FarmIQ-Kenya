# Agro-dealer Database for FarmIQ Kenya (CSV-Driven)
# Data is loaded from data/dealers.csv — edit that file to add/update dealers

import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEALERS_CSV = os.path.join(BASE_DIR, "data", "dealers.csv")

def _load_dealers():
    """Load dealers from CSV file. Returns list of dicts."""
    if os.path.exists(DEALERS_CSV):
        df = pd.read_csv(DEALERS_CSV)
        dealers = []
        for _, row in df.iterrows():
            dealers.append({
                "name": row["name"],
                "county": row["county"],
                "town": row["town"],
                "stocks": [s.strip() for s in str(row["stocks"]).split(",")]
            })
        return dealers
    return []

DEALERS = _load_dealers()

def get_dealers_by_county(county_name):
    """
    Intelligent filter that returns local specific dealers if available,
    otherwise falls back to National Distributors (KFA/KNTC).
    """
    results = [d for d in DEALERS if d["county"].lower() == county_name.lower()]
    if not results:
        results = [d for d in DEALERS if d["county"] == "All"]
    return results
