"""
Helper script to apply schema changes for Stage 3D Synthesis Tables in PostgreSQL.
"""
from app.db import engine, Base
from app.models import EventEditorialProse, EditionBrief

def init_tables():
    print("Creating Stage 3D Synthesis tables in PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    print("Stage 3D Synthesis tables created successfully.")

if __name__ == "__main__":
    init_tables()
