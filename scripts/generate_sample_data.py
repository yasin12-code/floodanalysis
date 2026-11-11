"""Generate deterministic demo data for the Flood Risk and Shelter WebGIS.

Eight flood-prone river cities across Pakistan, each with its own river
corridor, nested flood-risk zones, shelters, roads and an entry in
data/areas.json. The Nowshera area reproduces the original PRD demo dataset
exactly (same seed and random stream), so existing tests and the PRD demo
keep working unchanged.

Run:      python scripts/generate_sample_data.py
Writes:   data/flood_zones.geojson, data/shelters.geojson, data/roads.geojson,
          data/areas.json, data/test_points.json

Pure Python (no GIS libraries). Flood-zone polygons are built by offsetting a
meandering river centreline on both sides with rounded end caps. Jitter is
proportional to the half-width, so higher-risk zones nest inside lower-risk
ones. A ray-casting point-in-polygon test and point-to-segment distances
verify every test point before it is written.
"""

import json
import math
import os
import random

SEED = 42
M_PER_DEG_LAT = 111_320.0
# Nowshera keeps the original constant so its output stays byte-identical;
# other areas compute their own value from their centre latitude.
M_PER_DEG_LNG_NOWSHERA = 111_320.0 * math.cos(math.radians(34.0))

RISK_LABELS = {1: "Low", 2: "Medium", 3: "High", 4: "Very high"}
RETURN_PERIODS = {1: 100, 2: 50, 3: 20, 4: 5}
SEGMENTS = {"West": (0.05, 0.35), "Central": (0.35, 0.65), "East": (0.65, 0.95)}

BASE_NAMES = ["Government High School", "Girls Primary School", "Basic Health Unit",
              "District Hospital", "Jamia Masjid", "Markazi Masjid", "Community Centre",
              "Tehsil Municipal Office", "Relief Camp", "Government Degree College"]
TYPES = ["school", "hospital", "community_center", "mosque", "government_building", "camp", "other"]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "data"))


def _nowshera_river(t):
    """Original Nowshera river formula, kept verbatim for byte-identical output."""
    lng = 71.87 + 0.20 * t
    lat = 34.025 - 0.028 * t + 0.0045 * math.sin(t * 10 + 0.7) + 0.0018 * math.sin(t * 23 + 2.1)
    return lng, lat


def _generic_river(start, end, meanders):
    """Straight corridor from start to end with perpendicular sine meanders."""
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy) or 1.0
    px, py = -dy / length, dx / length  # unit perpendicular

    def fn(t):
        d = sum(amp * math.sin(t * w + p) for amp, w, p in meanders)
        return sx + dx * t + px * d, sy + dy * t + py * d

    return fn


def _area(slug, name, province, river_name, center, zoom, bbox, half_widths,
          river_start, river_end, localities, guaranteed_localities, highways,
          default_radius_m):
    min_lng, min_lat, max_lng, max_lat = bbox
    river_fn = _generic_river(river_start, river_end,
                              ((0.0045, 10.0, 0.7), (0.0018, 23.0, 2.1)))
    return {
        "slug": slug, "name": name, "province": province, "river_name": river_name,
        "center_lng": center[0], "center_lat": center[1], "zoom": zoom,
        "min_lng": min_lng, "min_lat": min_lat, "max_lng": max_lng, "max_lat": max_lat,
        "half_widths": half_widths,
        "river_fn": river_fn,
        "river_polyline": [river_fn(i * 0.01) for i in range(101)],
        "m_per_deg_lng": 111_320.0 * math.cos(math.radians(center[1])),
        "grid": (min_lat + 0.025, max_lat - 0.015, 0.0075,
                 min_lng + 0.025, max_lng - 0.025, 0.008),
        "shelter_box": (min_lng + 0.03, min_lat + 0.03, max_lng - 0.03, max_lat - 0.02),
        "localities": localities,
        "guaranteed_localities": guaranteed_localities,
        "highways": highways,
        "default_radius_m": default_radius_m,
    }


