-- TrafficFlow AI - PostgreSQL schema
-- Privacy note: only anonymous traffic metadata is stored. No frames, no plates, no faces.

CREATE TABLE IF NOT EXISTS areas (
    id               SERIAL PRIMARY KEY,
    name             VARCHAR(120) NOT NULL UNIQUE,
    description      TEXT,
    latitude         DOUBLE PRECISION,
    longitude        DOUBLE PRECISION,
    hourly_capacity  INTEGER NOT NULL DEFAULT 1200 CHECK (hourly_capacity > 0),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cameras (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(120) NOT NULL,
    location     VARCHAR(255),
    area_id      INTEGER REFERENCES areas(id) ON DELETE SET NULL,
    source_type  VARCHAR(20) NOT NULL DEFAULT 'video_file'
                 CHECK (source_type IN ('video_file', 'webcam', 'rtsp')),
    source_url   VARCHAR(500) NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'offline'
                 CHECK (status IN ('offline', 'online', 'processing', 'error', 'inactive')),
    latitude     DOUBLE PRECISION,
    longitude    DOUBLE PRECISION,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    last_error   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_cameras_area ON cameras(area_id);

-- Coordinates are normalised (0..1) so they survive any processing resolution.
CREATE TABLE IF NOT EXISTS counting_lines (
    id          SERIAL PRIMARY KEY,
    camera_id   INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    name        VARCHAR(120) NOT NULL,
    x1          DOUBLE PRECISION NOT NULL CHECK (x1 BETWEEN 0 AND 1),
    y1          DOUBLE PRECISION NOT NULL CHECK (y1 BETWEEN 0 AND 1),
    x2          DOUBLE PRECISION NOT NULL CHECK (x2 BETWEEN 0 AND 1),
    y2          DOUBLE PRECISION NOT NULL CHECK (y2 BETWEEN 0 AND 1),
    -- Label used when a vehicle moves from the line's right-hand side to its left-hand side
    -- (see ai/counter.py for the exact geometric convention) and vice versa.
    direction_ab VARCHAR(40) NOT NULL DEFAULT 'northbound',
    direction_ba VARCHAR(40) NOT NULL DEFAULT 'southbound',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_lines_camera ON counting_lines(camera_id);

-- polygon: JSON array of [x, y] pairs, normalised 0..1
CREATE TABLE IF NOT EXISTS zones (
    id          SERIAL PRIMARY KEY,
    camera_id   INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    name        VARCHAR(120) NOT NULL,
    polygon     JSONB NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_zones_camera ON zones(camera_id);

CREATE TABLE IF NOT EXISTS vehicle_events (
    id            BIGSERIAL PRIMARY KEY,
    camera_id     INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    area_id       INTEGER REFERENCES areas(id) ON DELETE SET NULL,
    line_id       INTEGER REFERENCES counting_lines(id) ON DELETE SET NULL,
    track_id      INTEGER NOT NULL,
    vehicle_type  VARCHAR(30) NOT NULL,
    direction     VARCHAR(40) NOT NULL,
    confidence    REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT now(),
    frame_number  INTEGER,
    speed_kmh     REAL,              -- optional, NULL unless a calibrated estimator is added
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_events_timestamp ON vehicle_events(timestamp);
CREATE INDEX IF NOT EXISTS ix_events_camera    ON vehicle_events(camera_id);
CREATE INDEX IF NOT EXISTS ix_events_area      ON vehicle_events(area_id);
CREATE INDEX IF NOT EXISTS ix_events_type      ON vehicle_events(vehicle_type);
CREATE INDEX IF NOT EXISTS ix_events_cam_ts    ON vehicle_events(camera_id, timestamp);

CREATE TABLE IF NOT EXISTS zone_events (
    id            BIGSERIAL PRIMARY KEY,
    zone_id       INTEGER NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    camera_id     INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    area_id       INTEGER REFERENCES areas(id) ON DELETE SET NULL,
    track_id      INTEGER NOT NULL,
    vehicle_type  VARCHAR(30) NOT NULL,
    event_type    VARCHAR(10) NOT NULL CHECK (event_type IN ('enter', 'exit')),
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT now(),
    frame_number  INTEGER
);
CREATE INDEX IF NOT EXISTS ix_zone_events_zone_ts ON zone_events(zone_id, timestamp);
CREATE INDEX IF NOT EXISTS ix_zone_events_camera  ON zone_events(camera_id);

-- Hourly roll-up maintained in the same transaction as each vehicle event.
-- bucket_start is the start of the hour in the application timezone (APP_TIMEZONE).
CREATE TABLE IF NOT EXISTS traffic_summaries (
    id            BIGSERIAL PRIMARY KEY,
    camera_id     INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    area_id       INTEGER REFERENCES areas(id) ON DELETE SET NULL,
    bucket_start  TIMESTAMPTZ NOT NULL,
    vehicle_type  VARCHAR(30) NOT NULL,
    direction     VARCHAR(40) NOT NULL,
    vehicle_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE (camera_id, bucket_start, vehicle_type, direction)
);
CREATE INDEX IF NOT EXISTS ix_summ_bucket ON traffic_summaries(bucket_start);
CREATE INDEX IF NOT EXISTS ix_summ_area   ON traffic_summaries(area_id);
CREATE INDEX IF NOT EXISTS ix_summ_type   ON traffic_summaries(vehicle_type);
