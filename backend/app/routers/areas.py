"""Study-area registry (P1): the dropdown of Pakistani cities the map can switch to.

Every spatial endpoint takes an `area` slug (default 'nowshera'); this router
exposes the list of areas and a lookup helper used for per-area bbox validation.
"""

from fastapi import APIRouter, HTTPException

from app.db import get_pool

router = APIRouter(prefix="/api", tags=["areas"])

AREA_COLUMNS = ("slug", "name", "province", "river_name", "center_lng", "center_lat",
                "zoom", "min_lng", "min_lat", "max_lng", "max_lat", "default_radius_m")

_AREA_SQL = ("SELECT slug, name, province, river_name, center_lng, center_lat, "
             "zoom, min_lng, min_lat, max_lng, max_lat, default_radius_m FROM areas")


def get_area(slug: str) -> dict:
    """Fetch one area's config; unknown slug -> 422."""
    with get_pool().connection() as conn:
        row = conn.execute(_AREA_SQL + " WHERE slug = %s", (slug,)).fetchone()
    if row is None:
        raise HTTPException(status_code=422, detail=f"Unknown area '{slug}'")
    return dict(zip(AREA_COLUMNS, row))


@router.get("/areas")
def list_areas():
    with get_pool().connection() as conn:
        rows = conn.execute(_AREA_SQL + " ORDER BY id").fetchall()
    return {"areas": [dict(zip(AREA_COLUMNS, row)) for row in rows]}
