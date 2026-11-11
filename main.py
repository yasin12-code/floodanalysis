"""Vercel entrypoint: expose the FastAPI app from backend/app/main.py.

Vercel auto-detects a FastAPI instance named `app` in a root-level main.py.
The app's routers import as `app.*`, so backend/ must be on sys.path first.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.main import app  # noqa: E402  (import after the sys.path setup)
