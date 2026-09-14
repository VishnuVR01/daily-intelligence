"""
Database Diagnostic Smoke Test Script
Reports environment-aware database status (LOCAL vs CLOUD).
Never prints passwords, credentials, or full DATABASE_URL strings.
Usage:
    python -m scripts.check_database
"""

import sys
from app.db import check_db_health


def main():
    health = check_db_health()

    print("=" * 45)
    print("      DATABASE SERVICE DIAGNOSTICS      ")
    print("=" * 45)
    print(f"Database configured : {'yes' if health['configured'] else 'no'}")
    print("Database type       : PostgreSQL")
    print(f"Host type           : {health['mode']}")
    print(f"Reachable           : {'yes' if health['reachable'] else 'no'}")
    print(f"Schema valid        : {'yes' if health['schema_valid'] else 'no'}")

    rev = health.get("migration_revision") or "N/A"
    print(f"Migration revision  : {rev}")
    print("=" * 45)

    if not health["reachable"] or not health["schema_valid"]:
        if health.get("error"):
            print(f"Diagnostic note: {health['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