AREAS = {
    "nowshera": {
        "slug": "nowshera", "name": "Nowshera", "province": "KP", "river_name": "Kabul River",
        "center_lng": 71.974, "center_lat": 34.006, "zoom": 13,
        "min_lng": 71.85, "min_lat": 33.90, "max_lng": 72.10, "max_lat": 34.12,
        "half_widths": {1: 1500.0, 2: 900.0, 3: 450.0, 4: 200.0},
        "river_fn": _nowshera_river,
        "river_polyline": [_nowshera_river(i * 0.01) for i in range(101)],
        "m_per_deg_lng": M_PER_DEG_LNG_NOWSHERA,
        "grid": (33.925, 34.105, 0.0075, 71.875, 72.075, 0.008),
        "shelter_box": (71.88, 33.93, 72.07, 34.10),
        "localities": ["Nowshera Kalan", "Nowshera Cantt", "Akora Khattak", "Risalpur",
                       "Pabbi", "Amangarh", "Kabul River Road", "GT Road", "Mardan Road", "Pir Piai"],
        "guaranteed_localities": None,
        "highways": [("GT Road (N-5)", "trunk", (71.865, 34.062), (0.0275, -0.00175), 0.0008, 9),
                     ("M-1 Motorway", "motorway", (71.868, 33.955), (0.0357, 0.0017), 0.0, 7)],
        "default_radius_m": 3000,
    },
    "peshawar": _area("peshawar", "Peshawar", "KP", "Kabul River",
                      (71.525, 34.015), 13, (71.40, 33.90, 71.65, 34.13),
                      {1: 1600.0, 2: 950.0, 3: 480.0, 4: 220.0},
                      (71.42, 34.10), (71.63, 33.92),
                      ["Peshawar City", "Hayatabad", "University Town", "Saddar", "Charsadda Road",
                       "Ring Road", "Warsak Road", "Kohat Road", "Dalazak Road", "Gulbahar"],
                      ["University Town", "University Road", "Hayatabad", "Dalazak Road"],
                      [("GT Road (N-5)", "trunk", (71.41, 34.09), (0.0275, -0.0125), 0.0008, 9),
                       ("M-1 Motorway", "motorway", (71.405, 33.93), (0.0357, 0.012), 0.0, 7)],
                      3000),
    "charsadda": _area("charsadda", "Charsadda", "KP", "Swat River",
                       (71.740, 34.148), 13, (71.61, 34.03, 71.87, 34.26),
                       {1: 1800.0, 2: 1100.0, 3: 550.0, 4: 260.0},
                       (71.63, 34.24), (71.85, 34.05),
                       ["Charsadda City", "Tangi", "Shabqadar", "Umarzai", "Rajjar",
                        "Prang", "Utmanzai", "Matta Mughal Khel", "Sardaryab", "Khyali"],
                       ["Charsadda City", "Shabqadar Road", "Tangi", "Umarzai"],
                       [("Charsadda Road (N-45)", "trunk", (71.62, 34.25), (0.028, -0.02), 0.0006, 9),
                        ("Swat Motorway", "motorway", (71.82, 34.06), (0.006, 0.024), 0.0, 7)],
                       3500),
    "mardan": _area("mardan", "Mardan", "KP", "Kalpani River",
                    (72.044, 34.198), 13, (71.92, 34.08, 72.17, 34.31),
                    {1: 1400.0, 2: 850.0, 3: 420.0, 4: 180.0},
                    (71.94, 34.29), (72.15, 34.10),
                    ["Mardan City", "Takht Bhai", "Sheikh Maltoon Town", "Par Hoti", "Katlang",
                     "Lund Khwar", "Baghicha Dheri", "Hoti", "Garhi Kapura", "Mayar"],
                    ["Mardan City", "Nowshera Road", "Takht Bhai", "Sheikh Maltoon Town"],
                    [("N-45 (Mardan-Malakand)", "trunk", (72.02, 34.30), (0.004, -0.024), 0.0005, 9),
                     ("Mardan Ring Road", "secondary", (72.09, 34.085), (0.013, 0.024), 0.0, 7)],
                    3000),
    "islamabad": _area("islamabad", "Islamabad", "ICT", "Soan River",
                       (73.048, 33.684), 13, (72.92, 33.58, 73.18, 33.79),
                       {1: 1200.0, 2: 700.0, 3: 350.0, 4: 150.0},
                       (72.94, 33.64), (73.16, 33.70),
                       ["Blue Area", "Sector F-6", "Sector F-8", "Sector G-9", "Sector G-10",
                        "Sector I-8", "Sector I-10", "Sohan", "Bara Kahu", "Rawal Town"],
                       ["Blue Area", "Sector G-9", "G-9 Markaz", "Sohan"],
                       [("Kashmir Highway", "trunk", (72.93, 33.66), (0.03, -0.002), 0.0004, 9),
                        ("Islamabad Expressway", "primary", (72.95, 33.735), (0.025, -0.005), 0.0005, 9)],
                       2500),
    "lahore": _area("lahore", "Lahore", "Punjab", "Ravi River",
                    (74.358, 31.520), 13, (74.22, 31.42, 74.50, 31.62),
                    {1: 2200.0, 2: 1300.0, 3: 650.0, 4: 300.0},
                    (74.24, 31.60), (74.48, 31.44),
                    ["Gulberg", "Model Town", "Johar Town", "Wapda Town", "Iqbal Town",
                     "DHA", "Shahdara", "Aziz Bhatti Road", "Ferozepur Road", "Canal Road"],
                    ["Gulberg", "Model Town", "Johar Town", "Shahdara"],
                    [("Multan Road", "trunk", (74.23, 31.60), (0.03, -0.013), 0.0006, 9),
                     ("Lahore Ring Road", "primary", (74.36, 31.425), (0.005, 0.022), 0.0, 7)],
                    3500),
    "multan": _area("multan", "Multan", "Punjab", "Chenab River",
                    (71.524, 30.158), 13, (71.39, 30.06, 71.66, 30.26),
                    {1: 2600.0, 2: 1600.0, 3: 800.0, 4: 380.0},
                    (71.41, 30.24), (71.64, 30.08),
                    ["Multan Cantt", "Bosan Road", "Shah Rukn-e-Alam", "Chowk Kumharanwala",
                     "Gulgasht Colony", "Mumtazabad", "Vehari Road", "Shujabad Road",
                     "Qasim Bela", "Daulat Gate"],
                    ["Multan Cantt", "Bosan Road", "Shah Rukn-e-Alam", "Vehari Road"],
                    [("N-5 (Multan Bypass)", "trunk", (71.40, 30.24), (0.028, -0.018), 0.0007, 9),
                     ("M-5 Motorway", "motorway", (71.62, 30.065), (0.004, 0.023), 0.0, 7)],
                    4500),
    "sukkur": _area("sukkur", "Sukkur", "Sindh", "Indus River",
                    (68.858, 27.705), 13, (68.72, 27.60, 69.00, 27.81),
                    {1: 3500.0, 2: 2100.0, 3: 1050.0, 4: 500.0},
                    (68.74, 27.79), (68.98, 27.62),
                    ["Sukkur City", "Rohri", "Military Road", "Shikarpur Road", "Barrage Colony",
                     "Gharibabad", "Saleh Pat", "Pano Aqil", "Bunder Road", "Minara Road"],
                    ["Sukkur City", "Military Road", "Rohri", "Shikarpur Road"],
                    [("N-5 (Sukkur)", "trunk", (68.73, 27.79), (0.029, -0.018), 0.0006, 9),
                     ("Sukkur Bypass (M-5)", "motorway", (68.845, 27.605), (0.004, 0.024), 0.0, 7)],
                    5000),
}


