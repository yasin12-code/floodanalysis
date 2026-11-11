"""FastAPI application: health/config, routers, CORS, request logging and the
static Leaflet frontend (served by StaticFiles)."""

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import close_pool, get_pool, init_pool
from app.routers import areas, layers, risk, shelters, stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("webgis")

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_pool(settings.database_url)
    yield
    close_pool()


app = FastAPI(title="Flood Risk and Shelter WebGIS", version="1.0.0", lifespan=lifespan)

# NFR-3: CORS is limited to the configured origin(s), never "*" unless configured.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # NFR-6: log every request with its duration.
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %d (%.1f ms)", request.method, request.url.path,
                response.status_code, duration_ms)
    return response


@app.exception_handler(psycopg.Error)
async def database_error_handler(request: Request, exc: psycopg.Error):
    # NFR-6: log the full SQL error server-side, never leak details to the client.
    logger.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
def health():
    # PostGIS_Version() proves the extension is installed and the DB is reachable.
    with get_pool().connection() as conn:
        row = conn.execute("SELECT PostGIS_Version() AS version").fetchone()
    return {"status": "ok", "postgis_version": row[0]}


@app.get("/api/config")
def config():
    # The frontend reads all map settings from here; nothing is hard-coded in JS.
    return {
        "map_center_lat": settings.map_center_lat,
        "map_center_lng": settings.map_center_lng,
        "map_zoom": settings.map_zoom,
        "study_area_bbox": settings.bbox_dict,
        "default_radius_m": settings.default_radius_m,
        "caution_radius_m": settings.caution_radius_m,
    }


app.include_router(areas.router)
app.include_router(layers.router)
app.include_router(risk.router)
app.include_router(shelters.router)
app.include_router(stats.router)


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def api_not_found(path: str):
    raise HTTPException(status_code=404, detail="Not found")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
