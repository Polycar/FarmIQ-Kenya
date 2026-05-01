"""
FarmIQ Kenya - Phase 1: Automated Soil Data Extraction (FAST)
==============================================================
Strategy: Download Kenya-extent subsets of each iSDAsoil raster
ONCE, then do all 47 county zonal stats locally. ~5 min total.

Output: data/kenya_county_soils.csv
"""

import os
import sys
import warnings
import subprocess
import requests
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape, MultiPolygon, Polygon, GeometryCollection
from shapely.ops import transform as shp_transform
from pyproj import Transformer
import rasterio
from rasterio.mask import mask as rio_mask

warnings.filterwarnings("ignore")

# ----------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RASTER_DIR = os.path.join(DATA_DIR, "rasters")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RASTER_DIR, exist_ok=True)

S3_BASE = "https://isdasoil.s3.amazonaws.com/soil_data"

# Kenya bounding box (WGS84)
KENYA_BBOX = (33.9, -4.7, 41.9, 5.5)  # min_lon, min_lat, max_lon, max_lat

SOIL_PROPERTIES = {
    "ph": {
        "url": f"{S3_BASE}/ph/ph.tif",
        "label": "pH",
        "band": 1,
        "convert": lambda x: x / 10,
    },
    "nitrogen_total": {
        "url": f"{S3_BASE}/nitrogen_total/nitrogen_total.tif",
        "label": "Total Nitrogen (g/kg)",
        "band": 1,
        "convert": lambda x: x,
    },
    "phosphorous_extractable": {
        "url": f"{S3_BASE}/phosphorous_extractable/phosphorous_extractable.tif",
        "label": "Extractable Phosphorus (mg/kg)",
        "band": 1,
        "convert": lambda x: x,
    },
    "potassium_extractable": {
        "url": f"{S3_BASE}/potassium_extractable/potassium_extractable.tif",
        "label": "Extractable Potassium (mg/kg)",
        "band": 1,
        "convert": lambda x: x,
    },
    "carbon_organic": {
        "url": f"{S3_BASE}/carbon_organic/carbon_organic.tif",
        "label": "Organic Carbon (g/kg)",
        "band": 1,
        "convert": lambda x: x / 10,
    },
}

COUNTY_NAMES = [
    "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo Marakwet",
    "Embu", "Garissa", "Homa Bay", "Isiolo", "Kajiado",
    "Kakamega", "Kericho", "Kiambu", "Kilifi", "Kirinyaga",
    "Kisii", "Kisumu", "Kitui", "Kwale", "Laikipia",
    "Lamu", "Machakos", "Makueni", "Mandera", "Marsabit",
    "Meru", "Migori", "Mombasa", "Murang'a", "Nairobi",
    "Nakuru", "Nandi", "Narok", "Nyamira", "Nyandarua",
    "Nyeri", "Samburu", "Siaya", "Taita Taveta", "Tana River",
    "Tharaka Nithi", "Trans Nzoia", "Turkana", "Uasin Gishu",
    "Vihiga", "Wajir", "West Pokot"
]

TO_3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

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


# ----------------------------------------------------------------
# STEP 1: Download Kenya-extent rasters (5 files, ~30s each)
# ----------------------------------------------------------------

def download_kenya_raster(prop_key, prop_info):
    """
    Download just the Kenya bounding-box subset of a COG using
    rasterio's windowed read via /vsicurl/. Much faster than
    per-county reads.
    """
    local_path = os.path.join(RASTER_DIR, f"kenya_{prop_key}.tif")

    if os.path.exists(local_path):
        print(f"  CACHED {prop_info['label']} -> {local_path}")
        return local_path

    print(f"  Downloading {prop_info['label']}...", end="", flush=True)

    vsicurl_url = f"/vsicurl/{prop_info['url']}"

    # Transform Kenya bbox to EPSG:3857
    min_lon, min_lat, max_lon, max_lat = KENYA_BBOX
    x_min, y_min = TO_3857.transform(min_lon, min_lat)
    x_max, y_max = TO_3857.transform(max_lon, max_lat)

    try:
        with rasterio.open(vsicurl_url) as src:
            # Get the window for Kenya's extent
            window = rasterio.windows.from_bounds(
                x_min, y_min, x_max, y_max, src.transform
            )

            # Read only band 1 (0-20cm mean) within the window
            data = src.read(prop_info["band"], window=window)
            transform = src.window_transform(window)

            # Write local GeoTIFF
            profile = src.profile.copy()
            profile.update({
                "count": 1,
                "height": data.shape[0],
                "width": data.shape[1],
                "transform": transform,
                "compress": "lzw",
            })

            with rasterio.open(local_path, "w", **profile) as dst:
                dst.write(data, 1)

        print(f" OK ({data.shape[1]}x{data.shape[0]} px)")
        return local_path

    except Exception as e:
        print(f" FAILED: {e}")
        return None


