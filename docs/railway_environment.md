# Railway Environment Variables Configuration Guide

This document lists all environment variables required for deploying **Daily Intelligence** to Railway.

> [!IMPORTANT]
> Never commit actual passwords, API keys, or production secrets to Git. Configure these variables directly in the **Railway Dashboard -> Service Settings -> Environment Variables**.

---

## 1. Required Variables

| Variable Name | Example Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://postgres:password@monorail.proxy.rlwy.net:5432/railway` | PostgreSQL database connection URL automatically supplied by Railway PostgreSQL plugin. |
| `APP_ENV` | `production` | Enables production mode rules, disables debug routes, and enforces secure database URL validation. |
| `APP_TIMEZONE` | `Europe/London` | Sets the canonical editorial briefing timezone for Europe/London date boundaries. |
| `PORT` | `8080` | Provided automatically by Railway to bind the Uvicorn web server port. |

---

## 2. Optional / Feature Variables

| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `OLLAMA_ENABLED` | `false` | Set to `false` during Stage 1 deployment (Ollama processing disabled in initial cloud ingestion). |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Base URL for Ollama inference service if cloud LLM proxy is attached later. |
| `MARKET_DATA_API_KEY` | *(empty)* | Optional API key for live financial market data providers (Twelve Data / FRED). |
| `ENABLE_ERROR_TEST_ROUTES` | `false` | Must remain `false` in production. |

---

## 3. Production Deployment Commands

### Database Schema Initialization (Empty Railway PostgreSQL)
```bash
python -m alembic upgrade head
```

### Source Registry Seed (Idempotent 50 Active Sources)
```bash
python -m scripts.seed_sources
```

### Scheduled Ingestion Cron (Every 30 Minutes)
```bash
python -m scripts.run_ingestion_once
```

### Production Web Server Start Command
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
