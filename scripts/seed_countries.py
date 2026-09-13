import logging
from typing import Any
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.models import Base, Country

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

INITIAL_COUNTRIES = [
    # BRICS Members
    {"code": "BR", "name": "Brazil", "region": "Americas", "is_brics": True, "is_g7": False, "is_g20": True, "lat": -14.235, "lng": -51.925},
    {"code": "RU", "name": "Russia", "region": "Europe", "is_brics": True, "is_g7": False, "is_g20": True, "lat": 61.524, "lng": 105.318},
    {"code": "IN", "name": "India", "region": "Asia", "is_brics": True, "is_g7": False, "is_g20": True, "lat": 20.593, "lng": 78.962},
    {"code": "CN", "name": "China", "region": "Asia", "is_brics": True, "is_g7": False, "is_g20": True, "lat": 35.861, "lng": 104.195},
    {"code": "ZA", "name": "South Africa", "region": "Africa", "is_brics": True, "is_g7": False, "is_g20": True, "lat": -30.559, "lng": 22.937},
    {"code": "EG", "name": "Egypt", "region": "Africa", "is_brics": True, "is_g7": False, "is_g20": False, "lat": 26.820, "lng": 30.802},
    {"code": "ET", "name": "Ethiopia", "region": "Africa", "is_brics": True, "is_g7": False, "is_g20": False, "lat": 9.145, "lng": 40.489},
    {"code": "IR", "name": "Iran", "region": "Middle East", "is_brics": True, "is_g7": False, "is_g20": False, "lat": 32.427, "lng": 53.688},
    {"code": "AE", "name": "United Arab Emirates", "region": "Middle East", "is_brics": True, "is_g7": False, "is_g20": False, "lat": 23.424, "lng": 53.847},
    {"code": "SA", "name": "Saudi Arabia", "region": "Middle East", "is_brics": True, "is_g7": False, "is_g20": True, "lat": 23.885, "lng": 45.079},
    
    # G7 & G20 Members
    {"code": "US", "name": "United States", "region": "Americas", "is_brics": False, "is_g7": True, "is_g20": True, "lat": 37.090, "lng": -95.712},
    {"code": "GB", "name": "United Kingdom", "region": "Europe", "is_brics": False, "is_g7": True, "is_g20": True, "lat": 55.378, "lng": -3.436},
    {"code": "DE", "name": "Germany", "region": "Europe", "is_brics": False, "is_g7": True, "is_g20": True, "lat": 51.165, "lng": 10.451},
    {"code": "FR", "name": "France", "region": "Europe", "is_brics": False, "is_g7": True, "is_g20": True, "lat": 46.227, "lng": 2.213},
    {"code": "IT", "name": "Italy", "region": "Europe", "is_brics": False, "is_g7": True, "is_g20": True, "lat": 41.871, "lng": 12.567},
    {"code": "JP", "name": "Japan", "region": "Asia", "is_brics": False, "is_g7": True, "is_g20": True, "lat": 36.204, "lng": 138.252},
    {"code": "CA", "name": "Canada", "region": "Americas", "is_brics": False, "is_g7": True, "is_g20": True, "lat": 56.130, "lng": -106.346},
    
    # Other Key Economies
    {"code": "AU", "name": "Australia", "region": "Oceania", "is_brics": False, "is_g7": False, "is_g20": True, "lat": -25.274, "lng": 133.775},
    {"code": "KR", "name": "South Korea", "region": "Asia", "is_brics": False, "is_g7": False, "is_g20": True, "lat": 35.907, "lng": 127.766},
    {"code": "MX", "name": "Mexico", "region": "Americas", "is_brics": False, "is_g7": False, "is_g20": True, "lat": 23.634, "lng": -102.552},
    {"code": "ID", "name": "Indonesia", "region": "Asia", "is_brics": False, "is_g7": False, "is_g20": True, "lat": -0.789, "lng": 113.921},
    {"code": "TR", "name": "Turkey", "region": "Europe", "is_brics": False, "is_g7": False, "is_g20": True, "lat": 38.963, "lng": 35.243},
    {"code": "AR", "name": "Argentina", "region": "Americas", "is_brics": False, "is_g7": False, "is_g20": True, "lat": -38.416, "lng": -63.616},
    {"code": "CH", "name": "Switzerland", "region": "Europe", "is_brics": False, "is_g7": False, "is_g20": False, "lat": 46.818, "lng": 8.227},
    {"code": "NL", "name": "Netherlands", "region": "Europe", "is_brics": False, "is_g7": False, "is_g20": False, "lat": 52.132, "lng": 5.291},
    {"code": "SG", "name": "Singapore", "region": "Asia", "is_brics": False, "is_g7": False, "is_g20": False, "lat": 1.352, "lng": 103.819},
    {"code": "QA", "name": "Qatar", "region": "Middle East", "is_brics": False, "is_g7": False, "is_g20": False, "lat": 25.354, "lng": 51.183},
    {"code": "FI", "name": "Finland", "region": "Europe", "is_brics": False, "is_g7": False, "is_g20": False, "lat": 61.924, "lng": 25.748},
]


def seed_countries(session: Session) -> dict[str, int]:
    inserted = 0
    updated = 0
    unchanged = 0

    for data in INITIAL_COUNTRIES:
        code = data["code"]
        existing = session.query(Country).filter(Country.code == code).first()
        if existing:
            changed = False
            for field in ["name", "region", "is_brics", "is_g7", "is_g20", "lat", "lng"]:
                if getattr(existing, field) != data[field]:
                    setattr(existing, field, data[field])
                    changed = True
            if changed:
                updated += 1
            else:
                unchanged += 1
        else:
            new_country = Country(**data)
            session.add(new_country)
            inserted += 1

    session.commit()
    return {"inserted": inserted, "updated": updated, "unchanged": unchanged, "total": len(INITIAL_COUNTRIES)}


def main() -> None:
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        summary = seed_countries(session)
        logger.info(f"Seeded countries: {summary}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