def download_all_rasters():
    """Download Kenya subsets for all 5 soil properties."""
    print("[1/4] Downloading Kenya-extent rasters from iSDAsoil AWS...")

    paths = {}
    for key, info in SOIL_PROPERTIES.items():
        path = download_kenya_raster(key, info)
        if path:
            paths[key] = path

    print(f"  Downloaded {len(paths)}/5 rasters.\n")
    return paths


# ----------------------------------------------------------------
# STEP 2: Load county boundaries
# ----------------------------------------------------------------

def county_to_filename(name):
    return name.lower().replace("'", "").replace(" ", "-")


def extract_polygons(geom):
    """Extract Polygon/MultiPolygon parts from any geometry."""
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    elif geom.geom_type == "MultiPolygon":
        return geom
    elif geom.geom_type == "GeometryCollection":
        polys = []
        for g in geom.geoms:
            if g.geom_type == "Polygon":
                polys.append(g)
            elif g.geom_type == "MultiPolygon":
                polys.extend(g.geoms)
        return MultiPolygon(polys) if polys else None
    return None


def reproject_geom(geom_4326):
    return shp_transform(TO_3857.transform, geom_4326)


def load_county_boundaries():
    print("[2/4] Loading Kenya county boundaries from GitHub...")

    base_url = "https://raw.githubusercontent.com/Mondieki/kenya-counties-subcounties/master/geojson"
    records = []

    for county in COUNTY_NAMES:
        fname = county_to_filename(county)
        url = f"{base_url}/{fname}.json"

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            geo = resp.json()

            if geo.get("type") == "FeatureCollection":
                raw = shape(geo["features"][0]["geometry"])
            elif geo.get("type") == "Feature":
                raw = shape(geo["geometry"])
            else:
                raw = shape(geo)

            geom = extract_polygons(raw)
            if geom is None or geom.is_empty:
                print(f"  SKIP {county}")
                continue

            records.append({
                "county": county,
                "geometry": geom,
                "geometry_3857": reproject_geom(geom),
            })
            print(f"  OK   {county}")

        except Exception as e:
            print(f"  FAIL {county}: {e}")

    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    print(f"  Loaded {len(gdf)}/47 counties.\n")
    return gdf


# ----------------------------------------------------------------
# STEP 3: Zonal statistics (LOCAL - very fast)
# ----------------------------------------------------------------

def compute_county_mean(local_raster_path, geom_3857, convert_fn):
    """Compute mean value for a county from a LOCAL raster. Very fast."""
    try:
        with rasterio.open(local_raster_path) as src:
            out_image, _ = rio_mask(
                src, [geom_3857], crop=True, indexes=[1], filled=True
            )
            nodata = src.nodata if src.nodata is not None else 255
            valid = out_image[out_image != nodata].astype(float)

            if len(valid) == 0:
                return None

            return round(float(convert_fn(np.mean(valid))), 2)

    except Exception:
        return None


def extract_all_soil_data(gdf, raster_paths):
    """Compute zonal stats for all counties x all properties (LOCAL)."""
    print("[3/4] Computing county-level soil statistics (local processing)...")

    results = []
    n = len(gdf)

    for idx, row in gdf.iterrows():
        county = row["county"]
        geom_3857 = row["geometry_3857"]
        county_data = {"County": county}

        vals = []
        for prop_key, prop_info in SOIL_PROPERTIES.items():
            if prop_key not in raster_paths:
                county_data[prop_info["label"]] = None
                continue

            val = compute_county_mean(
                raster_paths[prop_key], geom_3857, prop_info["convert"]
            )
            county_data[prop_info["label"]] = val
            vals.append(f"{prop_info['label']}={val}")

        print(f"  [{idx+1}/{n}] {county}: {', '.join(vals)}")
        results.append(county_data)

    return pd.DataFrame(results)


# ----------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------

def main():
    print("=" * 60)
    print("  FarmIQ Kenya -- Soil Data Extraction Pipeline (Fast)")
    print("  47 Counties x 5 Soil Properties")
    print("=" * 60)
    print()

    # Step 1: Download Kenya-extent rasters (5 fast downloads)
    raster_paths = download_all_rasters()
    if not raster_paths:
        print("ERROR: No rasters downloaded. Exiting.")
        sys.exit(1)

    # Step 2: Load county boundaries
    gdf = load_county_boundaries()
    if len(gdf) == 0:
        print("ERROR: No counties loaded. Exiting.")
        sys.exit(1)

    # Step 3: Local zonal stats (fast)
    df = extract_all_soil_data(gdf, raster_paths)

    # Step 4: Add zone classification
    df["Agroecological Zone"] = df["County"].map(ZONE_MAP).fillna("Other")
    cols = ["County", "Agroecological Zone"] + [
        c for c in df.columns if c not in ["County", "Agroecological Zone"]
    ]
    df = df[cols]

    # Save
    output_path = os.path.join(DATA_DIR, "kenya_county_soils.csv")
    df.to_csv(output_path, index=False)

    print()
    print("=" * 60)
    print(f"  DONE! Saved to: {output_path}")
    print(f"  Counties: {len(df)}, Properties: {len(SOIL_PROPERTIES)}")
    print("=" * 60)
    print()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