def river_point(area, t):
    """Point on the area's meandering river centreline, t in [0, 1]."""
    return area["river_fn"](t)


def _seg_pts(area, seg_start, seg_end, step=0.01):
    n = int(round((seg_end - seg_start) / step)) + 1
    return [river_point(area, seg_start + i * step) for i in range(n)]


def _unit_tangent(a, b):
    """Unit tangent of segment a->b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    return dx / length, dy / length


def _unit_normal(a, b):
    """Unit normal of segment a->b, flipped to point north (lat increasing)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length
    if ny < 0:
        nx, ny = -nx, -ny
    return nx, ny


def _normal_at(pts, i):
    a = pts[max(i - 1, 0)]
    b = pts[min(i + 1, len(pts) - 1)]
    return _unit_normal(a, b)


def _arc_points(center, tangent, normal, w_lng, w_lat, jit, steps=8):
    """Rounded cap: arc from the left side (+normal) to the right side (-normal)."""
    pts = []
    for k in range(1, steps):
        theta = math.pi * k / steps
        direction = (normal[0] * math.cos(theta) + tangent[0] * math.sin(theta),
                     normal[1] * math.cos(theta) + tangent[1] * math.sin(theta))
        pts.append((center[0] + direction[0] * w_lng * jit,
                    center[1] + direction[1] * w_lat * jit))
    return pts


