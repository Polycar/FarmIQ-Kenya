# 🌱 FarmIQ Kenya: National Precision Agriculture Platform

FarmIQ is a scientifically rigorous, data-driven soil intelligence platform designed to move Kenya from regional county averages to meter-level agricultural precision.

![FarmIQ Screenshot](https://img.icons8.com/color/96/agriculture.png)

## 🚀 Vision
To eliminate regional bias in agricultural advice by providing hyper-localized soil insights and fertilizer recommendations for all 47 Kenyan counties based on 30m-resolution satellite data and "Ground Truth" expert lab overrides.

## ✨ Key Features
- **Precision-First Mapping**: Sample 30m-resolution iSDAsoil datasets using GPS coordinates.
- **National Geographic Neutrality**: A completely unbiased UI that supports any location in Kenya without hardcoded regional defaults.
- **Expert Lab Mode**: Allow extension officers and farmers to override satellite data with physical soil test results for meter-level accuracy.
- **Scientific Soil Health Score**: Replaced unrealistic binary scores with a SIGMOID-weighted Soil Quality Index (SQI).
- **Dynamic Dealer Locator**: Automatically find verified agro-dealers near your shamba with direct navigation links.
- **Multi-lingual Support**: Full support for English and Kiswahili.

## 🛠️ Tech Stack
- **Dashboard**: Streamlit
- **Spatial Engine**: Rasterio & NumPy
- **Database**: SQLite & SQLAlchemy
- **Reports**: FPDF2
- **Styling**: Vanilla CSS with Glassmorphism aesthetics

## 📦 Installation

1. **Clone the Repo**
   ```bash
   git clone https://github.com/YOUR_USERNAME/farm-iq-kenya.git
   cd farm-iq-kenya
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Data Setup (Required)**
   > [!IMPORTANT]
   > The high-resolution raster file `kenya_ph.tif` (308MB) is excluded from this repository to ensure performance. 
   > Please download it from [Source Link Placeholder] and place it in the `data/rasters/` directory.

4. **Run Locally**
   ```bash
   streamlit run app.py
   ```

## 📈 Scientific Attribution
Soil chemistry data is sampled from the **iSDAsoil Africa Soil Map (2021)**. Nutrient threshold calculations are based on standard Kenyan Agronomic Baselines.

---
*Developed for the future of Kenyan Agriculture.*
