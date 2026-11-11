"""risk-check behaviour against data/test_points.json (Section 12, phase 5)."""

from conftest import load_test_points

TEST_POINTS = load_test_points()


def risk_check(client, point, **params):
    return client.get("/api/risk-check", params={"lng": point["lng"], "lat": point["lat"], **params})


def test_inside_level_4_zone(client):
    res = risk_check(client, TEST_POINTS["inside_level_4"])
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "in_zone"
    assert body["risk_level"] == 4
    assert body["risk_label"] == "Very high"
    assert len(body["zones"]) >= 1
    assert all(z["risk_level"] in (1, 2, 3, 4) for z in body["zones"])
    assert body["nearest_zone_distance_m"] == 0
    assert body["search_buffer"]["type"] == "Polygon"
    assert body["radius_m"] == 3000
    assert body["flooded_roads_in_radius"] >= 0
    assert len(body["shelters"]) > 0


def test_inside_level_1_zone(client):
    res = risk_check(client, TEST_POINTS["inside_level_1"])
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "in_zone"
    assert body["risk_level"] == 1
    assert body["risk_label"] == "Low"


def test_within_500m_of_zone(client):
    pt = TEST_POINTS["within_500m_of_zone"]
    res = risk_check(client, pt)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "near_zone"
    assert body["risk_level"] is None
    assert body["zones"] == []
    distance = body["nearest_zone_distance_m"]
    assert pt["expected_nearest_zone_distance_m_min"] <= distance <= pt["expected_nearest_zone_distance_m_max"]


def test_far_outside(client):
    pt = TEST_POINTS["far_outside"]
    res = risk_check(client, pt)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "outside"
    assert body["risk_level"] is None
    assert body["zones"] == []
    assert body["nearest_zone_distance_m"] >= pt["expected_nearest_zone_distance_m_min"]


def test_shelters_sorted_by_distance_with_fields(client):
    body = risk_check(client, TEST_POINTS["inside_level_4"]).json()
    distances = [s["distance_m"] for s in body["shelters"]]
    assert distances == sorted(distances)
    for shelter in body["shelters"]:
        assert 0 <= shelter["available"] <= shelter["capacity"]
        assert shelter["distance_m"] <= body["radius_m"] + 1
        assert shelter["in_flood_zone"] in (True, False)
    # the riverside community centre sits inside a flood zone near the point
    assert any(s["in_flood_zone"] for s in body["shelters"])


def test_recommendation_is_safe_and_open(client):
    pt = TEST_POINTS["inside_level_4"]
    body = risk_check(client, pt).json()
    if body["recommended_shelter_id"] is not None:
        rec = next(s for s in body["shelters"] if s["id"] == body["recommended_shelter_id"])
        assert rec["status"] == "open"
        assert rec["available"] > 0
        assert rec["in_flood_zone"] is False
    # with a wide radius a safe recommendation must exist
    wide = risk_check(client, pt, radius_m=10000).json()
    assert wide["recommended_shelter_id"] is not None


def test_limit_and_radius_params(client):
    pt = TEST_POINTS["inside_level_4"]
    assert len(risk_check(client, pt, limit=2).json()["shelters"]) <= 2
    assert risk_check(client, pt, limit=20).status_code == 200
    assert risk_check(client, pt, radius_m=500).json()["radius_m"] == 500


def test_invalid_input_returns_422(client):
    pt = TEST_POINTS["inside_level_4"]
    assert client.get("/api/risk-check", params={"lat": pt["lat"]}).status_code == 422  # missing lng
    assert risk_check(client, pt, radius_m=99).status_code == 422
    assert risk_check(client, pt, radius_m=20001).status_code == 422
    assert risk_check(client, pt, limit=0).status_code == 422
    assert risk_check(client, pt, limit=21).status_code == 422
    assert client.get("/api/risk-check", params={"lat": 91, "lng": 0}).status_code == 422


def test_outside_study_area_returns_422(client):
    res = risk_check(client, {"lng": 73.0, "lat": 34.5})
    assert res.status_code == 422
    assert "study area" in res.json()["detail"].lower()