def zone_ring(area, seg_start, seg_end, half_width_m, rng):
    """Closed polygon ring around a river segment at a given half-width."""
    pts = _seg_pts(area, seg_start, seg_end)
    w_lng = half_width_m / area["m_per_deg_lng"]
    w_lat = half_width_m / M_PER_DEG_LAT
    # Jitter shared by every risk level of this segment (proportional to width
    # when applied), which keeps higher-risk polygons nested in lower-risk ones.
    jits = [1.0 + 0.12 * math.sin(i * 0.55) + 0.04 * rng.uniform(-1.0, 1.0) for i in range(len(pts))]

    left, right = [], []
    for i, (lng, lat) in enumerate(pts):
        nx, ny = _normal_at(pts, i)
        j = jits[i]
        left.append((lng + nx * w_lng * j, lat + ny * w_lat * j))
        right.append((lng - nx * w_lng * j, lat - ny * w_lat * j))

    end_n = _normal_at(pts, len(pts) - 1)
    start_n = _normal_at(pts, 0)
    end_cap = _arc_points(pts[-1], _unit_tangent(pts[-2], pts[-1]), end_n, w_lng, w_lat, jits[-1])
    tx, ty = _unit_tangent(pts[0], pts[1])
    start_cap = _arc_points(pts[0], (-tx, -ty), start_n, w_lng, w_lat, jits[0])
    start_cap = list(reversed(start_cap))

    ring = left + end_cap + list(reversed(right)) + start_cap
    ring.append(ring[0])
    return ring


def point_in_ring(pt, ring):
    """Ray-casting point-in-polygon test (works for the simple rings above)."""
    x, y = pt
    inside = False
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def point_in_feature(pt, feature):
    return point_in_ring(pt, feature["geometry"]["coordinates"][0])


def distance_point_to_segment(p, a, b):
    """Metres from point p to segment a-b (both in degrees, converted to metres)."""
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot((px - ax) * M_PER_DEG_LNG_NOWSHERA, (py - ay) * M_PER_DEG_LAT)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot((px - cx) * M_PER_DEG_LNG_NOWSHERA, (py - cy) * M_PER_DEG_LAT)


def distance_point_to_ring(pt, ring):
    """Distance in metres from a point to a ring's boundary (0 if inside)."""
    if point_in_ring(pt, ring):
        return 0.0
    best = float("inf")
    for i in range(len(ring) - 1):
        best = min(best, distance_point_to_segment(pt, ring[i], ring[i + 1]))
    return best


def distance_to_feature_m(pt, feature):
    """Metres from a point to a polygon: 0 if inside, else distance to boundary."""
    ring = feature["geometry"]["coordinates"][0]
    best = float("inf")
    for i in range(len(ring) - 1):
        best = min(best, distance_point_to_segment(pt, ring[i], ring[i + 1]))
    return 0.0 if point_in_ring(pt, ring) else best


def risk_of(pt, zones):
    """Highest risk level among zones containing the point, 0 if outside all."""
    return max((z["properties"]["risk_level"] for z in zones if point_in_feature(pt, z)), default=0)


