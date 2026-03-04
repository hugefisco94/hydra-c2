-- HYDRA-C2 Enhanced Seed: 10 additional actors with real ICAO codes from plane-alert-db
-- Source: plane-alert-mil.csv (8,710 verified military aircraft records)
-- Run AFTER seed.sql (extends the 15-actor base scenario to 25 actors)

INSERT INTO pli_history (actor_id, callsign, team, geom, speed_mps, course_deg, source, confidence, metadata, recorded_at) VALUES

-- ── FRIENDLY (Blue Force) ─────────────────────────────────────────────────
-- ROK Navy P-8A Poseidon — Maritime patrol/ASW (real ICAO: 71F010, Reg: 230925)
('a1000010-0000-0000-0000-000000000010', 'POSEIDON-1', 'FRIENDLY',
 ST_SetSRID(ST_MakePoint(129.45, 35.85, 7500.0), 4326),
 180.0, 225.0, 'ADS-B', 0.97,
 '{"actor_type":"AIRCRAFT","affiliation":"FRIENDLY","aircraft_type":"Boeing P-8A Poseidon","icao_hex":"71F010","registration":"230925","operator":"Republic of Korea Navy","mission":"Maritime Patrol / ASW","icao_type":"P8","tags":["One Ping Only Vasily","Anti-Submarine Warfare"],"first_seen":"2026-03-04T08:00:00+00:00"}'::jsonb,
 NOW() - interval '4 minutes'),

-- ROKAF KC-330 Cygnus — Aerial refueling tanker (real ICAO: 71F881, Reg: 19-002)
('a1000011-0000-0000-0000-000000000011', 'CYGNUS-9', 'FRIENDLY',
 ST_SetSRID(ST_MakePoint(127.50, 36.20, 9000.0), 4326),
 220.0, 270.0, 'ADS-B', 0.96,
 '{"actor_type":"AIRCRAFT","affiliation":"FRIENDLY","aircraft_type":"Airbus KC-330 Cygnus","icao_hex":"71F881","registration":"19-002","operator":"Republic of Korea Air Force","mission":"Air-to-Air Refueling","icao_type":"A332","tags":["Refuel","Air2Air","The Highest Power Defending Korea"],"first_seen":"2026-03-04T06:30:00+00:00"}'::jsonb,
 NOW() - interval '6 minutes'),

-- USAF RC-135V Rivet Joint — SIGINT reconnaissance (real ICAO: AE01C3, Reg: 64-14848)
('a1000012-0000-0000-0000-000000000012', 'RIVET-55', 'FRIENDLY',
 ST_SetSRID(ST_MakePoint(127.80, 37.50, 10500.0), 4326),
 200.0, 0.0, 'ADS-B', 0.93,
 '{"actor_type":"AIRCRAFT","affiliation":"FRIENDLY","aircraft_type":"Boeing RC-135V Rivet Joint","icao_hex":"AE01C3","registration":"64-14848","operator":"USAF 55th Wing","mission":"SIGINT/ELINT","icao_type":"R135","tags":["Eye In The Sky","SIGINT","Rivet Joint"],"orbit_pattern":"racetrack","first_seen":"2026-03-04T02:00:00+00:00"}'::jsonb,
 NOW() - interval '2 minutes'),

-- ROK Army — Ground-based border surveillance radar station
('a1000013-0000-0000-0000-000000000013', 'SENTINEL-6', 'FRIENDLY',
 ST_SetSRID(ST_MakePoint(127.10, 37.95, 350.0), 4326),
 0.0, 0.0, 'ATAK', 0.99,
 '{"actor_type":"SENSOR","affiliation":"FRIENDLY","sensor_type":"AN/TPS-80 G/ATOR","operator":"ROK Army 1st Corps","coverage_km":150,"sector_deg":[315,45],"mission":"Border Surveillance","first_seen":"2026-03-01T00:00:00+00:00"}'::jsonb,
 NOW() - interval '1 minute'),

-- JASDF RC-2 — Japanese ELINT/EW (real ICAO: 87CC10, Reg: 18-1202, allied ISR)
('a1000014-0000-0000-0000-000000000014', 'OVERCAST-2', 'FRIENDLY',
 ST_SetSRID(ST_MakePoint(130.50, 35.50, 8000.0), 4326),
 190.0, 315.0, 'ADS-B', 0.91,
 '{"actor_type":"AIRCRAFT","affiliation":"FRIENDLY","aircraft_type":"Kawasaki RC-2","icao_hex":"87CC10","registration":"18-1202","operator":"Japan Air Self-Defense Force","mission":"ELINT/Electronic Warfare","icao_type":"KC2","tags":["ELINT","Electronic Warfare","Ready Anytime"],"first_seen":"2026-03-04T05:00:00+00:00"}'::jsonb,
 NOW() - interval '7 minutes'),

