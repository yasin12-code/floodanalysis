-- All geometries use SRID 4326 (WGS 84), coordinates are longitude first (ST_MakePoint(lng, lat)).
-- Distances/buffers in metres are computed by casting to geography (geom::geography).

-- Study areas: each city/corridor is an independent map context. Every spatial
-- table carries an `area` slug; layer/risk/stats endpoints default to 'nowshera'
-- (the PRD demo area) so the original behaviour is unchanged.
CREATE TABLE areas (
  id SERIAL PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  province TEXT,
  river_name TEXT,
  center_lng DOUBLE PRECISION NOT NULL,
  center_lat DOUBLE PRECISION NOT NULL,
  zoom SMALLINT NOT NULL DEFAULT 13,
  min_lng DOUBLE PRECISION NOT NULL,
  min_lat DOUBLE PRECISION NOT NULL,
  max_lng DOUBLE PRECISION NOT NULL,
  max_lat DOUBLE PRECISION NOT NULL,
  default_radius_m INT NOT NULL DEFAULT 3000
);

CREATE TABLE flood_zones (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  area TEXT NOT NULL DEFAULT 'nowshera',
  risk_level SMALLINT NOT NULL CHECK (risk_level BETWEEN 1 AND 4), -- 1 low, 2 medium, 3 high, 4 very high
  return_period_years INT,
  source TEXT,
  geom GEOMETRY(MultiPolygon, 4326) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE shelters (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  area TEXT NOT NULL DEFAULT 'nowshera',
  shelter_type TEXT NOT NULL CHECK (shelter_type IN ('school','hospital','community_center','mosque','government_building','camp','other')),
  capacity INT NOT NULL CHECK (capacity >= 0),
  current_occupancy INT NOT NULL DEFAULT 0 CHECK (current_occupancy >= 0),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','full','closed')),
  contact_phone TEXT,
  address TEXT,
  is_verified BOOLEAN NOT NULL DEFAULT FALSE,
  geom GEOMETRY(Point, 4326) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE roads (
  id SERIAL PRIMARY KEY,
  name TEXT,
  area TEXT NOT NULL DEFAULT 'nowshera',
  road_type TEXT NOT NULL CHECK (road_type IN ('motorway','trunk','primary','secondary','tertiary','residential','track')),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','flooded','blocked')),
  geom GEOMETRY(LineString, 4326) NOT NULL
);

-- P1: community flood sightings (filled via POST /api/flood-reports)
CREATE TABLE flood_reports (
  id SERIAL PRIMARY KEY,
  report_type TEXT NOT NULL CHECK (report_type IN ('water_level','road_blocked','people_stranded')),
  severity SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 3),
  description TEXT,
  area TEXT NOT NULL DEFAULT 'nowshera',
  geom GEOMETRY(Point, 4326) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