def offset_point(area, t, metres):
    """River point at parameter t, offset `metres` to the north side."""
    a = river_point(area, t - 0.005)
    b = river_point(area, t + 0.005)
    nx, ny = _unit_normal(a, b)
    lng, lat = river_point(area, t)
    return (lng + nx * metres / area["m_per_deg_lng"], lat + ny * metres / M_PER_DEG_LAT)


def generate_zones(area, rng):
    features = []
    for seg_name, (start, end) in SEGMENTS.items():
        for level in (1, 2, 3, 4):
            ring = zone_ring(area, start, end, area["half_widths"][level], rng)
            features.append({
                "type": "Feature",
                "properties": {
                    "name": f"{area['river_name']} {seg_name} — {RISK_LABELS[level]} risk zone",
                    "risk_level": level,
                    "return_period_years": RETURN_PERIODS[level],
                    "source": "Generated demo data (deterministic, seed 42)",
                    "area": area["slug"],
                },
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            })
    # Verify nesting: every vertex of a higher-risk polygon must sit inside the
    # next-lower-risk polygon of the same segment (same jitter profile).
    by_key = {(f["properties"]["name"].split(" —")[0], f["properties"]["risk_level"]): f for f in features}
    for seg_name in SEGMENTS:
        for level in (2, 3, 4):
            outer = by_key[(f"{area['river_name']} {seg_name}", level - 1)]["geometry"]["coordinates"][0]
            inner = by_key[(f"{area['river_name']} {seg_name}", level)]["geometry"]["coordinates"][0]
            for pt in inner:
                assert point_in_ring(pt, outer), f"{area['slug']} {seg_name} level {level} not nested in level {level - 1}"
    return features


def _generic_guaranteed(area):
    """The 7 guaranteed shelters (one per UI state), positioned by zone width."""
    city, prov = area["name"], area["province"]
    loc = area["guaranteed_localities"]
    hw1 = area["half_widths"][1]
    return [
        dict(name=f"Government Boys High School {city}", shelter_type="school", capacity=600,
             occupancy=240, status="open", verified=True, phone="+92 333 4512101",
             address=f"{loc[0]}, {city}, {prov}", offset=hw1 + 600),
        dict(name="Riverside Community Centre", shelter_type="community_center", capacity=150,
             occupancy=60, status="open", verified=True, phone="+92 333 4512102",
             address=f"{area['river_name']} Road, {city}, {prov}", offset=80),
        dict(name="Al-Khidmat Relief Camp", shelter_type="camp", capacity=400,
             occupancy=400, status="full", verified=True, phone="+92 333 4512103",
             address=f"Cantt Area, {city}, {prov}", offset=hw1 + 3000),
        dict(name=f"Civil Hospital {city}", shelter_type="hospital", capacity=250,
             occupancy=0, status="closed", verified=True, phone="+92 333 4512104",
             address=f"Main Bazaar, {city}, {prov}", offset=-(hw1 + 3500)),
        dict(name="Jamia Masjid Taqwa", shelter_type="mosque", capacity=500,
             occupancy=130, status="open", verified=False, phone="+92 333 4512105",
             address=f"{loc[1]}, {city}, {prov}", offset=hw1 + 1700),
        dict(name=f"Community Centre {loc[2]} (proposed)", shelter_type="community_center",
             capacity=300, occupancy=0, status="open", verified=False, phone=None,
             address=f"{loc[2]}, {city}, {prov}", offset=hw1 + 2100),
        dict(name=f"Government Primary School {loc[3]} (unverified)", shelter_type="school",
             capacity=350, occupancy=90, status="open", verified=False, phone="+92 333 4512106",
             address=f"{loc[3]}, {city}, {prov}", offset=-(hw1 + 1700)),
    ]


