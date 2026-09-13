# Daily Intelligence — SQL Guide

This folder separates **database setup**, **reference schema**, **diagnostic queries**, and **legacy/manual SQL**.

## Important rule

The live application database schema is managed with **Alembic migrations**.

Do not use the files in `reference/` or `archive/` to modify the live schema unless you are deliberately rebuilding a historical MVP database.

## Recommended order

### First-time PostgreSQL setup
Run as a PostgreSQL administrator:

1. `00_user_setup.sql`

Then configure the application's `.env` with the correct database URL.

### Schema changes
Use Alembic:

```powershell
python -m alembic upgrade head
```

Create new migrations for future model/schema changes. Do not add manual `ALTER TABLE` statements to diagnostic files.

### Database checks
Use the scripts in `diagnostics/` from pgAdmin or `psql` as needed.

- `10_database_health.sql` — database/schema identity and counts
- `20_source_audit.sql` — registered sources, activity and coverage
- `30_article_quality.sql` — duplicates, missing fields, future dates
- `40_content_checks.sql` — focused content/source investigations

### Historical reference
- `reference/01_initial_mvp_schema.sql` preserves the original MVP schema for documentation only.
- `archive/legacy_manual_alters.sql` preserves old manual schema changes that should now be handled through Alembic.
