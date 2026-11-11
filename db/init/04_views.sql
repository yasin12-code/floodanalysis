-- Derived risk: max_risk_level IS NOT NULL means the feature is in or crosses a flood zone.
-- Uses ST_Intersects (geometry vs geometry, 4326) with a correlated subquery per row.

CREATE VIEW shelters_with_risk AS
SELECT s.*, (SELECT MAX(z.risk_level) FROM flood_zones z WHERE ST_Intersects(s.geom, z.geom)) AS max_risk_level
FROM shelters s;

CREATE VIEW roads_with_risk AS
SELECT r.*, (SELECT MAX(z.risk_level) FROM flood_zones z WHERE ST_Intersects(r.geom, z.geom)) AS max_risk_level
FROM roads r;