def generate_shelters(area, rng, zones):
    features = []

    def add(name, lng, lat, shelter_type, capacity, occupancy, status, verified, phone, address):
        features.append({
            "type": "Feature",
            "properties": {
                "name": name,
                "shelter_type": shelter_type,
                "capacity": capacity,
                "current_occupancy": occupancy,
                "status": status,
                "contact_phone": phone,
                "address": address,
                "is_verified": verified,
                "area": area["slug"],
            },
            "geometry": {"type": "Point", "coordinates": [round(lng, 6), round(lat, 6)]},
        })

    # Guaranteed shelters so every UI state can be demonstrated.
    if area["slug"] == "nowshera":
        lng, lat = offset_point(area, 0.5, 2100)          # outside every zone
        add("Government Boys High School Nowshera Kalan", lng, lat, "school", 600, 240,
            "open", True, "+92 333 4512101", "Nowshera Kalan, Nowshera, KP")
        lng, lat = offset_point(area, 0.5, 80)            # inside the level-4 zone: flagged unsafe
        add("Riverside Community Centre", lng, lat, "community_center", 150, 60,
            "open", True, "+92 333 4512102", "Kabul River Road, Nowshera, KP")
        lng, lat = offset_point(area, 0.5, 4500)          # full: orange marker
        add("Al-Khidmat Relief Camp", lng, lat, "camp", 400, 400,
            "full", True, "+92 333 4512103", "Cantt Area, Nowshera, KP")
        lng, lat = offset_point(area, 0.5, -5000)         # closed: grey marker
        add("Civil Hospital Nowshera", lng, lat, "hospital", 250, 0,
            "closed", True, "+92 333 4512104", "Main Bazaar, Nowshera, KP")
        lng, lat = offset_point(area, 0.5, 3200)          # unverified: hidden by default
        add("Jamia Masjid Taqwa", lng, lat, "mosque", 500, 130,
            "open", False, "+92 333 4512105", "Risalpur Road, Nowshera, KP")
        lng, lat = offset_point(area, 0.5, 3600)
        add("Community Centre Amangarh (proposed)", lng, lat, "community_center", 300, 0,
            "open", False, None, "Amangarh, Nowshera, KP")
        lng, lat = offset_point(area, 0.5, -3200)
        add("Government Primary School Pir Piai (unverified)", lng, lat, "school", 350, 90,
            "open", False, "+92 333 4512106", "Pir Piai, Nowshera, KP")
    else:
        for g in _generic_guaranteed(area):
            lng, lat = offset_point(area, 0.5, g.pop("offset"))
            add(g.pop("name"), lng, lat, g.pop("shelter_type"), g.pop("capacity"),
                g.pop("occupancy"), g.pop("status"), g.pop("verified"),
                g.pop("phone"), g.pop("address"))

    min_lng, min_lat, max_lng, max_lat = area["shelter_box"]
    localities = area["localities"]

    used_names = set()
    while len(features) < 32:
        name = f"{rng.choice(BASE_NAMES)} {rng.choice(localities)}"
        if name in used_names:
            name = f"{name} {rng.randint(2, 99)}"
        used_names.add(name)
        lng = round(rng.uniform(min_lng, max_lng), 6)
        lat = round(rng.uniform(min_lat, max_lat), 6)
        capacity = rng.randint(50, 1500)
        roll = rng.random()
        if roll < 0.85:
            status, occupancy = "open", rng.randint(0, capacity)
        elif roll < 0.925:
            status, occupancy = "full", capacity
        else:
            status, occupancy = "closed", rng.randint(0, capacity)
        add(name, lng, lat, rng.choice(TYPES), capacity, occupancy, status,
            rng.random() < 0.85, f"+92 3{rng.randint(0, 9)}{rng.randint(0, 9)} {rng.randint(1000000, 9999999)}",
            f"{rng.choice(localities)}, {area['name']}, {area['province']}")

    assert 25 <= len(features) <= 40, f"expected 25-40 shelters, got {len(features)}"
    return features


def _signed_side(pt, area):
    """Side of the local river polyline the point sits on (via cross product)."""
    px, py = pt
    best_sign = 0.0
    best_d = float("inf")
    for a, b in zip(area["river_polyline"], area["river_polyline"][1:]):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            continue
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t * dx, ay + t * dy
        d = math.hypot((px - cx) * area["m_per_deg_lng"], (py - cy) * M_PER_DEG_LAT)
        if d < best_d:
            best_d = d
            best_sign = 1.0 if dx * (py - ay) - dy * (px - ax) > 0 else -1.0
    return best_sign


