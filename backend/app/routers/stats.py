"""Summary statistics (Section 8.3, P1)."""

from fastapi import APIRouter, Query

from app.db import get_pool

router = APIRouter(prefix="/api", tags=["stats"])

STATS_SQL = """
    SELECT
        -- ST_Area on geography: area per risk level in square metres -> km2.
        (SELECT COALESCE(jsonb_object_agg(risk_level, area_km2), '{}'::jsonb) FROM (
             SELECT risk_level, ROUND((SUM(ST_Area(geom::geography)) / 1e6)::numeric, 2) AS area_km2
             FROM flood_zones
             WHERE area = %(area)s
             GROUP BY risk_level
         ) a) AS area_km2_by_risk_level,
        -- Shelters inside flood zones (max_risk_level comes from ST_Intersects in the view).
        (SELECT jsonb_build_object(
             'count', COUNT(*) FILTER (WHERE max_risk_level IS NOT NULL),
             'total_capacity', COALESCE(SUM(capacity) FILTER (WHERE max_risk_level IS NOT NULL), 0)
         ) FROM shelters_with_risk WHERE area = %(area)s) AS shelters_inside,
        (SELECT jsonb_build_object(
             'count', COUNT(*) FILTER (WHERE max_risk_level IS NULL),
             'total_capacity', COALESCE(SUM(capacity) FILTER (WHERE max_risk_level IS NULL), 0)
         ) FROM shelters_with_risk WHERE area = %(area)s) AS shelters_outside,
        (SELECT COALESCE(SUM(capacity - current_occupancy) FILTER (WHERE status = 'open'), 0)
         FROM shelters_with_risk WHERE area = %(area)s) AS open_available_capacity,
        -- ST_Length on geography: kilometres of road that intersect flood zones.
        (SELECT ROUND((COALESCE(SUM(ST_Length(geom::geography))
                                FILTER (WHERE max_risk_level IS NOT NULL), 0) / 1000.0)::numeric, 2)
         FROM roads_with_risk WHERE area = %(area)s) AS roads_at_risk_km
"""


@router.get("/stats")
def get_stats(
    area: str = Query(default="nowshera", min_length=1, max_length=64, description="Study area slug"),
):
    with get_pool().connection() as conn:
        row = conn.execute(STATS_SQL, {"area": area}).fetchone()
    return {
        "area_km2_by_risk_level": row[0],
        "shelters": {
            "inside_flood_zone": row[1],
            "outside_flood_zone": row[2],
        },
        "open_available_capacity": row[3],
        "roads_at_risk_km": row[4],
    }
