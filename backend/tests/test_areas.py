"""Multi-area support: /api/areas list, per-area layers/stats, area validation."""

AREA_KEYS = ("slug", "name", "province", "river_name", "center_lat", "center_lng",
             "zoom", "min_lng", "min_lat", "max_lng", "max_lat", "default_radius_m")


def get_area(client, slug):
    return next(a for a in client.get("/api/areas").json()["areas"] if a["slug"] == slug)


def coords_of(fc):
    """All [lng, lat] pairs anywhere in a FeatureCollection's geometry."""
    def walk(node):
        if isinstance(node, list):
            if len(node) == 2 and all(isinstance(v, (int, float)) for v in node):
                yield node
            else:
                for child in node:
                    yield from walk(child)
    for feature in fc["features"]:
        yield from walk(feature["geometry"]["coordinates"])


def assert_within_area(coords, area, margin=0.005):
    for lng, lat in coords:
        assert area["min_lng"] - margin <= lng <= area["max_lng"] + margin, (lng, lat)
        assert area["min_lat"] - margin <= lat <= area["max_lat"] + margin, (lng, lat)


def test_areas_list_returns_all_study_areas(client):
    res = client.get("/api/areas")
    assert res.status_code == 200
    areas = res.json()["areas"]
    assert len(areas) == 8
    for area in areas:
        for key in AREA_KEYS:
            assert key in area, f"missing key {key!r} in {area.get('slug')}"
        assert area["min_lng"] < area["max_lng"] and area["min_lat"] < area["max_lat"]
    slugs = [a["slug"] for a in areas]
    assert "nowshera" in slugs and "lahore" in slugs and "sukkur" in slugs
    assert len(set(slugs)) == 8


def test_area_filter_changes_layer_features(client):
    lahore = get_area(client, "lahore")
    nowshera = get_area(client, "nowshera")
    lahore_fc = client.get("/api/layers/flood-zones", params={"area": "lahore"}).json()
    default_fc = client.get("/api/layers/flood-zones").json()
    assert len(lahore_fc["features"]) == len(default_fc["features"]) == 12
    assert_within_area(coords_of(lahore_fc), lahore)
    assert_within_area(coords_of(default_fc), nowshera)
    # Lahore is ~350 km from Nowshera: the first zone must move far away.
    def first_point(fc):
        return next(coords_of(fc))
    lahore_pt, nowshera_pt = first_point(lahore_fc), first_point(default_fc)
    assert abs(lahore_pt[0] - nowshera_pt[0]) > 2 and abs(lahore_pt[1] - nowshera_pt[1]) > 2


def test_area_filter_applies_to_shelters_and_roads(client):
    lahore = get_area(client, "lahore")
    lahore_shelters = client.get("/api/layers/shelters",
                                 params={"area": "lahore", "include_unverified": "true"}).json()
    assert lahore_shelters["features"]
    assert_within_area(coords_of(lahore_shelters), lahore)
    lahore_roads = client.get("/api/layers/roads", params={"area": "lahore"}).json()
    assert 100 <= len(lahore_roads["features"]) <= 200
    # Road gridlines may extend slightly past the study-area rectangle.
    assert_within_area(coords_of(lahore_roads), lahore, margin=0.02)


def test_stats_differ_per_area(client):
    lahore = client.get("/api/stats", params={"area": "lahore"}).json()
    nowshera = client.get("/api/stats").json()
    assert lahore["area_km2_by_risk_level"]
    assert lahore["area_km2_by_risk_level"]["1"] != nowshera["area_km2_by_risk_level"]["1"]
    assert lahore["roads_at_risk_km"] > 0


def test_unknown_area_422_on_validated_endpoints(client):
    res = client.get("/api/risk-check",
                     params={"lat": 74.358, "lng": 31.520, "radius_m": 1000, "area": "xyz"})
    assert res.status_code == 422
    assert "Unknown area" in res.json()["detail"]
    res = client.post("/api/shelters", json={
        "name": "TEST-Unknown Area", "shelter_type": "school", "capacity": 100,
        "lat": 74.358, "lng": 31.520, "area": "xyz",
    })
    assert res.status_code == 422
    # Unfiltered layer endpoints simply return nothing for unknown areas.
    fc = client.get("/api/layers/flood-zones", params={"area": "xyz"}).json()
    assert fc == {"type": "FeatureCollection", "features": []}


def test_risk_check_validates_point_against_area_bbox(client):
    # A point inside Lahore's bbox is rejected when asked for Nowshera.
    res = client.get("/api/risk-check",
                     params={"lat": 31.520, "lng": 74.358, "radius_m": 1000, "area": "nowshera"})
    assert res.status_code == 422
    assert "study area" in res.json()["detail"].lower()
    # The same point is accepted for Lahore.
    res = client.get("/api/risk-check",
                     params={"lat": 31.520, "lng": 74.358, "radius_m": 1000, "area": "lahore"})
    assert res.status_code == 200
    assert res.json()["status"] in ("in_zone", "near_zone", "outside")


def test_shelter_created_in_named_area(client, cleanup_test_rows):
    res = client.post("/api/shelters", json={
        "name": "TEST-Lahore Shelter", "shelter_type": "school", "capacity": 200,
        "lat": 31.520, "lng": 74.358, "area": "lahore",
    })
    assert res.status_code == 201
    shelter_id = res.json()["properties"]["id"]
    visible = client.get("/api/layers/shelters", params={
        "area": "lahore", "include_unverified": "true",
        "bbox": "74.30,31.47,74.42,31.57",
    }).json()
    assert any(f["properties"]["id"] == shelter_id for f in visible["features"])
    not_in_nowshera = client.get("/api/layers/shelters", params={
        "area": "nowshera", "include_unverified": "true",
    }).json()
    assert all(f["properties"]["id"] != shelter_id for f in not_in_nowshera["features"])


def test_reports_area_filter(client, cleanup_test_rows):
    client.post("/api/flood-reports", json={
        "report_type": "water_level", "severity": 2,
        "description": "pytest cleanup marker", "lat": 31.520, "lng": 74.358,
        "area": "lahore",
    })
    lahore = client.get("/api/layers/flood-reports", params={"area": "lahore"}).json()
    assert any(f["properties"]["description"] == "pytest cleanup marker"
               for f in lahore["features"])
    nowshera = client.get("/api/layers/flood-reports", params={"area": "nowshera"}).json()
    assert all(f["properties"]["description"] != "pytest cleanup marker"
               for f in nowshera["features"])
