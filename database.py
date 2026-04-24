from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os

# Database Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_URL = f"sqlite:///{os.path.join(BASE_DIR, 'farmiq.db')}"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class RecommendationRecord(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    county = Column(String)
    crop = Column(String)
    current_fert = Column(String)
    farm_acres = Column(Float)
    is_acidic = Column(Integer)  # 1 for True, 0 for False
    is_n_low = Column(Integer)
    is_p_low = Column(Integer)
    is_k_low = Column(Integer)
    total_budget = Column(Integer)
    recommended_fert = Column(String)
    lang = Column(String)

class YieldRecord(Base):
    __tablename__ = "yields"
    
    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(String, index=True)  # Phone number or Farm Name
    crop = Column(String)
    season = Column(String)
    yield_bags_per_acre = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.now)

# Create tables
Base.metadata.create_all(bind=engine)

def save_recommendation(result, farm_acres, lang):
    """Logs a recommendation result to the database."""
    db = SessionLocal()
    try:
        # Robust primary recommendation extraction
        primary_rec = result.get("comparison", {}).get("recommended", "Custom")

        record = RecommendationRecord(
            county=result.get("county_data", {}).get("County", "Unknown"),
            crop=result.get("crop", "Unknown"),
            current_fert=result.get("current_fert", "None"),
            farm_acres=farm_acres,
            is_acidic=1 if result.get("is_acidic", False) else 0,
            is_n_low=1 if result.get("is_n_low", False) else 0,
            is_p_low=1 if result.get("is_p_low", False) else 0,
            is_k_low=1 if result.get("is_k_low", False) else 0,
            total_budget=result.get("budget", {}).get("total_budget", 0),
            recommended_fert=primary_rec,
            lang=lang
        )
        db.add(record)
        db.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        db.close()

def get_all_records():
    """Retrieves all historical recommendation records."""
    db = SessionLocal()
    try:
        return db.query(RecommendationRecord).order_by(RecommendationRecord.timestamp.desc()).all()
    finally:
        db.close()

def get_stats():
    """Generates aggregate statistics for the dashboard."""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        total = db.query(RecommendationRecord).count()
        if total == 0:
            return None
            
        acidic_count = db.query(RecommendationRecord).filter(RecommendationRecord.is_acidic == 1).count()
        n_low_count = db.query(RecommendationRecord).filter(RecommendationRecord.is_n_low == 1).count()
        p_low_count = db.query(RecommendationRecord).filter(RecommendationRecord.is_p_low == 1).count()
        k_low_count = db.query(RecommendationRecord).filter(RecommendationRecord.is_k_low == 1).count()
        
        county_trends = db.query(RecommendationRecord.county, func.count(RecommendationRecord.id)).group_by(RecommendationRecord.county).all()
        crop_trends = db.query(RecommendationRecord.crop, func.count(RecommendationRecord.id)).group_by(RecommendationRecord.crop).all()
        
        return {
            "total_queries": total,
            "soil_health": {
                "Acidic": acidic_count,
                "Nitrogen Deficit": n_low_count,
                "Phosphorus Deficit": p_low_count,
                "Potassium Deficit": k_low_count
            },
            "county_distribution": dict(county_trends),
            "crop_distribution": dict(crop_trends)
        }
    finally:
        db.close()

def log_yield(farmer_id, crop, season, yield_bags_per_acre):
    """Logs a farmer's harvest yield."""
    db = SessionLocal()
    try:
        record = YieldRecord(
            farmer_id=farmer_id,
            crop=crop,
            season=season,
            yield_bags_per_acre=yield_bags_per_acre
        )
        db.add(record)
        db.commit()
    except Exception:
        pass
    finally:
        db.close()

def get_farmer_yields(farmer_id):
    """Retrieves all historical yield records for a specific farmer."""
    db = SessionLocal()
    try:
        return db.query(YieldRecord).filter(YieldRecord.farmer_id == farmer_id).order_by(YieldRecord.timestamp.asc()).all()
    finally:
        db.close()
