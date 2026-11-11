"""Shelter suggestion form endpoint (Section 8.2)."""

from fastapi import APIRouter, HTTPException

from app.db import get_pool
from app.routers.areas import get_area
from app.schemas import ShelterCreate

router = APIRouter(prefix="/api", tags=["shelters"])


@router.post("/shelters", status_code=201)
def create_shelter(payload: ShelterCreate):
    area_cfg = get_area(payload.area)
    if not (area_cfg["min_lng"] <= payload.lng <= area_cfg["max_lng"]
            and area_cfg["min_lat"] <= payload.lat <= area_cfg["max_lat"]):
        raise HTTPException(status_code=422, detail="Shelter location is outside the study area")
    # ST_MakePoint + ST_SetSRID: store the suggestion unverified (lng first, 4326).
    sql = """
        INSERT INTO shelters (name, area, shelter_type, capacity, contact_phone, address, is_verified, geom)
        VALUES (%(name)s, %(area)s, %(shelter_type)s, %(capacity)s, %(contact_phone)s, %(address)s, FALSE,
                ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326))
        RETURNING id, name, shelter_type, capacity, current_occupancy, status, contact_phone,
                  address, is_verified, ST_X(geom) AS lng, ST_Y(geom) AS lat
    """
    with get_pool().connection() as conn:
        row = conn.execute(sql, payload.model_dump()).fetchone()
    # Plain cursor: RETURNING order is id, name, shelter_type, capacity,
    # current_occupancy, status, contact_phone, address, is_verified, lng, lat.
    (shelter_id, name, shelter_type, capacity, current_occupancy, status,
     contact_phone, address, is_verified, lng, lat) = row
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {
            "id": shelter_id,
            "name": name,
            "shelter_type": shelter_type,
            "capacity": capacity,
            "current_occupancy": current_occupancy,
            "status": status,
            "contact_phone": contact_phone,
            "address": address,
            "is_verified": is_verified,
        },
    }
