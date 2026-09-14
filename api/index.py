"""
Vercel Serverless Function entrypoint adapter.
Exposes FastAPI app as the ASGI handler.
"""

from app.main import app
