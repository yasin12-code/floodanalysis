"""Layer endpoints. Each GeoJSON FeatureCollection is assembled inside PostGIS
with ST_AsGeoJSON + jsonb_agg; every response is capped at 5000 features."""

from fastapi import APIRouter, HTTPException, Query

from app.db import get_pool
from app.schemas import ROAD_STATUSES, SHELTER_STATUSES, SHELTER_TYPES

router = APIRouter(prefix="/api/layers", tags=["layers"])

MAX_FEATURES = 5000

_LEVELS = (1, 2, 3, 4)


def _parse_bbox(bbox: str | None) -> dict | None:
    """Validate 'minLng,minLat,maxLng,maxLat' and return the four floats."""
    if bbox is None:
        return None
    try:
        min_lng, min_lat, max_lng, max_lat = (float(p) for p in bbox.split(","))
    except ValueError:
        raise HTTPException(status_code=422, detail="bbox must be minLng,minLat,maxLng,maxLat")
    if not (min_lng < max_lng and min_lat < max_lat):
        raise HTTPException(status_code=422, detail="bbox must have minLng < maxLng and minLat < maxLat")
    return {"min_lng": min_lng, "min_lat": min_lat, "max_lng": max_lng, "max_lat": max_lat}


@router.get("/flood-zones")
def list_flood_zones(
    risk_min: list[int] | None = Query(default=None, description="Risk levels to include, repeatable (?risk_min=2&risk_min=3)"),
    bbox: str | None = Query(default=None, description="minLng,minLat,maxLng,maxLat"),
    buffer_m: int | None = Query(default=None, ge=0, le=10000, description="Expand zones by this many metres (caution band)"),
    area: str = Query(default="nowshera", min_length=1, max_length=64, description="Study area slug"),
):
    if risk_min and any(level not in _LEVELS for level in risk_min):
        raise HTTPException(status_code=422, detail="risk_min values must be between 1 and 4")
    b = _parse_bbox(bbox)
    conditions = ["area = %(area)s"]
    params: dict = {"risk_min": risk_min, "buffer_m": buffer_m, "area": area,
                    "min_lng": None, "min_lat": None, "max_lng": None, "max_lat": None}
    if risk_min:
        conditions.append("risk_level = ANY(%(risk_min)s::int[])")
    if b:
        params.update(b)
        # && is the GiST-accelerated bounding-box operator; ST_MakeEnvelope builds
        # the bbox geometry in SRID 4326.
        conditions.append("geom && ST_MakeEnvelope(%(min_lng)s::float8, %(min_lat)s::float8, %(max_lng)s::float8, %(max_lat)s::float8, 4326)")
    sql = f"""
        -- ST_AsGeoJSON serialises each geometry; jsonb_agg assembles the
        -- FeatureCollection in the database. ST_Buffer (on geography, metres)
        -- expands the zones into a caution band when buffer_m is set.
        SELECT jsonb_build_object(
          'type', 'FeatureCollection',
          'features', COALESCE(jsonb_agg(jsonb_build_object(
            'type', 'Feature',
            'geometry', ST_AsGeoJSON(geom)::jsonb,
            'properties', jsonb_build_object(
              'id', id, 'name', name, 'risk_level', risk_level,
              'return_period_years', return_period_years, 'source', source
            )
          )), '[]'::jsonb)
        ) AS fc
        FROM (
          SELECT id, name, risk_level, return_period_years, source,
                 CASE WHEN %(buffer_m)s::int IS NOT NULL
                      THEN ST_Buffer(geom::geography, %(buffer_m)s::int)::geometry
                      ELSE geom END AS geom
          FROM flood_zones
          WHERE {' AND '.join(conditions)}
          LIMIT {MAX_FEATURES}
        ) t
    """
    with get_pool().connection() as conn:
        row = conn.execute(sql, params).fetchone()
    return row[0]


