"""
Production Runtime Environment Diagnostic Script for Daily Intelligence.
Safe, non-secret diagnostic report for Railway container execution.
Never outputs passwords, secrets, or raw credentials.
"""

import os
import sys
import importlib.metadata
import urllib.parse
from app.config import get_settings, sanitize_database_url


def check_package_version(package_name: str) -> str:
    try:
        return importlib.metadata.version(package_name)
    except Exception as exc:
        return f"NOT INSTALLED ({exc.__class__.__name__})"


def main() -> None:
    settings = get_settings()
    raw_db_url = os.getenv("DATABASE_URL") or ""
    db_present = bool(raw_db_url.strip())
    sanitized_db = sanitize_database_url(settings.effective_database_url)

    print("=================================================================")
    print("      DAILY INTELLIGENCE — PYTHON RUNTIME DIAGNOSTIC      ")
    print("=================================================================")
    print(f"  Python Version      : {sys.version.split()[0]}")
    print(f"  Python Executable   : {sys.executable}")
    print(f"  App Environment     : {settings.app_env}")
    print(f"  Is Production       : {settings.is_production}")
    print("-----------------------------------------------------------------")
    print("--- PACKAGE VERSIONS ---")
    print(f"  FastAPI Version     : {check_package_version('fastapi')}")
    print(f"  Uvicorn Version     : {check_package_version('uvicorn')}")
    print(f"  SQLAlchemy Version  : {check_package_version('sqlalchemy')}")
    print(f"  Psycopg Version     : {check_package_version('psycopg')}")
    print(f"  Alembic Version     : {check_package_version('alembic')}")
    print("-----------------------------------------------------------------")
    print("--- DATABASE CONFIGURATION ---")
    print(f"  DATABASE_URL Present: {db_present}")
    print(f"  Sanitized DB URL    : {sanitized_db}")
    print("=================================================================")

    # Verify critical packages
    critical_packages = ["fastapi", "uvicorn", "sqlalchemy", "psycopg", "alembic"]
    missing = [pkg for pkg in critical_packages if "NOT INSTALLED" in check_package_version(pkg)]

    if missing:
        print(f"ERROR: Critical packages missing: {missing}")
        sys.exit(1)

    print("RESULT: RUNTIME DIAGNOSTIC PASSED — ENVIRONMENT DETERMINISTIC & VALID")


if __name__ == "__main__":
    main()
