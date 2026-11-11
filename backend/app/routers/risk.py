"""Click analysis (/api/risk-check) and community flood sightings (P1).

risk-check follows Section 8.1 step by step: ST_Intersects containment,
ST_Buffer caution band, ST_Distance to the nearest zone (via the <-> GiST
operator), ST_Buffer search area, ST_DWithin shelter search with ST_Distance
ranking, and a recommendation that never points into a flood zone."""

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.db import get_pool
from app.routers.areas import get_area
from app.schemas import FloodReportCreate

router = APIRouter(prefix="/api", tags=["risk"])

RISK_LABELS = {1: "Low", 2: "Medium", 3: "High", 4: "Very high"}

RISK_CHECK_SQL = """
    WITH point AS (
        -- ST_SetSRID + ST_MakePoint: the clicked point, longitude first (SRID 4326).
        SELECT ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326) AS geom
    ),
    zones_containing AS (
        -- ST_Intersects: does any flood zone contain the point?
        SELECT z.id, z.name, z.risk_level, z.return_period_years
        FROM flood_zones z, point p
        WHERE z.area = %(area)s
          AND ST_Intersects(z.geom, p.geom)
    ),
    caution_check AS (
        -- ST_Buffer on geography: 500 m caution circle around the point.
        SELECT EXISTS (
            SELECT 1 FROM flood_zones z, point p
            WHERE z.area = %(area)s
              AND ST_Intersects(z.geom, ST_Buffer(p.geom::geography, %(caution_m)s)::geometry)
        ) AS hit
    ),
    nearest_zone AS (
        -- <-> orders candidates with the GiST index; ST_Distance on geography
        -- returns the true nearest-zone distance in metres.
        SELECT ROUND(ST_Distance(z.geom::geography, p.geom::geography)::numeric, 1) AS distance_m
        FROM flood_zones z, point p
        WHERE z.area = %(area)s
        ORDER BY z.geom <-> p.geom
        LIMIT 1
    ),
    search_area AS (
        -- ST_Buffer on geography: the search circle, returned as GeoJSON so the
        -- frontend can draw it.
        SELECT ST_AsGeoJSON(ST_Buffer(p.geom::geography, %(radius_m)s)::geometry)::jsonb AS buffer_geojson
        FROM point p
    ),
    flooded_roads AS (
        -- ST_Intersects: flooded or blocked roads inside the search circle.
        SELECT COUNT(*) AS n
        FROM roads r, point p
        WHERE r.area = %(area)s
          AND r.status IN ('flooded', 'blocked')
          AND ST_Intersects(r.geom, ST_Buffer(p.geom::geography, %(radius_m)s)::geometry)
    ),
    shelters_nearby AS (
        -- ST_DWithin on geography (index-backed) restricts the search, then
        -- ST_Distance ranks verified shelters by metres; LIMIT caps the list.
        SELECT s.id, s.name, s.shelter_type, s.capacity, s.current_occupancy,
               (s.capacity - s.current_occupancy) AS available,
               s.status, s.contact_phone, s.address,
               ROUND(ST_Distance(s.geom::geography, p.geom::geography)::numeric, 1) AS distance_m,
               (s.max_risk_level IS NOT NULL) AS in_flood_zone,
               ST_X(s.geom) AS lng, ST_Y(s.geom) AS lat
        FROM shelters_with_risk s, point p
        WHERE s.area = %(area)s
          AND s.is_verified
          AND ST_DWithin(s.geom::geography, p.geom::geography, %(radius_m)s)
        ORDER BY distance_m
        LIMIT %(limit)s
    ),
    recommendation AS (
        -- Nearest verified OPEN shelter with free capacity that is itself outside
        -- every flood zone; NULL when none qualifies within the radius.
        SELECT s.id
        FROM shelters_with_risk s, point p
        WHERE s.area = %(area)s
          AND s.is_verified
          AND s.status = 'open'
          AND s.capacity > s.current_occupancy
          AND s.max_risk_level IS NULL
          AND ST_DWithin(s.geom::geography, p.geom::geography, %(radius_m)s)
        ORDER BY ST_Distance(s.geom::geography, p.geom::geography)
        LIMIT 1
    )
    SELECT
        (SELECT COALESCE(jsonb_agg(jsonb_build_object(
             'id', id, 'name', name, 'risk_level', risk_level,
             'return_period_years', return_period_years)), '[]'::jsonb)
         FROM zones_containing) AS zones,
        (SELECT hit FROM caution_check) AS caution_hit,
        (SELECT distance_m FROM nearest_zone) AS nearest_zone_distance_m,
        (SELECT buffer_geojson FROM search_area) AS search_buffer,
        (SELECT n FROM flooded_roads) AS flooded_roads_in_radius,
        (SELECT COALESCE(jsonb_agg(to_jsonb(s)), '[]'::jsonb) FROM shelters_nearby s) AS shelters,
        (SELECT id FROM recommendation) AS recommended_shelter_id
"""