@router.get("/shelters")
def list_shelters(
    type: list[str] | None = Query(default=None, alias="type", description="Shelter types, repeatable"),
    status: list[str] | None = Query(default=None, description="open/full/closed, repeatable"),
    min_capacity: int | None = Query(default=None, ge=0),
    include_unverified: bool = Query(default=False),
    bbox: str | None = Query(default=None, description="minLng,minLat,maxLng,maxLat"),
    area: str = Query(default="nowshera", min_length=1, max_length=64, description="Study area slug"),
):
    if type and any(t not in SHELTER_TYPES for t in type):
        raise HTTPException(status_code=422, detail=f"type must be one of {', '.join(SHELTER_TYPES)}")
    if status and any(s not in SHELTER_STATUSES for s in status):
        raise HTTPException(status_code=422, detail=f"status must be one of {', '.join(SHELTER_STATUSES)}")
    b = _parse_bbox(bbox)
    params: dict = {"type": type, "status": status, "min_capacity": min_capacity,
                    "include_unverified": include_unverified, "area": area,
                    "min_lng": None, "min_lat": None, "max_lng": None, "max_lat": None}
    if b:
        params.update(b)
    sql = f"""
        -- Reads shelters_with_risk so max_risk_level (ST_Intersects against the
        -- flood zones, computed in the view) travels with every feature.
        SELECT jsonb_build_object(
          'type', 'FeatureCollection',
          'features', COALESCE(jsonb_agg(jsonb_build_object(
            'type', 'Feature',
            'geometry', ST_AsGeoJSON(geom)::jsonb,
            'properties', jsonb_build_object(
              'id', id, 'name', name, 'shelter_type', shelter_type,
              'capacity', capacity, 'current_occupancy', current_occupancy,
              'available', capacity - current_occupancy,
              'status', status, 'contact_phone', contact_phone, 'address', address,
              'is_verified', is_verified, 'max_risk_level', max_risk_level
            )
          )), '[]'::jsonb)
        ) AS fc
        FROM (
          SELECT *
          FROM shelters_with_risk
          WHERE TRUE
            AND area = %(area)s
            AND (%(include_unverified)s OR is_verified)
            AND (%(type)s::text[] IS NULL OR shelter_type = ANY(%(type)s::text[]))
            AND (%(status)s::text[] IS NULL OR status = ANY(%(status)s::text[]))
            AND (%(min_capacity)s::int IS NULL OR capacity >= %(min_capacity)s::int)
            AND (%(min_lng)s::float8 IS NULL
                 OR geom && ST_MakeEnvelope(%(min_lng)s::float8, %(min_lat)s::float8, %(max_lng)s::float8, %(max_lat)s::float8, 4326))
          LIMIT {MAX_FEATURES}
        ) t
    """
    with get_pool().connection() as conn:
        row = conn.execute(sql, params).fetchone()
    return row[0]


@router.get("/roads")
def list_roads(
    status: list[str] | None = Query(default=None, description="open/flooded/blocked, repeatable"),
    road_type: list[str] | None = Query(default=None, description="Road types, repeatable"),
    at_risk: bool = Query(default=False, description="Only roads that intersect a flood zone"),
    bbox: str | None = Query(default=None, description="minLng,minLat,maxLng,maxLat"),
    area: str = Query(default="nowshera", min_length=1, max_length=64, description="Study area slug"),
):
    road_types = ("motorway", "trunk", "primary", "secondary", "tertiary", "residential", "track")
    if status and any(s not in ROAD_STATUSES for s in status):
        raise HTTPException(status_code=422, detail=f"status must be one of {', '.join(ROAD_STATUSES)}")
    if road_type and any(t not in road_types for t in road_type):
        raise HTTPException(status_code=422, detail=f"road_type must be one of {', '.join(road_types)}")
    b = _parse_bbox(bbox)
    params: dict = {"status": status, "road_type": road_type, "at_risk": at_risk,
                    "area": area,
                    "min_lng": None, "min_lat": None, "max_lng": None, "max_lat": None}
    if b:
        params.update(b)
    sql = f"""
        -- Reads roads_with_risk; max_risk_level IS NOT NULL means the road
        -- intersects a flood zone (ST_Intersects in the view definition).
        SELECT jsonb_build_object(
          'type', 'FeatureCollection',
          'features', COALESCE(jsonb_agg(jsonb_build_object(
            'type', 'Feature',
            'geometry', ST_AsGeoJSON(geom)::jsonb,
            'properties', jsonb_build_object(
              'id', id, 'name', name, 'road_type', road_type,
              'status', status, 'max_risk_level', max_risk_level
            )
          )), '[]'::jsonb)
        ) AS fc
        FROM (
          SELECT *
          FROM roads_with_risk
          WHERE TRUE
            AND area = %(area)s
            AND (%(status)s::text[] IS NULL OR status = ANY(%(status)s::text[]))
            AND (%(road_type)s::text[] IS NULL OR road_type = ANY(%(road_type)s::text[]))
            AND (%(at_risk)s = FALSE OR max_risk_level IS NOT NULL)
            AND (%(min_lng)s::float8 IS NULL
                 OR geom && ST_MakeEnvelope(%(min_lng)s::float8, %(min_lat)s::float8, %(max_lng)s::float8, %(max_lat)s::float8, 4326))
          LIMIT {MAX_FEATURES}
        ) t
    """
    with get_pool().connection() as conn:
        row = conn.execute(sql, params).fetchone()
    return row[0]


@router.get("/flood-reports")
def list_flood_reports(
    area: str = Query(default="nowshera", min_length=1, max_length=64, description="Study area slug"),
):
    # Layer for community flood sightings (FR-16); newest reports first.
    sql = f"""
        SELECT jsonb_build_object(
          'type', 'FeatureCollection',
          'features', COALESCE(jsonb_agg(jsonb_build_object(
            'type', 'Feature',
            'geometry', ST_AsGeoJSON(geom)::jsonb,
            'properties', jsonb_build_object(
              'id', id, 'report_type', report_type, 'severity', severity,
              'description', description, 'created_at', created_at
            )
          )), '[]'::jsonb)
        ) AS fc
        FROM (
          SELECT * FROM flood_reports
          WHERE area = %(area)s
          ORDER BY created_at DESC
          LIMIT {MAX_FEATURES}
        ) t
    """
    with get_pool().connection() as conn:
        row = conn.execute(sql, {"area": area}).fetchone()
    return row[0]