-- ── HOSTILE (Red Force) ───────────────────────────────────────────────────
-- Russian Tu-214R SIGINT (real ICAO: 14FBFF, Reg: RF-64511) — provocative ISR flight
('a1000015-0000-0000-0000-000000000015', 'FOXHOUND-3', 'HOSTILE',
 ST_SetSRID(ST_MakePoint(131.20, 40.10, 11000.0), 4326),
 250.0, 180.0, 'ADS-B', 0.88,
 '{"actor_type":"AIRCRAFT","affiliation":"HOSTILE","aircraft_type":"Tupolev Tu-214R","icao_hex":"14FBFF","registration":"RF-64511","operator":"Russian Air Force","mission":"SIGINT/ELINT","icao_type":"T204","threat_level":"HIGH","tags":["SIGINT","ELINT","No Codename"],"first_seen":"2026-03-04T03:00:00+00:00"}'::jsonb,
 NOW() - interval '9 minutes'),

-- DPRK submarine — subsurface contact via sonobuoy
('a1000016-0000-0000-0000-000000000016', 'TORPEDO-7', 'HOSTILE',
 ST_SetSRID(ST_MakePoint(125.80, 37.20, -50.0), 4326),
 4.0, 150.0, 'SONOBUOY', 0.42,
 '{"actor_type":"SUBMARINE","affiliation":"HOSTILE","assessed_type":"Sang-O class coastal submarine","threat_level":"CRITICAL","detection_method":"passive_sonar","bearing_error_deg":8,"tonals_hz":[50,120,440],"first_seen":"2026-03-04T09:00:00+00:00"}'::jsonb,
 NOW() - interval '14 minutes'),

-- DPRK massed artillery — MLRS cluster near Kaesong
('a1000017-0000-0000-0000-000000000017', 'LIGHTNING-4', 'HOSTILE',
 ST_SetSRID(ST_MakePoint(126.60, 37.97, 180.0), 4326),
 0.0, 0.0, 'SDR', 0.55,
 '{"actor_type":"UNIT","affiliation":"HOSTILE","assessed_type":"240mm MLRS Battery","threat_level":"HIGH","estimated_tubes":12,"range_km":60,"target_area":"Seoul Metropolitan","emitter":"counter-battery_radar","first_seen":"2026-03-04T01:30:00+00:00"}'::jsonb,
 NOW() - interval '16 minutes'),

-- ── NEUTRAL ───────────────────────────────────────────────────────────────
-- Asiana Airlines commercial flight (based on ICAO prefix 71xxxx for Korean registered aircraft)
('a1000018-0000-0000-0000-000000000018', 'OZ-204', 'NEUTRAL',
 ST_SetSRID(ST_MakePoint(128.60, 37.40, 10500.0), 4326),
 235.0, 45.0, 'ADS-B', 0.99,
 '{"actor_type":"AIRCRAFT","affiliation":"NEUTRAL","aircraft_type":"Airbus A350-900","airline":"Asiana Airlines","flight":"OZ204","icao_type":"A359","route":"ICN-FRA","first_seen":"2026-03-04T09:30:00+00:00"}'::jsonb,
 NOW() - interval '3 minutes'),

-- ── UNKNOWN ───────────────────────────────────────────────────────────────
-- Unidentified high-altitude slow mover — possible surveillance balloon
('a1000019-0000-0000-0000-000000000019', 'DARKSTAR-1', 'UNKNOWN',
 ST_SetSRID(ST_MakePoint(126.40, 37.60, 18000.0), 4326),
 8.0, 90.0, 'KRAKEN', 0.25,
 '{"actor_type":"UNKNOWN","affiliation":"UNKNOWN","assessed_type":"High-Altitude Balloon / Aerostat","altitude_ft":59000,"radar_rcs_dbsm":-15.0,"ir_signature":"MINIMAL","wind_vector_kt":{"speed":45,"direction":270},"first_seen":"2026-03-04T10:00:00+00:00"}'::jsonb,
 NOW() - interval '11 minutes');
