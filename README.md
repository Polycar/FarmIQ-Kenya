# 🌱 FarmIQ Kenya: National Precision Agriculture Platform

FarmIQ is a scientifically rigorous, data-driven soil intelligence platform designed to move Kenya from regional county averages to meter-level agricultural precision.

![FarmIQ Screenshot](https://img.icons8.com/color/96/agriculture.png)

## 🚀 Vision
To eliminate regional bias in agricultural advice by providing hyper-localized soil insights and fertilizer recommendations for all 47 Kenyan counties based on 30m-resolution satellite data and "Ground Truth" expert lab overrides.

## 🔬 Data Integrity & Fallback Architecture
To ensure scientific credibility even when external services encounter outages, FarmIQ utilizes a decoupled, multi-tier fallback data engine:

1. **Primary: iSDAsoil API** (30m high-resolution spatial precision).
2. **Secondary: ISRIC SoilGrids API** (250m resolution global dataset).
3. **Local Baseline & GeoTIFF Cache**: High-resolution AWS rasters (e.g., `data/rasters/kenya_ph.tif`) paired with regional statistical averages for zero-downtime offline access.
4. **Expert Lab Overrides**: Allowing physical soil testing overrides securely.

> [!NOTE]
> The app explicitly labels the **Source of Data** in every generated report to ensure complete transparency for agronomists and funders.

## ✨ Key Features
- **Precision-First Mapping**: Sample 30m-resolution iSDAsoil datasets using GPS coordinates.
- **National Geographic Neutrality**: A completely unbiased UI that supports any location in Kenya without hardcoded regional defaults.
- **Expert Lab Mode**: Allow extension officers and farmers to override satellite data with physical soil test results.
- **Scientific Soil Health Score**: Replaced unrealistic binary scores with a SIGMOID-weighted Soil Quality Index (SQI).
- **Dynamic Dealer Locator**: Automatically find verified agro-dealers near your shamba with direct navigation links.
- **Multi-lingual Support**: Full support for English and Kiswahili.

## 🛠️ Tech Stack
- **Dashboard**: Streamlit
- **Spatial Engine**: Rasterio & NumPy
- **Database**: SQLite & SQLAlchemy
- **Reports**: FPDF2
- **Styling**: Vanilla CSS with Glassmorphism aesthetics

## 📦 Installation & Data Setup

1. **Clone & Install**
   ```bash
   git clone https://github.com/Polycar/FarmIQ-Kenya.git
   pip install -r requirements.txt
   ```

2. **High-Resolution Data (Optional)**
   The full `kenya_ph.tif` (308MB) is excluded from GitHub. In production, this should be hosted in Cloud Storage or added to the `data/rasters/` folder manually. 
   Without this file, the app uses **Regional Baseline (CSV)** averages.

3. **Run Locally**
   ```bash
   streamlit run app.py
   ```

## 🗺️ Multi-Phase Roadmap

* **Phase 1 (Current):** Offline baseline GeoTIFF caching deployed.
* **Phase 2 (Next Month):** Migrate architectures to Google Earth Engine (GEE) parameters.
* **Phase 3 (Month 6):** Execute abstract provider loops securely.
* **Phase 4 (Month 12):** Collect ground truth vectors via physical farm pilot partnerships.

## 📈 Scientific Attribution
Soil chemistry metrics utilize the **iSDAsoil Africa Grid (2021)**. Nutrient threshold calculations reflect Kenyan Agronomic Baselines comfortably.

---
*Developed for the future of Kenyan Agriculture.*