@router.get("/risk-check")
def risk_check(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(default=settings.default_radius_m, ge=100, le=20000),
    limit: int = Query(default=5, ge=1, le=20),
    area: str = Query(default="nowshera", min_length=1, max_length=64, description="Study area slug"),
):
    area_cfg = get_area(area)
    if not (area_cfg["min_lng"] <= lng <= area_cfg["max_lng"]
            and area_cfg["min_lat"] <= lat <= area_cfg["max_lat"]):
        raise HTTPException(status_code=422, detail="Point is outside the study area")

    params = {"lat": lat, "lng": lng, "radius_m": radius_m, "limit": limit,
              "caution_m": settings.caution_radius_m, "area": area}
    with get_pool().connection() as conn:
        row = conn.execute(RISK_CHECK_SQL, params).fetchone()

    # Plain cursor: row is a tuple in the SELECT order of RISK_CHECK_SQL.
    (zones, caution_hit, nearest_zone_distance_m, search_buffer,
     flooded_roads_in_radius, shelters, recommended_shelter_id) = row

    if zones:
        status = "in_zone"
        risk_level = max(z["risk_level"] for z in zones)
        risk_label = RISK_LABELS[risk_level]
    elif caution_hit:
        status = "near_zone"
        risk_level = None
        risk_label = "Near a flood zone"
    else:
        status = "outside"
        risk_level = None
        risk_label = "Outside flood zones"

    return {
        "location": {"lat": lat, "lng": lng},
        "status": status,
        "risk_level": risk_level,
        "risk_label": risk_label,
        "zones": zones,
        "nearest_zone_distance_m": nearest_zone_distance_m,
        "radius_m": radius_m,
        "search_buffer": search_buffer,
        "shelters": shelters or [],
        "recommended_shelter_id": recommended_shelter_id,
        "flooded_roads_in_radius": flooded_roads_in_radius,
    }


@router.post("/flood-reports", status_code=201)
def create_flood_report(payload: FloodReportCreate):
    area_cfg = get_area(payload.area)
    if not (area_cfg["min_lng"] <= payload.lng <= area_cfg["max_lng"]
            and area_cfg["min_lat"] <= payload.lat <= area_cfg["max_lat"]):
        raise HTTPException(status_code=422, detail="Report location is outside the study area")
    # ST_MakePoint + ST_SetSRID: the sighting point, longitude first (SRID 4326).
    sql = """
        INSERT INTO flood_reports (report_type, severity, description, area, geom)
        VALUES (%(report_type)s, %(severity)s, %(description)s, %(area)s,
                ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326))
        RETURNING id, report_type, severity, description, created_at,
                  ST_X(geom) AS lng, ST_Y(geom) AS lat
    """
    with get_pool().connection() as conn:
        row = conn.execute(sql, payload.model_dump()).fetchone()
    # Plain cursor: RETURNING order is id, report_type, severity, description,
    # created_at, lng, lat.
    report_id, report_type, severity, description, created_at, lng, lat = row
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {
            "id": report_id,
            "report_type": report_type,
            "severity": severity,
            "description": description,
            "created_at": created_at.isoformat(),
        },
    }
