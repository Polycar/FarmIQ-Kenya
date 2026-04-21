# 🌱 FarmIQ Kenya: National Precision Agriculture Platform

FarmIQ is a scientifically rigorous, data-driven soil intelligence platform designed to move Kenya from regional county averages to meter-level agricultural precision.

![FarmIQ Screenshot](https://img.icons8.com/color/96/agriculture.png)

## 🚀 Vision
To eliminate regional bias in agricultural advice by providing hyper-localized soil insights and fertilizer recommendations for all 47 Kenyan counties based on 30m-resolution satellite data and "Ground Truth" expert lab overrides.

## 🔬 Data Integrity & Fallback Architecture
To ensure scientific credibility even when large satellite rasters are unavailable in low-bandwidth environments, FarmIQ uses a dual-layer data strategy:

1. **Layer 1: 30m Precision (Raster)**: If the `kenya_ph.tif` file is present in `data/rasters/`, the app samples hyper-localized 30m resolution data based on target GPS coordinates.
2. **Layer 2: Regional Baseline (CSV)**: If the high-resolution file is missing, the app gracefully falls back to validated county-level averages from the iSDAsoil dataset.
3. **Layer 3: Lab Override**: Users can override either layer by inputting actual laboratory soil test results.

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

## 📈 Scientific Attribution
Soil chemistry data is sampled from the **iSDAsoil Africa Soil Map (2021)**. Nutrient threshold calculations are based on standard Kenyan Agronomic Baselines.

---
*Developed for the future of Kenyan Agriculture.*