def generate_roads(area, rng, zones):
    features = []

    def add(name, road_type, status, coords):
        features.append({
            "type": "Feature",
            "properties": {"name": name, "road_type": road_type, "status": status,
                           "area": area["slug"]},
            "geometry": {"type": "LineString", "coordinates": coords},
        })

    def jitter(lng, lat):
        return (round(lng + rng.uniform(-0.0008, 0.0008), 6),
                round(lat + rng.uniform(-0.0008, 0.0008), 6))

    # Rough street grid across the floodplain, each line split into 3 segments.
    lat_start, lat_end, lat_step, lng_start, lng_end, lng_step = area["grid"]
    street_no = 0
    lat = lat_start
    while lat <= lat_end:
        road_type = "secondary" if street_no % 5 == 0 else "residential"
        name = f"{road_type.capitalize()} Road {street_no}, {area['name']}"
        pts = [jitter(lng_start + k * 0.0667, lat) for k in range(4)]
        for k in range(3):
            add(name, road_type, "open", [pts[k], pts[k + 1]])
        street_no += 1
        lat += lat_step
    lng = lng_start
    while lng <= lng_end:
        road_type = "tertiary" if street_no % 4 == 0 else "residential"
        name = f"Street {street_no}, {area['name']}"
        pts = [jitter(lng, lat_start + k * 0.06) for k in range(4)]
        for k in range(3):
            add(name, road_type, "open", [pts[k], pts[k + 1]])
        street_no += 1
        lng += lng_step

    # Trunk road and motorway across the study area.
    for name, road_type, (base_lng, base_lat), (d_lng, d_lat), amp, k_count in area["highways"]:
        pts = [jitter(base_lng + k * d_lng, base_lat + k * d_lat + amp * math.sin(k))
               for k in range(k_count)]
        for k in range(k_count - 1):
            add(name, road_type, "open", [pts[k], pts[k + 1]])

    def crosses_river(seg):
        (a_lng, a_lat), (b_lng, b_lat) = seg["geometry"]["coordinates"]
        if area["slug"] == "nowshera":
            fa = a_lat - _nowshera_river((a_lng - 71.87) / 0.20)[1]
            fb = b_lat - _nowshera_river((b_lng - 71.87) / 0.20)[1]
            return fa * fb < 0
        return _signed_side((a_lng, a_lat), area) != _signed_side((b_lng, b_lat), area)

    # Force flood/blocked states on river crossings (at least 3 total).
    flooded = blocked = 0
    for feat in features:
        if flooded + blocked >= 4:
            break
        if feat["properties"]["road_type"] in ("residential", "tertiary", "secondary") and crosses_river(feat):
            if flooded < 2:
                feat["properties"]["status"] = "flooded"
                flooded += 1
            else:
                feat["properties"]["status"] = "blocked"
                blocked += 1

    assert 100 <= len(features) <= 200, f"expected 100-200 roads, got {len(features)}"
    assert flooded + blocked >= 3, f"{area['slug']}: need at least 3 flooded/blocked roads"
    return features


def find_test_points(area, zones):
    inside4 = river_point(area, 0.5)
    assert risk_of(inside4, zones) == 4, "inside_level_4 point must sit in a level-4 zone"

    inside1 = None
    for metres in range(1000, 1500, 25):
        pt = offset_point(area, 0.5, metres)
        if risk_of(pt, zones) == 1:
            inside1 = pt
            break
    assert inside1 is not None, "could not find a point inside level 1 only"

    near = None
    for metres in range(1700, 1950, 25):
        pt = offset_point(area, 0.5, metres)
        d = min(distance_to_feature_m(pt, z) for z in zones)
        if risk_of(pt, zones) == 0 and 200.0 <= d <= 450.0:
            near = pt
            break
    assert near is not None, "could not find a point within 500 m of a zone"

    far = None
    for metres in (8000, 8500, 9000, 9500):
        pt = offset_point(area, 0.5, metres)
        d = min(distance_to_feature_m(pt, z) for z in zones)
        min_lng, min_lat, max_lng, max_lat = area["min_lng"], area["min_lat"], area["max_lng"], area["max_lat"]
        if risk_of(pt, zones) == 0 and d >= 5000.0 and min_lng <= pt[0] <= max_lng and min_lat <= pt[1] <= max_lat:
            far = pt
            break
    assert far is not None, "could not find a far-outside point inside the study area"

    return inside4, inside1, near, far


