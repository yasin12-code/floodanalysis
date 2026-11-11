# Flood Risk and Shelter WebGIS

A web GIS that shows flood-prone zones, emergency shelters and roads on one
interactive map. Click any location and you immediately learn whether it lies
inside a flood risk zone, which shelters are nearby and how far each one is,
and whether the shelter itself is safe from flooding.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![PostGIS](https://img.shields.io/badge/PostGIS-3.4-41719c)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![Leaflet](https://img.shields.io/badge/Leaflet-1.9.4-199900)

![Main map with flood zones, shelters and roads](docs/screenshot-map.png)

**Study areas:** eight flood-prone river cities in Pakistan — Nowshera
(default), Peshawar, Charsadda, Mardan, Islamabad, Lahore, Multan and Sukkur.
The "Study area" dropdown in the header switches between them; each area has
its own zones, shelters and roads in the database, with the default area
configurable via environment variables.

## Features

- **Click analysis** — the core feature: a click (or "Use my location") runs a
  PostGIS risk check and returns in-zone/near-zone/outside status, the risk
  level, distance to the nearest zone, flooded/blocked roads in the search
  radius, and nearby shelters ranked by distance.
- **Shelter recommendation** — nearest verified, open shelter with free
  capacity that is itself outside any flood zone.
- **Live map layers** — flood zones (4 risk levels), shelters (open/full/
  closed, warning ring when inside a zone), roads (open/flooded/blocked/
  at-risk), a 500 m caution band, and community flood reports.
- **Filters** — risk level, shelter type/status/minimum capacity, unverified
  shelters, road status, at-risk roads only.
- **Community input** — suggest a shelter (unverified until reviewed) or
  report flooding from the sidebar.
- **Statistics** — area per risk level, shelter capacity inside/outside zones,
  open capacity, kilometres of road at risk.
- **Multi-area** — eight study areas, each with its own deterministic dataset.
- **Mobile-ready** — the sidebar becomes a bottom sheet under 768 px.
- **Accessible** — keyboard-navigable shelter list, ARIA roles, colour never
  the only signal.

## Architecture

```
PostGIS (geometry + GiST indexes)
        │  raw parameterised SQL, GeoJSON built in the database
        ▼
FastAPI backend (psycopg 3 pool, Pydantic v2 validation)
        │  /api/* JSON endpoints
        ▼
Leaflet 1.9.x frontend (plain HTML/CSS/JS, ES modules, no build step)
```

The application reads **all** spatial data from PostGIS at runtime. No geometry
is hard-coded in the frontend or backend, and no static GeoJSON file is served
to the map — the files in `data/` are seed input for `scripts/load_data.py`
(manual/local seeding) and for the startup auto-seed in `backend/app/seed.py`.

## Repository layout

```
backend/   FastAPI application (routers, schemas, config) + pytest suite
frontend/  Leaflet frontend (HTML, CSS, ES-module JS) served by FastAPI
db/init/   SQL schema, indexes and views (run in filename order)
scripts/   deterministic sample-data generator and DB loader
data/      generated seed data (GeoJSON + areas.json + test points)
docs/      screenshots
```

## Quick start (Docker)

Prerequisites: Docker with the Compose plugin.

```bash
git clone https://github.com/<your-username>/webgis-flood.git
cd webgis-flood
cp .env.example .env        # optional: adjust settings
docker compose up --build
```

Open **http://localhost:8000**. On first start the `db` container runs
`db/init/*.sql` in order and the `api` container runs `scripts/load_data.py`
before serving, so the app comes up with sample data loaded — no manual steps.

Stop with `Ctrl+C`; `docker compose down` removes the containers (the database
volume `pgdata` survives; `docker compose down -v` deletes it).

> The Docker path is provided for cross-platform use but was developed on a
> machine without Docker Desktop, so it is untested end-to-end — the local
> setup below is the verified one. Issues and PRs welcome.

## Local setup (PostgreSQL + PostGIS)

Verified on Windows with PostgreSQL 16 + PostGIS 3.4.

**Windows one-click launcher:** double-click `run.bat` in the project root.
It starts the local PostgreSQL 16 + PostGIS if it is not running, starts the
backend, and opens the browser once the app answers `/api/health`. Close the
window to stop the server. Edit the `PGBIN`/`PGDATA` paths at the top of
`run.bat` to match your install (the defaults expect a portable PostGIS at
`C:\Users\Yaseen\postgres-pg16` on port 5433).

Manual setup:

1. Install PostgreSQL 16 and the PostGIS bundle for PG16
   (e.g. `https://download.osgeo.org/postgis/windows/pg16/archive/postgis-bundle-pg16-3.4.2x64.zip`,
   copy `bin/`, `lib/`, `share/extension/` and `share/contrib/` into your
   PostgreSQL 16 install directory, then restart the service).
2. Create the database and load the schema — the SQL files run in filename
   order:

   ```bash
   psql -U postgres -c "CREATE DATABASE webgis;"
   psql -U postgres -d webgis -f db/init/01_extensions.sql
   psql -U postgres -d webgis -f db/init/02_schema.sql
   psql -U postgres -d webgis -f db/init/03_indexes.sql
   psql -U postgres -d webgis -f db/init/04_views.sql
   ```

3. Install Python dependencies and load the sample data:

   ```bash
   cd backend
   python -m venv .venv
   .venv/Scripts/pip install -r requirements.txt        # Windows
   #   or: .venv/bin/pip install -r requirements.txt    # macOS/Linux
   cd ..
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/webgis \
     python scripts/load_data.py
   ```

   `load_data.py` is idempotent: it truncates `areas`, `flood_zones`,
   `shelters`, `roads` and `flood_reports`, then re-inserts from
   `data/areas.json` and the `data/*.geojson` files.

4. Run the API:

   ```bash
   cd backend
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/webgis \
     .venv/Scripts/uvicorn app.main:app --port 8000
   ```

   Open http://localhost:8000 — FastAPI serves the `frontend/` directory.

> The schema targets PostGIS 3.4 (Docker image `postgis/postgis:16-3.4`). On
> Windows the earliest available PG16 bundle is 3.4.2; every spatial function
> used here behaves identically in both.

## Configuration

Everything is read from environment variables (see `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/webgis` | PostGIS connection string |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `postgres` / `postgres` / `webgis` | used by the compose `db` service |
| `MAP_CENTER_LAT` / `MAP_CENTER_LNG` | `34.006` / `71.974` | initial map centre (Nowshera) |
| `MAP_ZOOM` | `13` | initial zoom |
| `STUDY_AREA_BBOX` | `71.85,33.90,72.10,34.12` | `minLng,minLat,maxLng,maxLat`; `risk-check` and the shelter form reject points outside it |
| `DEFAULT_RADIUS_M` | `3000` | default search radius |
| `CAUTION_RADIUS_M` | `500` | "near a zone" buffer |
| `CORS_ORIGINS` | `http://localhost:8000` | comma-separated allowed origins |

The frontend reads map settings from `GET /api/config` — nothing is hard-coded
in JavaScript. The defaults above describe the default study area (Nowshera);
after the user picks another area in the header dropdown, the map centre, zoom
and default radius come from the `areas` table (the per-area bbox is also the
validation rectangle for `risk-check` and the suggestion forms).

## Data model

All geometry columns use **SRID 4326** (WGS 84), coordinates are **longitude
first**, and every geometry column has a **GiST index**. Distances and buffers
in metres are computed by casting to geography (`geom::geography`).

| Table | Entities | Key columns |
|---|---|---|
| `areas` | Study-area definitions (8 rows) | `slug` (unique), `name`, `province`, `river_name`, `center_lat`/`center_lng`, `zoom`, `min_lng`/`min_lat`/`max_lng`/`max_lat`, `default_radius_m` |
| `flood_zones` | Flood-prone polygons (`MultiPolygon`) | `area`, `name`, `risk_level` (1 low … 4 very high), `return_period_years`, `source`, `geom` |
| `shelters` | Shelter points | `area`, `name`, `shelter_type` (school, hospital, community_center, mosque, government_building, camp, other), `capacity`, `current_occupancy`, `status` (open/full/closed), `contact_phone`, `address`, `is_verified`, `geom` |
| `roads` | Road segments (`LineString`) | `area`, `name`, `road_type` (motorway … track), `status` (open/flooded/blocked), `geom` |
| `flood_reports` | Community flood sightings | `area`, `report_type` (water_level/road_blocked/people_stranded), `severity` (1–3), `description`, `geom` |

Every `/api` endpoint that touches data takes an optional `area=<slug>` query
parameter (default `nowshera`); all four feature tables carry the `area`
column with a plain B-tree index for it.

Views (`db/init/04_views.sql`):

- `shelters_with_risk` — shelters plus `max_risk_level` (highest zone level
  the shelter intersects; `NULL` means safe).
- `roads_with_risk` — same for roads.

**Sample data** (`scripts/generate_sample_data.py`, fixed random seed 42): for
each of the 8 areas the generator builds a river corridor and 12 flood
polygons at risk levels 1–4 with higher-risk zones nested inside lower ones,
32 shelters (including shelters inside flood zones, a full one, a closed one
and unverified ones so every UI state can be demonstrated), and ~170 road
segments with flooded, blocked and at-risk examples — 96 zones, 256 shelters
and 1344 roads in total. Each area uses its own random stream, so regeneration
is reproducible and the Nowshera dataset is stable across regenerations.
`data/test_points.json` contains four named coordinates (inside a level-4
zone, inside a level-1 zone, within 500 m of a zone, far outside) used by the
tests and the demo.

## Spatial SQL under the hood

Every query below is real application SQL (parameterised; `:name` is a bound
parameter).

**Click analysis** — `GET /api/risk-check` (`backend/app/routers/risk.py`):

| Step | Function | One-line explanation |
|---|---|---|
| Build point | `ST_SetSRID(ST_MakePoint(lng, lat), 4326)` | makes a point geometry, longitude first, in SRID 4326 |
| In a zone? | `ST_Intersects(zone.geom, point)` | true when the point lies inside or on the zone polygon |
| Near a zone? | `ST_Buffer(point::geography, 500)::geometry` | draws a 500 m circle around the point (geography cast ⇒ metres) |
| Distance to nearest zone | `ORDER BY zone.geom <-> point` + `ST_Distance(zone.geom::geography, point::geography)` | `<->` is the KNN operator that uses the GiST index to pick candidates; `ST_Distance` on geography returns metres |
| Search area | `ST_Buffer(point::geography, radius_m)::geometry` | the search circle, returned as GeoJSON so the map can draw it |
| Flooded roads in radius | `ST_Intersects(road.geom, buffer)` | counts flooded/blocked roads touching the circle |
| Nearby shelters | `ST_DWithin(shelter.geom::geography, point::geography, radius_m)` | index-backed "within N metres" test; combined with `ST_Distance` for ranking |

**Shelter recommendation** — nearest verified open shelter with free capacity
whose `max_risk_level IS NULL` (never points into a flood zone).

**Layers** — `GET /api/layers/*` (`backend/app/routers/layers.py`): each
FeatureCollection is assembled inside PostGIS with `ST_AsGeoJSON` (geometry →
GeoJSON) and `jsonb_agg` (rows → feature array), capped at 5000 features.
The bbox filter uses `geom && ST_MakeEnvelope(...)` — the `&&` bounding-box
operator is served by the GiST indexes.

**Stats** — `GET /api/stats`: `ST_Area(geom::geography)` for km² per risk
level and `ST_Length(geom::geography)` for km of road at risk.

## API examples

```bash
# Health + PostGIS version
curl http://localhost:8000/api/health

# Frontend configuration
curl http://localhost:8000/api/config

# Study areas (the header dropdown)
curl http://localhost:8000/api/areas

# Flood zones (GeoJSON built in PostGIS)
curl "http://localhost:8000/api/layers/flood-zones"
curl "http://localhost:8000/api/layers/flood-zones?risk_min=3&risk_min=4"
curl "http://localhost:8000/api/layers/flood-zones?buffer_m=500"          # caution band
curl "http://localhost:8000/api/layers/flood-zones?area=lahore"           # another study area

# Shelters (unverified hidden by default)
curl "http://localhost:8000/api/layers/shelters?type=school&status=open&min_capacity=100"
curl "http://localhost:8000/api/layers/shelters?include_unverified=true"

# Roads
curl "http://localhost:8000/api/layers/roads?status=flooded"
curl "http://localhost:8000/api/layers/roads?at_risk=true"
curl "http://localhost:8000/api/layers/flood-reports"

# Click analysis (the core feature)
curl "http://localhost:8000/api/risk-check?lat=34.010068&lng=71.97&radius_m=3000&limit=5"
curl "http://localhost:8000/api/risk-check?lat=31.52&lng=74.358&radius_m=3000&area=lahore"

# Suggest a shelter
curl -X POST http://localhost:8000/api/shelters \
  -H "Content-Type: application/json" \
  -d '{"name":"Government High School Pabbi","shelter_type":"school","capacity":500,
       "contact_phone":"+92 333 1234567","address":"Pabbi, Nowshera","lat":34.02,"lng":71.97}'

# Report flooding
curl -X POST http://localhost:8000/api/flood-reports \
  -H "Content-Type: application/json" \
  -d '{"report_type":"water_level","severity":2,"description":"Kabul River rising",
       "lat":34.0,"lng":71.98}'

# Summary statistics
curl http://localhost:8000/api/stats
curl "http://localhost:8000/api/stats?area=sukkur"
```

Invalid input returns `422` with a clear message (Pydantic validation), e.g.
a radius outside 100–20000 m, a point outside the study area, or an unknown
area slug. SQL errors are logged server-side and returned as a generic `500`
— never leaked to the client.

## Performance

All geometry columns have GiST indexes (`db/init/03_indexes.sql`), and the
distance ordering uses the `<->` KNN operator. `EXPLAIN` for the nearest-zone
subquery of `risk-check` (run against the sample data):

```
QUERY PLAN
------------------------------------------------------------------------------------------------------
 Limit  (cost=0.14..13.37 rows=1 width=40)
   ->  Index Scan using flood_zones_geom_gix on flood_zones z  (cost=0.14..7539.64 rows=570 width=40)
         Order By: (geom <-> '0101000020E6100000AE47E17A14FE5140E17A14AE47014140'::geometry)
```

`EXPLAIN` for the shelter search shows the geography index being used by
`ST_DWithin`:

```
QUERY PLAN
------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 Limit  (cost=1216.19..1216.19 rows=1 width=36)
   ->  Sort  (cost=1216.19..1216.19 rows=1 width=36)
         Sort Key: (round((st_distance((s.geom)::geography, '0101000020E6100000AE47E17A14FE5140E17A14AE47014140'::geography, true))::numeric, 1))
         ->  Bitmap Heap Scan on shelters s  (cost=4.98..1216.18 rows=1 width=36)
               Filter: (is_verified AND st_dwithin((geom)::geography, '0101000020E6100000AE47E17A14FE5140E17A14AE47014140'::geography, '3000'::double precision, true))
               ->  Bitmap Index Scan on shelters_geog_gix  (cost=0.00..4.98 rows=95 width=0)
                     Index Cond: ((geom)::geography && _st_expand('0101000020E6100000AE47E17A14FE5140E17A14AE47014140'::geography, '3000'::double precision))
```

Measured locally on the Nowshera sample (32 shelters, 164 roads, 12 zones):
`/api/risk-check` ≈ 12–29 ms, layer endpoints ≈ 13–22 ms, `/api/stats` ≈
12–17 ms — well under the 500 ms / 1 s targets.

## Tests

Integration tests against a real PostGIS instance (the sample data is reseeded
automatically):

```bash
cd backend
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/webgis \
  .venv/Scripts/python -m pytest
```

- `test_risk.py` — every point in `data/test_points.json` returns its expected
  status (`in_zone`/`near_zone`/`outside`) and risk level; shelters are sorted
  by distance; the recommendation is always open, has capacity and is not in a
  flood zone; invalid inputs return 422.
- `test_layers.py` — valid FeatureCollections, filters change feature counts,
  unverified shelters hidden by default, the 5000-feature cap, `/api/stats`.
- `test_shelters.py` — the suggestion form flow: POST returns 201 with
  `is_verified=false`, the point is hidden by default and appears when
  `include_unverified=true`, invalid payloads return 422.
- `test_areas.py` — the multi-area extension: `/api/areas` lists all 8 areas,
  `area=<slug>` moves layer features into that area's bbox, stats differ per
  area, `risk-check` validates the point against the area's bbox, unknown
  slugs return 422, and submitted shelters/reports land only in their area.

## Deploying on Vercel

The whole app — FastAPI API, Leaflet frontend and PostGIS database — can run
on Vercel's free tier. Vercel auto-detects the FastAPI app from the
`api/index.py` entrypoint and serves it as one serverless function
(`maxDuration: 60` in `vercel.json`); the frontend is served by the same app
through its existing `StaticFiles` mount, so everything stays same-origin and
no frontend code changes are needed. The database is
[Neon](https://neon.com) (Vercel's Postgres partner), which supports PostGIS
via `CREATE EXTENSION postgis`.

Deploy files already in the repo: `api/index.py` (entrypoint shim that puts
`backend/` on `sys.path`), `requirements.txt` (runtime dependencies),
`vercel.json`, `.gitignore`.

**The API seeds itself.** On startup (`backend/app/seed.py`, called from the
app lifespan) the API checks the database and, when it is empty, applies the
`db/init` schema and loads the sample data from `data/` automatically — no SQL
editor, no local `psql`, no `load_data.py` run. The check is idempotent and
guarded by an advisory lock, so concurrent cold starts seed only once and
later starts skip straight past it.

Deploying is three CLI commands (after a one-time `vercel login`):

1. `vercel project add floodanalysis` and
   `vercel link --yes --project floodanalysis` — create and link the project.
2. `vercel integration add neon --billing-plan free_v3 --meta region=sin1 --meta auth=false`
   — installs the Neon integration, creates the database and connects it to
   the project. `DATABASE_URL` (pooled), `DATABASE_URL_UNPOOLED` and the
   `PG*` variables are set on every environment automatically; `db.py`
   detects the `-pooler` host and disables psycopg prepared statements, so no
   `DB_PGBOUNCER` flag is needed.
3. `vercel --prod --yes` — deploy.

Then open `https://<your-app>.vercel.app`. The first hit takes a few extra
seconds: the cold start creates the PostGIS extension, the schema and the
sample data before serving the page. Every later request is fast, and the
map shows all eight study areas immediately. If Neon's free tier
rate-limits, switch `DATABASE_URL` to the unpooled connection string.

## Screenshots

Click analysis with shelter recommendation:

![Click analysis result](docs/screenshot-analysis.png)

Summary statistics panel:

![Stats panel](docs/screenshot-stats.png)

Shelter suggestion and flood report forms:

![Suggest a shelter / report flooding](docs/screenshot-suggest.png)

Mobile layout (360 px wide):

![Mobile layout](docs/screenshot-mobile.png)

## Design decisions

The application follows a fixed functional specification (a course brief).
Where the brief was silent, decisions were made and are logged here:

- `POST /api/flood-reports` lives in `routers/risk.py` (flood sightings are
  risk-domain), keeping the four-router backend layout of the spec.
- `GET /api/layers/flood-reports` was added because reports must be shown as
  a map layer; it returns the newest 5000 reports.
- Multi-select filters use repeatable query params
  (`?risk_min=2&risk_min=3`, `?type=school&type=mosque`).
- Layer responses are capped with `LIMIT 5000` in SQL.
- `risk-check` computes `nearest_zone_distance_m` even when the point is
  inside a zone (0.0 m) so the UI always has a value.
- Sample data is generated deterministically (seed 42) with pure Python
  (no GIS library): polygons are river-centreline offsets with proportional
  jitter so higher-risk zones nest inside lower-risk ones; all four test
  points are verified by the generator before being written.
- Multi-area support (beyond the original single-area spec): eight study
  areas across Pakistan. Each feature table gained an `area` column
  (`nowshera` default), a new `areas` table stores per-area centre/zoom/bbox/
  default radius, every endpoint accepts `area=<slug>`, and the frontend
  header has a dropdown that recentres the map and reloads all layers. The
  original single-area behaviour (Nowshera) is unchanged and remains the
  default.
- "River aqua" visual theme: the frontend chrome (header, tabs, panels,
  forms, popups, legend, Leaflet controls) is styled in a river blue/teal
  palette — dark teal gradient header with a wave divider, gradient accents,
  rounded cards. Pure CSS (`frontend/css/style.css`), no markup or logic
  changes, and the map's data colours (risk levels, shelter/road status) and
  the default OpenStreetMap basemap are unchanged so the GIS semantics stay
  exact.
- Vercel deployment support: `api/index.py` entrypoint shim (Vercel
  auto-detects the FastAPI app from it), `requirements.txt`, `vercel.json`
  (`maxDuration: 60`) and `.gitignore` added. `backend/app/db.py` detects
  Neon's pooled connection string (PgBouncer transaction mode, host contains
  `-pooler`) and disables psycopg prepared statements automatically — no
  `DB_PGBOUNCER` flag needed. Local behaviour is unchanged — 36/36 tests
  green. See the "Deploying on Vercel" section for the full runbook.
- Zero-step database seeding (deployment convenience): on startup the API
  creates the PostGIS extension, applies the `db/init` schema when the
  database has no tables and loads the sample data when the `areas` table is
  empty (`backend/app/seed.py`). Idempotent and advisory-lock-guarded, so a
  fresh Neon database comes up fully loaded with no manual `psql` or
  `load_data.py` steps; manual seeding still works unchanged for local use.

## Roadmap

GeoServer WMS/WFS publishing, admin verification endpoint, DBSCAN heatmap of
flood reports, real OSM/HDX data via `ogr2ogr` (mapped to the schema above),
pgRouting to the recommended shelter, draw-a-polygon analysis tool.
