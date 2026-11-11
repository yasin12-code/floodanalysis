"""Vercel entrypoint: expose the FastAPI app from backend/app/main.py.

Vercel routes every request to this function; the app itself serves both the
API and the static frontend. The routers import as `app.*`, so backend/ must
be on sys.path first.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import app  # noqa: E402  (import after the sys.path setup)
