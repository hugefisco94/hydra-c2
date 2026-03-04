-- =============================================================================
-- HYDRA-C2 PostgreSQL/PostGIS Schema
-- Layer 4: Persistence Layer — Spatial Data Store
-- =============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- Fuzzy text search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- UUID generation

-- =============================================================================
-- PLI (Position Location Information) History
-- =============================================================================
CREATE TABLE IF NOT EXISTS pli_history (
    id          BIGSERIAL PRIMARY KEY,
    actor_id    UUID NOT NULL DEFAULT uuid_generate_v4(),
    callsign    VARCHAR(64) NOT NULL,
    team        VARCHAR(32),
    geom        GEOMETRY(PointZ, 4326) NOT NULL,  -- WGS84 3D
    speed_mps   REAL,
    course_deg  REAL,
    battery_pct SMALLINT,
    source      VARCHAR(32) DEFAULT 'ATAK',       -- ATAK | MESH | SDR | MANUAL
    confidence  REAL DEFAULT 0.5,
    metadata    JSONB DEFAULT '{}',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pli_geom ON pli_history USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_pli_time ON pli_history(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_pli_callsign ON pli_history(callsign);
CREATE INDEX IF NOT EXISTS idx_pli_actor_id ON pli_history(actor_id);

-- =============================================================================
-- SDR Detection Events (Layer 0 → Layer 4)
-- =============================================================================
CREATE TABLE IF NOT EXISTS sdr_detections (
    id          BIGSERIAL PRIMARY KEY,
    detector    VARCHAR(32) NOT NULL,              -- KRAKEN | RTLSDR | HACKRF
    det_type    VARCHAR(32) NOT NULL,              -- RDF | ADSB | AIS | SPECTRUM
    freq_mhz    DOUBLE PRECISION,
    bearing_deg REAL,                              -- KrakenSDR DoA (MUSIC algorithm)
    power_dbm   REAL,
    geom        GEOMETRY(Point, 4326),             -- Detection location
    target_geom GEOMETRY(Point, 4326),             -- Estimated source location
    metadata    JSONB DEFAULT '{}',
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sdr_geom ON sdr_detections USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_sdr_target ON sdr_detections USING GIST(target_geom);
CREATE INDEX IF NOT EXISTS idx_sdr_type ON sdr_detections(det_type);
CREATE INDEX IF NOT EXISTS idx_sdr_freq ON sdr_detections(freq_mhz);
CREATE INDEX IF NOT EXISTS idx_sdr_time ON sdr_detections(detected_at DESC);

-- =============================================================================
-- ADS-B Aircraft Tracks
-- =============================================================================
CREATE TABLE IF NOT EXISTS adsb_tracks (
    id          BIGSERIAL PRIMARY KEY,
    icao_hex    VARCHAR(6) NOT NULL,
    callsign    VARCHAR(8),
    geom        GEOMETRY(PointZ, 4326) NOT NULL,
    speed_kts   REAL,
    heading_deg REAL,
    squawk      VARCHAR(4),
    on_ground   BOOLEAN DEFAULT FALSE,
    metadata    JSONB DEFAULT '{}',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_adsb_geom ON adsb_tracks USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_adsb_icao ON adsb_tracks(icao_hex);
CREATE INDEX IF NOT EXISTS idx_adsb_time ON adsb_tracks(recorded_at DESC);

-- =============================================================================
-- AIS Vessel Tracks
-- =============================================================================
CREATE TABLE IF NOT EXISTS ais_tracks (
    id          BIGSERIAL PRIMARY KEY,
    mmsi        VARCHAR(9) NOT NULL,
    vessel_name VARCHAR(64),
    geom        GEOMETRY(Point, 4326) NOT NULL,
    sog_kts     REAL,                              -- Speed over ground
    cog_deg     REAL,                              -- Course over ground
    heading_deg REAL,
    nav_status  SMALLINT,
    vessel_type SMALLINT,
    metadata    JSONB DEFAULT '{}',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ais_geom ON ais_tracks USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_ais_mmsi ON ais_tracks(mmsi);

-- =============================================================================
-- Geofences
-- =============================================================================
CREATE TABLE IF NOT EXISTS geofences (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(128) NOT NULL,
    fence_type  VARCHAR(32) DEFAULT 'ALERT',       -- ALERT | RESTRICT | MONITOR
    geom        GEOMETRY(Polygon, 4326) NOT NULL,
    active      BOOLEAN DEFAULT TRUE,
    created_by  VARCHAR(64),
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fence_geom ON geofences USING GIST(geom);

-- =============================================================================
-- Geofence Alerts
-- =============================================================================
CREATE TABLE IF NOT EXISTS geofence_alerts (
    id          BIGSERIAL PRIMARY KEY,
    pli_id      BIGINT REFERENCES pli_history(id),
    fence_id    UUID REFERENCES geofences(id),
    actor_id    UUID,
    callsign    VARCHAR(64),
    breach_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged BOOLEAN DEFAULT FALSE
);

-- =============================================================================
-- Geofence Breach Trigger
-- =============================================================================
CREATE OR REPLACE FUNCTION check_geofence_breach()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO geofence_alerts (pli_id, fence_id, actor_id, callsign, breach_at)
    SELECT NEW.id, g.id, NEW.actor_id, NEW.callsign, NOW()
    FROM geofences g
    WHERE g.active AND ST_Intersects(NEW.geom, g.geom);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_geofence_check ON pli_history;
CREATE TRIGGER trg_geofence_check
AFTER INSERT ON pli_history
FOR EACH ROW EXECUTE FUNCTION check_geofence_breach();

-- =============================================================================
-- Mission Areas & Search Grids
-- =============================================================================
CREATE TABLE IF NOT EXISTS mission_areas (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(128) NOT NULL,
    area_type   VARCHAR(32) DEFAULT 'AO',          -- AO | OBJ | NAI | TAI | SEARCH
    geom        GEOMETRY(Polygon, 4326) NOT NULL,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mission_geom ON mission_areas USING GIST(geom);

-- =============================================================================
-- Audit Log (Cross-cutting Security)
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     VARCHAR(64),
    action      VARCHAR(64) NOT NULL,
    resource    VARCHAR(128),
    details     JSONB DEFAULT '{}',
    ip_address  INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
