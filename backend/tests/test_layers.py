"""Layer endpoints: GeoJSON FeatureCollections, filters, bbox, 5000-feature cap."""


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    # PostGIS_Version() only exists if the extension is installed.
    assert body["postgis_version"].startswith("3.")


def test_config(client):
    res = client.get("/api/config")
    assert res.status_code == 200
    body = res.json()
    for key in ("map_center_lat", "map_center_lng", "map_zoom", "study_area_bbox",
                "default_radius_m", "caution_radius_m"):
        assert key in body
    bbox = body["study_area_bbox"]
    assert bbox["min_lng"] < bbox["max_lng"] and bbox["min_lat"] < bbox["max_lat"]


def test_flood_zones_feature_collection(client):
    fc = client.get("/api/layers/flood-zones").json()
    assert fc["type"] == "FeatureCollection"
    assert 8 <= len(fc["features"]) <= 12
    for feature in fc["features"]:
        assert feature["geometry"]["type"] == "MultiPolygon"
        assert feature["properties"]["risk_level"] in (1, 2, 3, 4)


def test_flood_zones_risk_filter(client):
    all_fc = client.get("/api/layers/flood-zones").json()
    filtered = client.get("/api/layers/flood-zones", params={"risk_min": "4"}).json()
    assert all(f["properties"]["risk_level"] == 4 for f in filtered["features"])
    assert len(filtered["features"]) < len(all_fc["features"])
    multi = client.get("/api/layers/flood-zones",
                       params=[("risk_min", "3"), ("risk_min", "4")]).json()
    assert all(f["properties"]["risk_level"] in (3, 4) for f in multi["features"])
    assert len(multi["features"]) == 6
    assert client.get("/api/layers/flood-zones", params={"risk_min": "9"}).status_code == 422


def test_flood_zones_buffer_returns_caution_band(client):
    fc = client.get("/api/layers/flood-zones", params={"buffer_m": 500}).json()
    assert len(fc["features"]) == 12
    # ST_Buffer on geography returns plain Polygons
    assert all(f["geometry"]["type"] == "Polygon" for f in fc["features"])


def test_flood_zones_bbox(client):
    all_fc = client.get("/api/layers/flood-zones").json()
    small = client.get("/api/layers/flood-zones",
                       params={"bbox": "71.95,34.00,71.99,34.02"}).json()
    assert len(small["features"]) < len(all_fc["features"])
    assert client.get("/api/layers/flood-zones", params={"bbox": "1,2,3"}).status_code == 422


def test_shelters_hide_unverified_by_default(client):
    default = client.get("/api/layers/shelters").json()
    assert all(f["properties"]["is_verified"] for f in default["features"])
    with_unverified = client.get("/api/layers/shelters",
                                 params={"include_unverified": "true"}).json()
    assert len(with_unverified["features"]) > len(default["features"])


def test_shelters_filters(client):
    schools = client.get("/api/layers/shelters", params={"type": "school"}).json()
    assert schools["features"]
    assert all(f["properties"]["shelter_type"] == "school" for f in schools["features"])
    full = client.get("/api/layers/shelters", params={"status": "full"}).json()
    assert full["features"]
    assert all(f["properties"]["status"] == "full" for f in full["features"])
    big = client.get("/api/layers/shelters", params={"min_capacity": 1000}).json()
    assert all(f["properties"]["capacity"] >= 1000 for f in big["features"])
    assert client.get("/api/layers/shelters", params={"type": "bunker"}).status_code == 422


def test_shelters_include_max_risk_level(client):
    fc = client.get("/api/layers/shelters", params={"include_unverified": "true"}).json()
    assert any(f["properties"]["max_risk_level"] is not None for f in fc["features"])
    assert any(f["properties"]["max_risk_level"] is None for f in fc["features"])


def test_roads(client):
    fc = client.get("/api/layers/roads").json()
    assert fc["type"] == "FeatureCollection"
    assert 100 <= len(fc["features"]) <= 200
    assert all(f["geometry"]["type"] == "LineString" for f in fc["features"])


def test_roads_status_filter(client):
    flooded = client.get("/api/layers/roads", params={"status": "flooded"}).json()
    assert flooded["features"]
    assert all(f["properties"]["status"] == "flooded" for f in flooded["features"])
    blocked = client.get("/api/layers/roads", params={"status": "blocked"}).json()
    assert len(flooded["features"]) + len(blocked["features"]) >= 3


def test_roads_at_risk_only(client):
    all_roads = client.get("/api/layers/roads").json()
    risky = client.get("/api/layers/roads", params={"at_risk": "true"}).json()
    assert all(f["properties"]["max_risk_level"] is not None for f in risky["features"])
    assert 0 < len(risky["features"]) < len(all_roads["features"])


def test_5000_feature_cap(client, db_conn):
    """The layer response must never exceed 5000 features (Section 8)."""
    with db_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO roads (name, road_type, status, geom)
            SELECT 'TEST-cap', 'track', 'open',
                   ST_SetSRID(ST_MakeLine(
                       ST_MakePoint(71.87 + (g % 100) * 0.0001, 33.92),
                       ST_MakePoint(71.8701 + (g % 100) * 0.0001, 33.9201)), 4326)
            FROM generate_series(1, 5001) AS g
        """)
    db_conn.commit()
    try:
        fc = client.get("/api/layers/roads", params={"bbox": "71.85,33.90,72.10,34.12"}).json()
        assert len(fc["features"]) <= 5000
    finally:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM roads WHERE name = 'TEST-cap'")
        db_conn.commit()


def test_stats(client):
    res = client.get("/api/stats")
    assert res.status_code == 200
    body = res.json()
    assert body["area_km2_by_risk_level"]
    assert all(v > 0 for v in body["area_km2_by_risk_level"].values())
    assert body["shelters"]["inside_flood_zone"]["count"] >= 1
    assert body["shelters"]["outside_flood_zone"]["count"] >= 1
    assert body["open_available_capacity"] > 0
    assert body["roads_at_risk_km"] > 0
