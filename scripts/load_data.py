"""Load data/*.geojson and data/areas.json into PostGIS. Idempotent: truncates, then re-inserts.

Run:      python scripts/load_data.py
Env:      DATABASE_URL (e.g. postgresql://postgres:postgres@localhost:5432/webgis)

The running app never reads the data/ files; they are only seed input for this
loader. Geometry is inserted with ST_GeomFromGeoJSON (SRID 4326), and zones
are cast to MultiPolygon with ST_Multi to match the schema column type.
"""

import json
import os
import sys

import psycopg

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "data"))

# table -> (geojson file, column list)
FILES = [
    ("flood_zones", "flood_zones.geojson",
     "name, area, risk_level, return_period_years, source, geom"),
    ("shelters", "shelters.geojson",
     "name, area, shelter_type, capacity, current_occupancy, status, contact_phone, address, is_verified, geom"),
    ("roads", "roads.geojson",
     "name, area, road_type, status, geom"),
]

AREA_COLUMNS = ("slug", "name", "province", "river_name", "center_lng", "center_lat",
                "zoom", "min_lng", "min_lat", "max_lng", "max_lat", "default_radius_m")


def load_areas(cur):
    with open(os.path.join(DATA_DIR, "areas.json"), encoding="utf-8") as fh:
        areas = json.load(fh)["areas"]
    cur.executemany(
        "INSERT INTO areas (slug, name, province, river_name, center_lng, center_lat, "
        "zoom, min_lng, min_lat, max_lng, max_lat, default_radius_m) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        [tuple(a[c] for c in AREA_COLUMNS) for a in areas])
    return len(areas)


def load_features(conn_url):
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE areas, flood_zones, shelters, roads, flood_reports "
                        "RESTART IDENTITY CASCADE")
        with conn.cursor() as cur:
            counts = {"areas": load_areas(cur)}
        for table, filename, _columns in FILES:
            with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as fh:
                features = json.load(fh)["features"]
            rows = []
            for feat in features:
                props = feat["properties"]
                geom_json = json.dumps(feat["geometry"])
                if table == "flood_zones":
                    rows.append((props["name"], props["area"], props["risk_level"],
                                 props["return_period_years"], props["source"], geom_json))
                elif table == "shelters":
                    rows.append((props["name"], props["area"], props["shelter_type"],
                                 props["capacity"], props["current_occupancy"], props["status"],
                                 props["contact_phone"], props["address"], props["is_verified"],
                                 geom_json))
                else:
                    rows.append((props["name"], props["area"], props["road_type"],
                                 props["status"], geom_json))
            if table == "flood_zones":
                sql = ("INSERT INTO flood_zones (name, area, risk_level, return_period_years, source, geom) "
                       "VALUES (%s, %s, %s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))")
            elif table == "shelters":
                sql = ("INSERT INTO shelters (name, area, shelter_type, capacity, current_occupancy, "
                       "status, contact_phone, address, is_verified, geom) "
                       "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))")
            else:
                sql = ("INSERT INTO roads (name, area, road_type, status, geom) "
                       "VALUES (%s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))")
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
            counts[table] = len(rows)
    return counts


def main():
    conn_url = os.environ.get("DATABASE_URL")
    if not conn_url and len(sys.argv) > 1:
        conn_url = sys.argv[1]
    if not conn_url:
        sys.exit("Set DATABASE_URL or pass it as an argument, e.g. "
                 "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/webgis python scripts/load_data.py")
    try:
        counts = load_features(conn_url)
    except psycopg.OperationalError as exc:
        sys.exit(f"Could not connect to the database: {exc}")
    print("Loaded:", ", ".join(f"{table}={n}" for table, n in counts.items()))


if __name__ == "__main__":
    main()
