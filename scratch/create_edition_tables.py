"""
Helper script to apply schema changes for Stage 3C Edition Tables in PostgreSQL.
"""
from app.db import engine, Base
from app.models import DailyEdition, EditionEvent

def init_tables():
    print("Creating/updating Stage 3C Daily Edition tables...")
    Base.metadata.create_all(bind=engine)
    print("Stage 3C Daily Edition tables created/updated successfully.")

if __name__ == "__main__":
    init_tables()
