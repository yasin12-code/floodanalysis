"""POST /api/shelters: validation, insertion, unverified visibility (Section 8.2)."""


def valid_payload(**overrides):
    payload = {
        "name": "TEST-Shelter School",
        "shelter_type": "school",
        "capacity": 300,
        "contact_phone": "+92 300 1234567",
        "address": "Test Street, Nowshera",
        "lat": 34.05,
        "lng": 71.99,
    }
    payload.update(overrides)
    return payload


def test_create_shelter_returns_201_feature(client, cleanup_test_rows):
    res = client.post("/api/shelters", json=valid_payload())
    assert res.status_code == 201
    body = res.json()
    assert body["type"] == "Feature"
    assert body["geometry"]["type"] == "Point"
    props = body["properties"]
    assert props["name"] == "TEST-Shelter School"
    assert props["is_verified"] is False
    assert props["status"] == "open"
    assert props["capacity"] == 300
    assert props["id"]


def test_created_shelter_hidden_then_visible_when_unverified_included(client, cleanup_test_rows):
    res = client.post("/api/shelters", json=valid_payload())
    shelter_id = res.json()["properties"]["id"]
    bbox = "71.98,34.04,72.00,34.06"
    hidden = client.get("/api/layers/shelters", params={"bbox": bbox}).json()
    assert all(f["properties"]["id"] != shelter_id for f in hidden["features"])
    visible = client.get("/api/layers/shelters",
                         params={"bbox": bbox, "include_unverified": "true"}).json()
    assert any(f["properties"]["id"] == shelter_id for f in visible["features"])


def test_invalid_shelter_payloads_return_422(client, cleanup_test_rows):
    assert client.post("/api/shelters", json=valid_payload(name="")).status_code == 422
    assert client.post("/api/shelters", json=valid_payload(name="x" * 121)).status_code == 422
    assert client.post("/api/shelters", json=valid_payload(shelter_type="bunker")).status_code == 422
    assert client.post("/api/shelters", json=valid_payload(capacity=-1)).status_code == 422
    assert client.post("/api/shelters", json=valid_payload(capacity=100001)).status_code == 422
    assert client.post("/api/shelters", json=valid_payload(contact_phone="abc-123")).status_code == 422
    assert client.post("/api/shelters", json=valid_payload(lat=200)).status_code == 422
    # outside the study area
    res = client.post("/api/shelters", json=valid_payload(lat=33.0, lng=70.0))
    assert res.status_code == 422
    assert "study area" in res.json()["detail"].lower()


def test_optional_fields(client, cleanup_test_rows):
    res = client.post("/api/shelters", json=valid_payload(contact_phone=None, address=None))
    assert res.status_code == 201
    assert res.json()["properties"]["contact_phone"] is None


def test_flood_report_create_and_validation(client, cleanup_test_rows):
    res = client.post("/api/flood-reports", json={
        "report_type": "water_level", "severity": 2,
        "description": "pytest cleanup marker", "lat": 34.0, "lng": 71.99,
    })
    assert res.status_code == 201
    assert res.json()["geometry"]["type"] == "Point"
    assert client.post("/api/flood-reports", json={
        "report_type": "fire", "severity": 2, "lat": 34.0, "lng": 71.99,
    }).status_code == 422
    assert client.post("/api/flood-reports", json={
        "report_type": "water_level", "severity": 0, "lat": 34.0, "lng": 71.99,
    }).status_code == 422
    # the new report appears in the reports layer
    fc = client.get("/api/layers/flood-reports").json()
    assert any(f["properties"]["description"] == "pytest cleanup marker" for f in fc["features"])
