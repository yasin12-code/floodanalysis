"""Configuration from environment variables (all documented in .env.example)."""

import os
from dataclasses import dataclass


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw is not None else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw is not None else default


def _env_bbox(name: str, default: str) -> tuple[float, float, float, float]:
    raw = os.environ.get(name, default)
    parts = [float(p) for p in raw.split(",")]
    if len(parts) != 4 or parts[0] >= parts[2] or parts[1] >= parts[3]:
        raise ValueError(f"{name} must be minLng,minLat,maxLng,maxLat (got {raw!r})")
    return tuple(parts)


@dataclass(frozen=True)
class Settings:
    database_url: str
    map_center_lat: float
    map_center_lng: float
    map_zoom: int
    study_area_bbox: tuple[float, float, float, float]
    default_radius_m: int
    caution_radius_m: int
    cors_origins: list[str]

    @property
    def bbox_dict(self) -> dict:
        min_lng, min_lat, max_lng, max_lat = self.study_area_bbox
        return {"min_lng": min_lng, "min_lat": min_lat, "max_lng": max_lng, "max_lat": max_lat}


def get_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/webgis"),
        map_center_lat=_env_float("MAP_CENTER_LAT", 34.006),
        map_center_lng=_env_float("MAP_CENTER_LNG", 71.974),
        map_zoom=_env_int("MAP_ZOOM", 13),
        study_area_bbox=_env_bbox("STUDY_AREA_BBOX", "71.85,33.90,72.10,34.12"),
        default_radius_m=_env_int("DEFAULT_RADIUS_M", 3000),
        caution_radius_m=_env_int("CAUTION_RADIUS_M", 500),
        cors_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:8000").split(",")
                      if o.strip()],
    )


settings = get_settings()
