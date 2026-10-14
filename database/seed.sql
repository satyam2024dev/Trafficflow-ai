-- Seed: structural data only (areas, cameras, counting lines, zones). NO traffic events are seeded;
-- all statistics come from real video processing.
-- Coordinates are placeholders - edit them in the UI (Areas / Cameras pages) to match your city.
INSERT INTO areas (name, description, latitude, longitude, hourly_capacity) VALUES
  ('Area A', 'Main arterial road',       12.9716, 77.5946, 1200),
  ('Area B', 'Commercial junction',      12.9352, 77.6245, 900),
  ('Area C', 'Residential connector',    12.9784, 77.6408, 600)
ON CONFLICT (name) DO NOTHING;

INSERT INTO cameras (name, location, area_id, source_type, source_url, latitude, longitude)
SELECT 'Demo Camera 1', 'Demo junction (video file)', a.id, 'video_file', 'demo.mp4', 12.9716, 77.5946
FROM areas a WHERE a.name = 'Area A'
AND NOT EXISTS (SELECT 1 FROM cameras WHERE name = 'Demo Camera 1');

INSERT INTO counting_lines (camera_id, name, x1, y1, x2, y2, direction_ab, direction_ba)
SELECT c.id, 'Main line', 0.05, 0.60, 0.95, 0.60, 'northbound', 'southbound'
FROM cameras c WHERE c.name = 'Demo Camera 1'
AND NOT EXISTS (SELECT 1 FROM counting_lines l WHERE l.camera_id = c.id);

INSERT INTO zones (camera_id, name, polygon)
SELECT c.id, 'Monitored zone', '[[0.05,0.45],[0.95,0.45],[0.95,0.85],[0.05,0.85]]'::jsonb
FROM cameras c WHERE c.name = 'Demo Camera 1'
AND NOT EXISTS (SELECT 1 FROM zones z WHERE z.camera_id = c.id);
