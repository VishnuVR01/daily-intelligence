import sys
import os
sys.path.insert(0, os.path.abspath("."))
from app.db import Base, engine

def create_tables():
    print("Creating event_clusters and event_cluster_articles tables if not existing...")
    Base.metadata.create_all(engine)
    print("Tables created successfully!")

if __name__ == "__main__":
    create_tables()
