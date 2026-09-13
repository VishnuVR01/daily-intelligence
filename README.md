# Daily Intelligence Newspaper

A local-first personal intelligence platform that collects trusted news/research sources,
stores a permanent archive, builds daily editions, and later adds AI-assisted classification,
summarisation, search, RAG, and specialist research agents.

## Local project location

Recommended Windows workspace:

```text
D:\Daily-Intelligence
```

## MVP order

1. Project + PostgreSQL setup
2. Source registry
3. RSS ingestion
4. Normalisation + deduplication
5. Persistent article archive
6. Daily edition generation
7. Local web interface
8. Ollama classification/summarisation
9. Scheduling
10. RAG + research agents

## Quick start on Windows

Open PowerShell in `D:\Daily-Intelligence` and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python scripts\check_setup.py
```

## Seed sources and run RSS ingestion

```powershell
python -m scripts.seed_sources
python -m scripts.run_ingestion
```

## Run the web app

```powershell
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/archive
http://127.0.0.1:8000/api/articles
http://127.0.0.1:8000/docs
```

## Database Migrations

Whenever database models change:

```powershell
python -m alembic revision --autogenerate -m "description"
python -m alembic upgrade head
```

## Golden rule

Collect first. Preserve provenance. Add AI second.

