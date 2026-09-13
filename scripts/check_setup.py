import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text

print("Python:", sys.version.split()[0])


try:
    from app.config import get_settings
    from app.db import Base, engine
    from app.schema_validation import validate_schema
    import app.models  # noqa: F401

    settings = get_settings()
    print("App:", settings.app_name)
    print("Timezone:", settings.app_timezone)

    with engine.connect() as connection:
        value = connection.execute(text("SELECT 1")).scalar_one()
        print("PostgreSQL connection:", "OK" if value == 1 else "Unexpected response")

    validate_schema(engine, Base.metadata)
    print("Schema Validation:", "OK (All model tables and columns present)")

except Exception as exc:

    print("\nSETUP CHECK FAILED")
    print(type(exc).__name__ + ":", exc)
    print("\nCheck that:")
    print("1. .venv is active")
    print("2. requirements.txt is installed")
    print("3. .env exists")
    print("4. PostgreSQL is running")
    print("5. DATABASE_URL contains the correct credentials")
    raise
