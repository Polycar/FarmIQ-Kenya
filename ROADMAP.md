# FarmIQ Kenya: Product Roadmap

This document outlines the future development trajectory for FarmIQ, capturing advanced features, enterprise-level upgrades, and commercialization strategies.

## Phase 1: MVP & Core Platform (Current)
- [x] Basic Soil Mapping (Regional CSV + 30m pH GeoTIFF)
- [x] Dynamic Crop Calendar & Shopping List
- [x] Season-over-Season Yield Tracking Dashboard
- [x] Live iSDAsoil API Integration for 30m NPK data
- [x] Agro-dealer database mapping for all 47 counties

## Phase 2: Commercial Scalability (Upcoming)
- [ ] **Database Migration**: Move `farmiq.db` (SQLite) to a scalable cloud provider like PostgreSQL (Supabase/Neon) or Firebase.
- [ ] **User Accounts**: Implement phone-number-based OTP login via Twilio or Africa's Talking.
- [ ] **B2B API Tier**: Allow agri-businesses to ping the FarmIQ recommendation engine via REST API.

## Phase 3: The Enterprise Risk Engine (Advanced Thesis Integration)
**Option D: Custom Kriging & Sequential Gaussian Simulation (SGS) Layer**

Instead of relying purely on deterministic points from APIs, FarmIQ will become an agricultural risk engine by integrating the Sequential Gaussian Simulation techniques developed in the founder's academic thesis.

### How it works:
1. **Pre-Computation**: Run SGS across legacy Kenyan soil profile data (e.g., AfSIS or iSDAsoil point datasets) to produce uncertainty-aware soil maps.
2. **E-Type & Variance Generation**: Generate Cloud-Optimized GeoTIFFs that map both the *predicted mean* and the *spatial uncertainty* (conditional variance).
3. **Cloud Hosting**: Host these rasters on an S3 bucket and query them dynamically via `rasterio`.

### The Business Value:
* **For Farmers**: "We predict your pH is 5.7, but there is a 15% probability it is highly acidic (<5.0) based on spatial uncertainty." 
* **For Lenders & Insurers (B2B)**: Provides a localized risk-scoring metric. If a bank issues a loan for DAP, they can factor in the exact spatial uncertainty of the soil health in that specific Kakamega parcel.

*Note: This feature is highly computationally expensive and should be executed outside of the live Streamlit environment as a pre-processing pipeline.*