def main():
    zones_by_area, shelters_by_area, roads_by_area = {}, {}, {}
    for area in AREAS.values():
        rng = random.Random(SEED)
        zones_by_area[area["slug"]] = generate_zones(area, rng)
        shelters_by_area[area["slug"]] = generate_shelters(area, rng, zones_by_area[area["slug"]])
        roads_by_area[area["slug"]] = generate_roads(area, rng, zones_by_area[area["slug"]])

    # Sanity: every area's river centre must sit inside its own level-4 zone,
    # and its test-shelter demo states must be positioned correctly.
    for slug, area in AREAS.items():
        centre = river_point(area, 0.5)
        assert risk_of(centre, zones_by_area[slug]) == 4, \
            f"{slug}: river centre must sit in its level-4 zone"

    nowshera = AREAS["nowshera"]
    inside4, inside1, near, far = find_test_points(nowshera, zones_by_area["nowshera"])

    def fc(features):
        return {"type": "FeatureCollection", "features": features}

    os.makedirs(DATA_DIR, exist_ok=True)
    files = {
        "flood_zones.geojson": fc(sum(zones_by_area.values(), [])),
        "shelters.geojson": fc(sum(shelters_by_area.values(), [])),
        "roads.geojson": fc(sum(roads_by_area.values(), [])),
        "areas.json": {
            "areas": [
                {k: area[k] for k in ("slug", "name", "province", "river_name",
                                      "center_lng", "center_lat", "zoom",
                                      "min_lng", "min_lat", "max_lng", "max_lat",
                                      "default_radius_m")}
                for area in AREAS.values()
            ]
        },
        "test_points.json": {
            "points": {
                "inside_level_4": {"lng": round(inside4[0], 6), "lat": round(inside4[1], 6),
                                   "expected_status": "in_zone", "expected_risk_level": 4},
                "inside_level_1": {"lng": round(inside1[0], 6), "lat": round(inside1[1], 6),
                                   "expected_status": "in_zone", "expected_risk_level": 1},
                "within_500m_of_zone": {"lng": round(near[0], 6), "lat": round(near[1], 6),
                                        "expected_status": "near_zone",
                                        "expected_nearest_zone_distance_m_min": 200,
                                        "expected_nearest_zone_distance_m_max": 500},
                "far_outside": {"lng": round(far[0], 6), "lat": round(far[1], 6),
                                "expected_status": "outside",
                                "expected_nearest_zone_distance_m_min": 5000},
            }
        },
    }
    for name, payload in files.items():
        with open(os.path.join(DATA_DIR, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

    print(f"areas={len(AREAS)} zones={len(files['flood_zones.geojson']['features'])} "
          f"shelters={len(files['shelters.geojson']['features'])} "
          f"roads={len(files['roads.geojson']['features'])}")
    for slug, area in AREAS.items():
        inside = sum(1 for s in shelters_by_area[slug]
                     if risk_of(s["geometry"]["coordinates"], zones_by_area[slug]) > 0)
        at_risk = sum(1 for r in roads_by_area[slug]
                      if r["properties"]["status"] in ("flooded", "blocked"))
        print(f"  {slug:10s} zones={len(zones_by_area[slug]):2d} "
              f"shelters={len(shelters_by_area[slug]):2d} (in_zone={inside:2d}) "
              f"roads={len(roads_by_area[slug]):3d} at_risk={at_risk}")
    print("test points:", {k: v["expected_status"] for k, v in files["test_points.json"]["points"].items()})


if __name__ == "__main__":
    main()
