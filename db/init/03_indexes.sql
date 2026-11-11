-- GiST indexes on every geometry column: accelerate && (bbox), ST_Intersects, ST_DWithin
-- and the <-> distance ordering operator.
CREATE INDEX flood_zones_geom_gix   ON flood_zones   USING GIST (geom);
CREATE INDEX shelters_geom_gix      ON shelters      USING GIST (geom);
CREATE INDEX roads_geom_gix         ON roads         USING GIST (geom);
CREATE INDEX flood_reports_geom_gix ON flood_reports USING GIST (geom);
-- Geography cast index: ST_DWithin/ST_Distance on geom::geography use this index.
CREATE INDEX shelters_geog_gix      ON shelters      USING GIST ((geom::geography));
-- Btree indexes on the area column: every endpoint filters by area first.
CREATE INDEX flood_zones_area_idx   ON flood_zones   (area);
CREATE INDEX shelters_area_idx      ON shelters      (area);
CREATE INDEX roads_area_idx         ON roads         (area);
CREATE INDEX flood_reports_area_idx ON flood_reports (area);
