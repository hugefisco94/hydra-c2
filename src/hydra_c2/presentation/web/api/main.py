"""HYDRA-C2 FastAPI Application — Layer 6 REST/WebSocket API.

Provides:
- CoT event ingestion endpoint (TAK Server webhook)
- Actor/Event CRUD operations
- Geofence management
- Real-time WebSocket feed for live COP updates
- SDR data ingestion endpoint
- Graph query proxy (Neo4j Cypher)
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import UUID

import structlog
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from hydra_c2.config import Settings, get_settings
from hydra_c2.container import Container
from hydra_c2.domain.entities.actor import GeoPosition

logger = structlog.get_logger()

# --- Application state ---
_container: Container | None = None


def get_container() -> Container:
    """Get the initialized DI container."""
    assert _container is not None, "Application not initialized"
    return _container


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — initialize and teardown resources."""
    global _container
    settings = get_settings()
    logger.info("hydra_c2_starting", version=settings.version)

    _container = Container(settings=settings)
    try:
        await _container.startup()
    except Exception as exc:
        logger.error("container_startup_failed", error=str(exc))
        # Still yield so health check can report degraded status
        _container = None

    yield

    if _container is not None:
        await _container.shutdown()
    logger.info("hydra_c2_shutting_down")


app = FastAPI(
    title="HYDRA-C2 API",
    description="Hybrid Universal Dynamic Reconnaissance Architecture — Multi-Domain C2 System",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Health & Status
# =============================================================================


@app.get("/health")
async def health_check() -> dict:
    """System health check endpoint."""
    infra_ok = _container is not None
    return {
        "status": "operational" if infra_ok else "degraded",
        "system": "HYDRA-C2",
        "version": "0.1.0",
        "infrastructure": "connected" if infra_ok else "disconnected",
        "layers": {
            "L0_physical_rf": "pending",
            "L1_edge_computing": "pending",
            "L2_mesh_transport": "pending",
            "L3_data_ingestion": "connected" if infra_ok else "pending",
            "L4_persistence": "connected" if infra_ok else "pending",
            "L5_analytics": "pending",
            "L6_visualization": "operational",
        },
    }


# =============================================================================
# CoT Ingestion (Layer 3)
# =============================================================================


@app.post("/api/v1/cot/ingest")
async def ingest_cot(cot_xml: str = Body(..., media_type="application/xml")) -> dict:
    """Ingest Cursor on Target XML event from TAK Server.

    TAK Server sends CoT events here via webhook/REST.
    """
    container = get_container()
    use_case = container.ingest_cot_use_case()
    result = await use_case.execute(cot_xml)

    if not result.success:
        raise HTTPException(status_code=422, detail=result.error or "CoT ingestion failed")

    return {
        "status": "ingested",
        "actor_id": str(result.actor_id) if result.actor_id else None,
        "event_id": str(result.event_id) if result.event_id else None,
        "callsign": result.callsign,
        "event_type": result.event_type,
    }


# =============================================================================
# Actor Queries (Layer 4 + Layer 5)
# =============================================================================


# --- Frontend-compatible response helpers ---

ACTOR_TYPE_TO_DOMAIN = {
    'PERSON': 'LAND', 'VEHICLE': 'LAND', 'UNIT': 'LAND', 'EQUIPMENT': 'LAND',
    'AIRCRAFT': 'AIR', 'UAV': 'AIR',
    'VESSEL': 'SEA',
    'TRANSMISSION_SOURCE': 'CYBER',
    'UNKNOWN': 'LAND',
}

AFFILIATION_MAP = {
    'FRIENDLY': 'FRIEND', 'HOSTILE': 'HOSTILE',
    'NEUTRAL': 'NEUTRAL', 'UNKNOWN': 'UNKNOWN',
}


def _actor_to_frontend(a) -> dict:
    return {
        'id': str(a.id),
        'name': a.callsign,
        'sidc': a.mil_std_2525b_sidc,
        'affiliation': AFFILIATION_MAP.get(a.affiliation.value, 'UNKNOWN'),
        'domain': ACTOR_TYPE_TO_DOMAIN.get(a.actor_type.value, 'LAND'),
        'position': {
            'latitude': a.position.latitude,
            'longitude': a.position.longitude,
            'altitude': a.position.altitude_m,
        } if a.position else None,
        'last_seen': a.last_seen.isoformat(),
        'source': a.source,
        'metadata': a.metadata,
    }


@app.get('/api/v1/actors')
async def list_actors(
    lat: float | None = Query(None, description='Center latitude for spatial query'),
    lon: float | None = Query(None, description='Center longitude for spatial query'),
    radius_m: float = Query(10000, description='Search radius in meters'),
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    """List actors, optionally filtered by spatial proximity."""
    container = get_container()

    if lat is not None and lon is not None:
        center = GeoPosition(latitude=lat, longitude=lon)
        actors = await container.actor_repo.find_within_radius(center, radius_m)
    else:
        actors = await container.actor_repo.find_recent(limit)

    return {
        'actors': [_actor_to_frontend(a) for a in actors],
        'total': len(actors),
    }


# =============================================================================
# Graph Queries (Neo4j — Layer 4)
# =============================================================================


@app.get("/api/v1/actors/{actor_id}/network")
async def get_actor_network(actor_id: str, depth: int = Query(3, ge=1, le=10)) -> dict:
    """Get relationship network for an actor (Neo4j graph traversal)."""
    container = get_container()

    try:
        actor_uuid = UUID(actor_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid actor_id: {actor_id}")

    connected = await container.actor_repo.find_network(actor_uuid, max_depth=depth)

    return {
        "actor_id": actor_id,
        "depth": depth,
        "network": [
            {
                "id": str(a.id),
                "callsign": a.callsign,
                "type": a.actor_type.value,
                "affiliation": a.affiliation.value,
            }
            for a in connected
        ],
        "total": len(connected),
    }


# =============================================================================
# SDR Detections (Layer 0 → Layer 4)
# =============================================================================


@app.get("/api/v1/sdr/detections")
async def list_sdr_detections(
    det_type: str | None = Query(None),
    freq_mhz: float | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    """List SDR detection events."""
    container = get_container()

    if freq_mhz is not None:
        transmissions = await container.transmission_repo.find_by_frequency(freq_mhz)
    else:
        transmissions = await container.transmission_repo.find_recent(limit)

    return {
        "detections": [
            {
                "id": str(t.id),
                "frequency_mhz": t.frequency_mhz,
                "power_dbm": t.power_dbm,
                "modulation": t.modulation,
                "bearing_deg": t.bearing_deg,
                "source_sdr": t.source_sdr,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in transmissions
        ],
        "total": len(transmissions),
    }


# =============================================================================
# Geofence Management (Layer 4)
# =============================================================================


@app.post("/api/v1/geofences")
async def create_geofence(
    name: str = Query(...),
    polygon_wkt: str = Body(...),
    fence_type: str = Query("ALERT"),
) -> dict:
    """Create a new geofence polygon."""
    container = get_container()
    fence_id = await container.geofence_repo.create_geofence(name, polygon_wkt, fence_type)

    return {
        "status": "created",
        "geofence_id": str(fence_id),
        "name": name,
        "fence_type": fence_type,
    }


@app.post("/api/v1/geofences/check")
async def check_geofence(
    lat: float = Query(...),
    lon: float = Query(...),
) -> dict:
    """Check if a position breaches any active geofences."""
    container = get_container()
    position = GeoPosition(latitude=lat, longitude=lon)
    breaches = await container.geofence_repo.check_breach(position)

    return {
        "position": {"lat": lat, "lon": lon},
        "breached": len(breaches) > 0,
        "geofences": breaches,
    }


# =============================================================================
# Threat Assessment (Layer 5 — Panopticon-derived patterns)
# =============================================================================


# Key reference locations for threat scoring
_CRITICAL_LOCATIONS = {
    'SEOUL': (37.5665, 126.9780),
    'PYONGYANG': (39.0392, 125.7625),
    'BUSAN': (35.1796, 129.0756),
    'DMZ_CENTER': (37.95, 126.85),
    'NLL_WEST': (37.70, 124.80),
    'OSAN_AB': (37.0901, 127.0297),  # US Air Base
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km (Panopticon utils.py pattern)."""
    R = 6371.0
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _compute_threat_score(actor_data: dict) -> dict:
    """Compute composite threat score using Panopticon engagement scoring pattern.

    Score factors (Panopticon weaponEngagement.py):
    - Affiliation weight: HOSTILE=1.0, UNKNOWN=0.5, NEUTRAL=0.1, FRIEND=0.0
    - Proximity to critical assets: closer = higher threat
    - Metadata threat_level: CRITICAL=1.0, HIGH=0.8, MEDIUM=0.5, LOW=0.2
    - Actor type weight: SUBMARINE=1.0, VEHICLE(TEL)=0.95, AIRCRAFT=0.8, UNIT=0.6
    """
    AFFILIATION_WEIGHTS = {'HOSTILE': 1.0, 'UNKNOWN': 0.5, 'NEUTRAL': 0.1, 'FRIEND': 0.0, 'FRIENDLY': 0.0}
    THREAT_LEVEL_MAP = {'CRITICAL': 1.0, 'HIGH': 0.8, 'MEDIUM': 0.5, 'LOW': 0.2}
    TYPE_WEIGHTS = {
        'SUBMARINE': 1.0, 'VEHICLE': 0.85, 'AIRCRAFT': 0.8,
        'UNIT': 0.6, 'VESSEL': 0.7, 'UAV': 0.65,
        'TRANSMISSION_SOURCE': 0.4, 'SENSOR': 0.2, 'PERSON': 0.3, 'UNKNOWN': 0.5,
    }

    affiliation = actor_data.get('affiliation', 'UNKNOWN')
    aff_score = AFFILIATION_WEIGHTS.get(affiliation, 0.5)

    meta = actor_data.get('metadata', {})
    threat_lvl = meta.get('threat_level', meta.get('priority', 'LOW'))
    threat_score = THREAT_LEVEL_MAP.get(threat_lvl.upper() if isinstance(threat_lvl, str) else 'LOW', 0.2)

    actor_type = meta.get('actor_type', 'UNKNOWN')
    # TEL gets max vehicle score
    if 'TEL' in meta.get('assessed_type', ''):
        type_score = 0.95
    else:
        type_score = TYPE_WEIGHTS.get(actor_type, 0.5)

    # Proximity to Seoul (most critical)
    pos = actor_data.get('position', {})
    lat = pos.get('latitude', 37.5)
    lon = pos.get('longitude', 127.0)
    dist_seoul = _haversine_km(lat, lon, *_CRITICAL_LOCATIONS['SEOUL'])
    # Normalize: 0km=1.0, 200km=0.0
    proximity_score = max(0.0, 1.0 - dist_seoul / 200.0)

    # Composite (Panopticon lethality formula adapted)
    composite = (
        aff_score * 0.30
        + threat_score * 0.25
        + type_score * 0.20
        + proximity_score * 0.25
    )

    closest_asset = min(
        _CRITICAL_LOCATIONS.items(),
        key=lambda loc: _haversine_km(lat, lon, loc[1][0], loc[1][1]),
    )

    return {
        'composite_score': round(composite, 3),
        'affiliation_score': aff_score,
        'threat_level_score': threat_score,
        'type_score': type_score,
        'proximity_score': round(proximity_score, 3),
        'distance_to_seoul_km': round(dist_seoul, 1),
        'closest_critical_asset': closest_asset[0],
        'distance_to_closest_km': round(
            _haversine_km(lat, lon, closest_asset[1][0], closest_asset[1][1]), 1
        ),
        'classification': (
            'CRITICAL' if composite >= 0.8 else
            'HIGH' if composite >= 0.6 else
            'MEDIUM' if composite >= 0.4 else
            'LOW'
        ),
    }


@app.get('/api/v1/threat-assessment')
async def threat_assessment() -> dict:
    """Compute threat assessment for all actors (Panopticon engagement scoring)."""
    container = get_container()
    actors = await container.actor_repo.find_recent(200)
    results = []
    for a in actors:
        actor_data = _actor_to_frontend(a)
        score = _compute_threat_score(actor_data)
        results.append({
            'actor_id': actor_data['id'],
            'name': actor_data['name'],
            'affiliation': actor_data['affiliation'],
            'domain': actor_data['domain'],
            **score,
        })
    # Sort by composite score descending
    results.sort(key=lambda x: x['composite_score'], reverse=True)
    return {
        'assessments': results,
        'total': len(results),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'critical_count': sum(1 for r in results if r['classification'] == 'CRITICAL'),
        'high_count': sum(1 for r in results if r['classification'] == 'HIGH'),
    }


# =============================================================================
# Enhanced SDR Detections (Layer 0 — URH-derived signal processing model)
# =============================================================================


# URH Modulator.py modulation types
SDR_MODULATION_TYPES = {
    'ASK': 'Amplitude Shift Keying',
    'FSK': 'Frequency Shift Keying',
    'PSK': 'Phase Shift Keying',
    'GFSK': 'Gaussian Frequency Shift Keying',
    'OQPSK': 'Offset Quadrature Phase Shift Keying',
    'QAM': 'Quadrature Amplitude Modulation',
    'AM': 'Amplitude Modulation (analog)',
    'FM': 'Frequency Modulation (analog)',
    'CW': 'Continuous Wave',
    'FHSS': 'Frequency Hopping Spread Spectrum',
    'DSSS': 'Direct Sequence Spread Spectrum',
    'UNKNOWN': 'Unknown modulation',
}

# URH FieldType.py protocol field classification
PROTOCOL_FIELD_TYPES = [
    'PREAMBLE', 'SYNC', 'LENGTH', 'SRC_ADDRESS', 'DST_ADDRESS',
    'SEQUENCE_NUMBER', 'TYPE', 'DATA', 'CHECKSUM', 'CUSTOM',
]

# Military frequency bands relevant to Korean Peninsula ops
MIL_FREQ_BANDS = {
    'HF': {'min_mhz': 3.0, 'max_mhz': 30.0, 'usage': 'Long-range military comms'},
    'VHF_LOW': {'min_mhz': 30.0, 'max_mhz': 88.0, 'usage': 'Tactical ground comms'},
    'VHF_AIR': {'min_mhz': 108.0, 'max_mhz': 137.0, 'usage': 'Aviation VHF'},
    'UHF_MIL': {'min_mhz': 225.0, 'max_mhz': 400.0, 'usage': 'Military UHF / SATCOM'},
    'L_BAND': {'min_mhz': 1000.0, 'max_mhz': 2000.0, 'usage': 'GPS / Radar / ADS-B'},
    'S_BAND': {'min_mhz': 2000.0, 'max_mhz': 4000.0, 'usage': 'Radar / WiFi'},
    'C_BAND': {'min_mhz': 4000.0, 'max_mhz': 8000.0, 'usage': 'SATCOM / Radar'},
    'X_BAND': {'min_mhz': 8000.0, 'max_mhz': 12000.0, 'usage': 'Fire control radar'},
}


def _classify_freq_band(freq_mhz: float) -> str:
    """Classify frequency into military band (URH signal analysis pattern)."""
    for band_name, band_info in MIL_FREQ_BANDS.items():
        if band_info['min_mhz'] <= freq_mhz <= band_info['max_mhz']:
            return band_name
    return 'OTHER'


@app.get('/api/v1/sdr/reference')
async def sdr_reference() -> dict:
    """Reference data for SDR analysis (URH-derived modulation/protocol models)."""
    return {
        'modulation_types': SDR_MODULATION_TYPES,
        'protocol_field_types': PROTOCOL_FIELD_TYPES,
        'military_frequency_bands': MIL_FREQ_BANDS,
    }


# =============================================================================
# Analytics & Fusion (Layer 5 — Panopticon sensor fusion pattern)
# =============================================================================


@app.get('/api/v1/analytics/overview')
async def analytics_overview() -> dict:
    """COP analytics overview — force composition, threat summary, coverage."""
    container = get_container()
    actors = await container.actor_repo.find_recent(200)

    by_affiliation: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    by_type: dict[str, int] = {}
    threat_actors = []

    for a in actors:
        aff = AFFILIATION_MAP.get(a.affiliation.value, 'UNKNOWN')
        dom = ACTOR_TYPE_TO_DOMAIN.get(a.actor_type.value, 'LAND')
        atype = a.actor_type.value

        by_affiliation[aff] = by_affiliation.get(aff, 0) + 1
        by_domain[dom] = by_domain.get(dom, 0) + 1
        by_type[atype] = by_type.get(atype, 0) + 1

        if aff in ('HOSTILE', 'UNKNOWN'):
            actor_data = _actor_to_frontend(a)
            score = _compute_threat_score(actor_data)
            threat_actors.append({
                'name': a.callsign,
                'classification': score['classification'],
                'composite_score': score['composite_score'],
            })

    threat_actors.sort(key=lambda x: x['composite_score'], reverse=True)

    return {
        'total_tracks': len(actors),
        'by_affiliation': by_affiliation,
        'by_domain': by_domain,
        'by_type': by_type,
        'top_threats': threat_actors[:10],
        'force_ratio': {
            'friendly': by_affiliation.get('FRIEND', 0),
            'hostile': by_affiliation.get('HOSTILE', 0),
            'ratio': round(
                by_affiliation.get('FRIEND', 1) / max(by_affiliation.get('HOSTILE', 1), 1), 2
            ),
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


@app.get('/api/v1/analytics/distance-matrix')
async def distance_matrix(
    affiliation: str = Query('HOSTILE', description='Filter actors by affiliation'),
    target_lat: float = Query(37.5665, description='Target latitude (default: Seoul)'),
    target_lon: float = Query(126.978, description='Target longitude (default: Seoul)'),
) -> dict:
    """Distance matrix from filtered actors to target (Panopticon pursuit pattern)."""
    container = get_container()
    actors = await container.actor_repo.find_recent(200)

    distances = []
    for a in actors:
        aff = AFFILIATION_MAP.get(a.affiliation.value, 'UNKNOWN')
        if aff != affiliation:
            continue
        if a.position is None:
            continue

        dist_km = _haversine_km(
            a.position.latitude, a.position.longitude, target_lat, target_lon
        )
        bearing = math.degrees(
            math.atan2(
                math.sin(math.radians(target_lon - a.position.longitude)) * math.cos(math.radians(target_lat)),
                math.cos(math.radians(a.position.latitude)) * math.sin(math.radians(target_lat))
                - math.sin(math.radians(a.position.latitude)) * math.cos(math.radians(target_lat))
                * math.cos(math.radians(target_lon - a.position.longitude)),
            )
        ) % 360

        distances.append({
            'actor_id': str(a.id),
            'name': a.callsign,
            'domain': ACTOR_TYPE_TO_DOMAIN.get(a.actor_type.value, 'LAND'),
            'distance_km': round(dist_km, 1),
            'bearing_deg': round(bearing, 1),
            'position': {
                'latitude': a.position.latitude,
                'longitude': a.position.longitude,
            },
        })

    distances.sort(key=lambda x: x['distance_km'])
    return {
        'target': {'latitude': target_lat, 'longitude': target_lon},
        'affiliation_filter': affiliation,
        'distances': distances,
        'total': len(distances),
        'closest': distances[0] if distances else None,
    }


# =============================================================================
# ADS-B State Model (Layer 0 — plane-notify/airplanejs patterns)
# =============================================================================


@app.get('/api/v1/adsb/state-model')
async def adsb_state_model() -> dict:
    """ADS-B aircraft state model reference data (plane-notify + airplanejs patterns)."""
    return {
        'message_types': {
            'DF17_TC1_4': {'name': 'Aircraft Identification', 'bits': 112, 'fields': ['callsign', 'category', 'wake_turbulence']},
            'DF17_TC5_8': {'name': 'Surface Position', 'bits': 112, 'fields': ['lat_cpr', 'lon_cpr', 'ground_speed', 'ground_track']},
            'DF17_TC9_18': {'name': 'Airborne Position (Baro Alt)', 'bits': 112, 'fields': ['lat_cpr', 'lon_cpr', 'altitude_ft', 'time_parity', 'surveillance_status']},
            'DF17_TC19': {'name': 'Airborne Velocity', 'bits': 112, 'fields': ['ground_speed_kts', 'track_deg', 'vertical_rate_fpm', 'heading_deg', 'ias_kts']},
            'DF17_TC20_22': {'name': 'Airborne Position (GNSS Alt)', 'bits': 112, 'fields': ['lat_cpr', 'lon_cpr', 'gnss_altitude_ft', 'time_parity']},
            'DF17_TC28': {'name': 'Aircraft Status', 'bits': 112, 'fields': ['emergency_state', 'squawk', 'spi']},
            'DF17_TC29': {'name': 'Target State & Status', 'bits': 112, 'fields': ['sel_altitude', 'baro_pressure', 'heading', 'nav_modes']},
            'DF17_TC31': {'name': 'Operational Status', 'bits': 112, 'fields': ['version', 'nic_supplement', 'nac_p', 'sil']},
        },
        'aircraft_state_fields': [
            'icao_hex', 'callsign', 'registration', 'aircraft_type',
            'latitude', 'longitude', 'alt_baro_ft', 'alt_gnss_ft',
            'ground_speed_kts', 'track_deg', 'heading_deg', 'ias_kts',
            'vertical_rate_fpm', 'squawk', 'on_ground', 'spi',
            'nav_modes', 'sel_nav_alt_ft', 'emergency',
            'seen_pos_sec', 'rssi_dbm',
        ],
        'state_machine': {
            'states': ['UNKNOWN', 'ACQUIRED', 'AIRBORNE', 'TAXIING', 'CIRCLING', 'EMERGENCY', 'LANDED', 'DATA_LOSS'],
            'transitions': {
                'UNKNOWN_to_ACQUIRED': 'First DF17 message received',
                'ACQUIRED_to_AIRBORNE': 'on_ground=False, alt > 1000ft AGL',
                'AIRBORNE_to_CIRCLING': 'bearing_change >= 720deg in 20min window',
                'AIRBORNE_to_EMERGENCY': 'squawk in [7500, 7600, 7700] held >= 60s',
                'AIRBORNE_to_LANDED': 'on_ground=True OR data_loss > N min + alt < 10000ft AGL',
                'ANY_to_DATA_LOSS': 'No position update for data_loss_minutes',
            },
        },
        'emergency_squawks': {'7500': 'Hijacking', '7600': 'Radio Failure', '7700': 'General Emergency'},
        'trigger_events': ['TAKEOFF', 'LANDING', 'EMERGENCY', 'CIRCLING', 'DATA_LOSS', 'DATA_ACQUISITION'],
        'cpr_decoding': {
            'algorithm': 'Compact Position Reporting (CPR)',
            'requires': 'Even + Odd frame pair (different time_parity bits)',
            'precision_m': 5,
            'lat_zones': 60,
            'lon_zones': 'Variable — max(NL(lat)-1, 1)',
            'steps': [
                '1. Collect even (F=0) and odd (F=1) DF17 TC9-18 frames',
                '2. Compute latitude zone index j',
                '3. Decode latitude using dLat = 360/(4*NZ) = 6deg',
                '4. Compute longitude zone NL from decoded latitude',
                '5. Decode longitude using dLon = 360/NL',
                '6. Resolve hemisphere ambiguity with receiver position',
            ],
        },
        'receiver_config': {
            'frequency_mhz': 1090.0,
            'modulation': 'PPM (Pulse Position Modulation)',
            'data_rate_mbps': 1.0,
            'protocol': 'Mode S Extended Squitter',
            'sdr_devices': ['RTL-SDR', 'Airspy Mini', 'HackRF One', 'FlightAware ProStick'],
        },
        'data_sources': ['ADSBX_V2_API', 'OPENSKY_NETWORK', 'RTL_SDR_1090MHZ', 'DUMP1090_BEAST'],
    }


# =============================================================================
# AIS Vessel Tracking Model (Layer 0 — AIS-catcher decoder patterns)
# =============================================================================


@app.get('/api/v1/ais/vessel-model')
async def ais_vessel_model() -> dict:
    """AIS vessel tracking model reference data (AIS-catcher decoder patterns)."""
    return {
        'message_types': {
            '1': {'name': 'Position Report Class A (Scheduled)', 'bits': 168, 'fields': ['mmsi', 'nav_status', 'rot', 'sog', 'position_accuracy', 'longitude', 'latitude', 'cog', 'true_heading', 'timestamp', 'maneuver_indicator']},
            '2': {'name': 'Position Report Class A (Assigned)', 'bits': 168, 'fields': 'Same as Type 1'},
            '3': {'name': 'Position Report Class A (Response to Interrogation)', 'bits': 168, 'fields': 'Same as Type 1'},
            '4': {'name': 'Base Station Report', 'bits': 168, 'fields': ['mmsi', 'year', 'month', 'day', 'hour', 'minute', 'second', 'longitude', 'latitude', 'type_of_epfd']},
            '5': {'name': 'Static & Voyage Related Data', 'bits': 424, 'fields': ['mmsi', 'imo', 'callsign', 'vessel_name', 'ship_type', 'bow', 'stern', 'port', 'starboard', 'type_of_epfd', 'eta', 'draught', 'destination']},
            '18': {'name': 'Standard Class B Position Report', 'bits': 168, 'fields': ['mmsi', 'sog', 'position_accuracy', 'longitude', 'latitude', 'cog', 'true_heading', 'timestamp']},
            '19': {'name': 'Extended Class B Position Report', 'bits': 312, 'fields': ['mmsi', 'sog', 'longitude', 'latitude', 'cog', 'true_heading', 'vessel_name', 'ship_type', 'bow', 'stern', 'port', 'starboard']},
            '24': {'name': 'Class B Static Data Report', 'bits': 168, 'fields': ['mmsi', 'part_A: vessel_name', 'part_B: callsign, ship_type, dimensions']},
        },
        'vessel_state_fields': [
            'mmsi', 'imo', 'callsign', 'vessel_name', 'ship_type',
            'latitude', 'longitude', 'cog_deg', 'sog_kts', 'true_heading_deg',
            'nav_status', 'rot_deg_per_min', 'draught_m', 'destination', 'eta',
            'dimension_bow_m', 'dimension_stern_m', 'dimension_port_m', 'dimension_starboard_m',
            'position_accuracy', 'channel', 'last_update_timestamp',
        ],
        'nav_status_codes': {
            '0': 'Under way using engine', '1': 'At anchor', '2': 'Not under command',
            '3': 'Restricted manoeuvrability', '4': 'Constrained by her draught',
            '5': 'Moored', '6': 'Aground', '7': 'Engaged in fishing',
            '8': 'Under way sailing', '9': 'Reserved (HSC)', '10': 'Reserved (WIG)',
            '11': 'Power-driven vessel towing astern', '12': 'Power-driven vessel pushing/towing',
            '14': 'AIS-SART (active)', '15': 'Not defined / default',
        },
        'ship_type_codes': {
            '30': 'Fishing', '31-32': 'Towing', '33': 'Dredging/Underwater ops',
            '34': 'Diving operations', '35': 'Military operations',
            '36': 'Sailing', '37': 'Pleasure craft',
            '40-49': 'High speed craft', '50': 'Pilot vessel',
            '51': 'Search and rescue vessel', '52': 'Tug',
            '55': 'Law enforcement', '58': 'Medical transport',
            '60-69': 'Passenger ship', '70-79': 'Cargo ship',
            '80-89': 'Tanker', '90-99': 'Other',
        },
        'decoder_state_machine': {
            'states': ['TRAINING', 'STARTFLAG', 'DATAFCS', 'FOUNDMESSAGE'],
            'crc_poly': '0x8408',
            'crc_check': '~0x0F47',
            'encoding': 'NRZI (Non-Return-to-Zero Inverted)',
        },
        'nmea_format': {
            'sentence': '!AIVDM,count,index,groupId,channel,payload,fillbits*checksum',
            'channels': {'A': '161.975 MHz', 'B': '162.025 MHz'},
            'tag_block': '\\s:timestamp,q:quality,c:station\\',
        },
        'data_pipeline': {
            'sources': ['RTL-SDR 162MHz', 'Airspy', 'HackRF', 'Network Feed (UDP)', 'Serial Port'],
            'flow': ['RF Input', 'NRZI Decoding', 'Bit Extraction', 'CRC16 Validation', 'Message Parsing', 'NMEA Output'],
            'forwarding': ['UDP multicast', 'TCP stream', 'HTTP POST', 'JSON WebSocket'],
        },
    }


# =============================================================================
# Signal Processing Chain (Layer 0 — openwebrx + noaa-apt patterns)
# =============================================================================


@app.get('/api/v1/signals/processing-chain')
async def signal_processing_chain() -> dict:
    """Multi-protocol SDR signal processing reference (openwebrx + noaa-apt patterns)."""
    return {
        'sdr_pipeline': {
            'stages': [
                {'name': 'RF Input', 'description': 'Complex I/Q samples from SDR device', 'output': 'complex64 stream'},
                {'name': 'Frequency Shift', 'description': 'Translate target freq to baseband', 'output': 'centered complex stream'},
                {'name': 'FIR Decimation', 'description': 'Integer-rate downsampling with anti-alias filter', 'output': 'reduced-rate stream'},
                {'name': 'Fractional Decimation', 'description': 'Polyphase resampler for non-integer ratios', 'output': 'target IF rate'},
                {'name': 'Bandpass Filter', 'description': 'Select signal bandwidth (transition = 0.15 * out/in)', 'output': 'filtered stream'},
                {'name': 'Squelch', 'description': '5-block power averaging, configurable threshold dB', 'output': 'gated stream'},
                {'name': 'Demodulation', 'description': 'Mode-specific signal extraction', 'output': 'audio/data stream'},
                {'name': 'Output', 'description': 'ADPCM/Opus compression + client delivery', 'output': 'audio packets'},
            ],
        },
        'supported_modes': {
            'analog': {
                'AM': {'bandwidth_hz': 10000, 'audio_rate_hz': 12000, 'description': 'Amplitude Modulation'},
                'NFM': {'bandwidth_hz': 12500, 'audio_rate_hz': 12000, 'description': 'Narrow FM (tactical radio)'},
                'WFM': {'bandwidth_hz': 150000, 'audio_rate_hz': 48000, 'description': 'Wideband FM (broadcast)', 'features': ['RDS', 'Stereo']},
                'LSB': {'bandwidth_hz': 2700, 'audio_rate_hz': 12000, 'description': 'Lower Sideband (HF comms)'},
                'USB': {'bandwidth_hz': 2700, 'audio_rate_hz': 12000, 'description': 'Upper Sideband (HF comms)'},
                'CW': {'bandwidth_hz': 500, 'audio_rate_hz': 12000, 'description': 'Continuous Wave (Morse)'},
            },
            'digital_voice': ['DMR', 'D-Star', 'NXDN', 'YSF', 'M17', 'FreeDV'],
            'weak_signal': ['FT8', 'FT4', 'JT65', 'JT9', 'WSPR', 'FST4', 'Q65'],
            'data': ['BPSK31', 'BPSK63', 'RTTY', 'Packet', 'POCSAG'],
            'specialized': {
                'ADS-B': {'if_rate_hz': 2400000, 'center_freq_mhz': 1090.0, 'description': 'Aircraft transponder'},
                'HFDL': {'description': 'HF Data Link (aircraft text messages)'},
                'AIS': {'center_freq_mhz': 162.0, 'description': 'Automatic Identification System (ships)'},
                'ISM': {'center_freq_mhz': 433.92, 'description': 'Industrial/Scientific/Medical band'},
            },
        },
        'satellite_apt': {
            'description': 'NOAA APT (Automatic Picture Transmission) weather satellite imagery',
            'decode_pipeline': [
                'Raw audio input (11025 Hz)',
                'Resample + lowpass (cutout=4800 Hz, atten=40dB)',
                'AM demodulation at carrier=2400 Hz',
                'Lowpass filter (cutout=2080 Hz)',
                'Sync frame detection (39px cross-correlation)',
                'Row alignment (2080 pixels per row)',
                'Final resample to 4160 Hz (1 sample/pixel)',
            ],
            'frame_structure': {
                'pixels_per_row': 2080,
                'channel_A': {'sync': 39, 'space_data': 47, 'image': 909, 'telemetry': 45},
                'channel_B': {'sync': 39, 'space_data': 47, 'image': 909, 'telemetry': 45},
            },
            'orbit_prediction': 'TLE (Two-Line Element) based propagation for pass scheduling',
            'satellites': ['NOAA-15 (137.620 MHz)', 'NOAA-18 (137.9125 MHz)', 'NOAA-19 (137.100 MHz)'],
        },
        'military_relevance': {
            'SIGINT': 'Detect and classify unknown transmissions via modulation analysis',
            'COMINT': 'Monitor military communication frequencies (HF/VHF/UHF)',
            'ELINT': 'Detect radar emissions (S/C/X-band)',
            'ADS-B': 'Track military aircraft via transponder (when active)',
            'AIS': 'Track naval vessels and maritime traffic',
            'SATINT': 'Weather imagery for operational planning',
        },
    }


# =============================================================================
# MDO Doctrine — Multi-Domain Operations Status (doctrine research)
# =============================================================================


# MDO domain coverage computed from actor positions and types
_MDO_DOMAINS = ['LAND', 'SEA', 'AIR', 'SPACE', 'CYBER', 'EMS']

# MDO phases (US Army FM 3-0 derived)
_MDO_PHASES = [
    'COMPETE',       # Shape the environment below armed conflict
    'PENETRATE',     # Create windows of opportunity through enemy A2/AD
    'DIS_INTEGRATE', # Disrupt enemy C2 and combined arms coherence
    'EXPLOIT',       # Achieve operational objectives rapidly
    'RE_COMPETE',    # Consolidate gains and transition back to competition
]


@app.get('/api/v1/doctrine/mdo-status')
async def mdo_status() -> dict:
    """Multi-Domain Operations status — cross-domain coverage and convergence assessment."""
    container = get_container()
    actors = await container.actor_repo.find_recent(200)

    domain_coverage: dict[str, dict] = {}
    for mdo_domain in _MDO_DOMAINS:
        domain_actors = [
            a for a in actors
            if ACTOR_TYPE_TO_DOMAIN.get(a.actor_type.value, 'LAND') == mdo_domain
            or (mdo_domain == 'EMS' and a.actor_type.value == 'TRANSMISSION_SOURCE')
        ]
        friendly = sum(1 for a in domain_actors if a.affiliation.value in ('FRIENDLY',))
        hostile = sum(1 for a in domain_actors if a.affiliation.value in ('HOSTILE',))
        domain_coverage[mdo_domain] = {
            'total_tracks': len(domain_actors),
            'friendly': friendly,
            'hostile': hostile,
            'coverage_pct': min(100, len(domain_actors) * 10),  # Simplified coverage model
            'status': 'CONTESTED' if hostile > 0 and friendly > 0 else
                      'DENIED' if hostile > friendly else
                      'PERMISSIVE' if friendly > 0 else 'UNKNOWN',
        }

    # Cross-domain synergy score (how many domains have both friendly presence and hostile awareness)
    contested_domains = sum(1 for d in domain_coverage.values() if d['status'] == 'CONTESTED')
    permissive_domains = sum(1 for d in domain_coverage.values() if d['status'] == 'PERMISSIVE')
    convergence_readiness = round((permissive_domains + contested_domains * 0.5) / max(len(_MDO_DOMAINS), 1), 3)

    # Determine current MDO phase based on force posture
    total_friendly = sum(d['friendly'] for d in domain_coverage.values())
    total_hostile = sum(d['hostile'] for d in domain_coverage.values())
    if total_hostile == 0:
        phase = 'COMPETE'
    elif total_friendly > total_hostile * 2:
        phase = 'EXPLOIT'
    elif contested_domains >= 3:
        phase = 'DIS_INTEGRATE'
    elif contested_domains >= 1:
        phase = 'PENETRATE'
    else:
        phase = 'RE_COMPETE'

    return {
        'doctrine': 'Multi-Domain Operations (FM 3-0)',
        'current_phase': phase,
        'phases': _MDO_PHASES,
        'domains': domain_coverage,
        'convergence_readiness': convergence_readiness,
        'cross_domain_synergy': {
            'contested_domains': contested_domains,
            'permissive_domains': permissive_domains,
            'denied_domains': sum(1 for d in domain_coverage.values() if d['status'] == 'DENIED'),
            'total_friendly': total_friendly,
            'total_hostile': total_hostile,
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Mosaic Warfare — Kill Web Connectivity Graph
# =============================================================================


@app.get('/api/v1/doctrine/kill-web')
async def kill_web() -> dict:
    """Mosaic warfare sensor-to-shooter kill web connectivity graph."""
    container = get_container()
    actors = await container.actor_repo.find_recent(200)

    sensors: list[dict] = []
    shooters: list[dict] = []
    c2_nodes: list[dict] = []
    edges: list[dict] = []

    for a in actors:
        aff = AFFILIATION_MAP.get(a.affiliation.value, 'UNKNOWN')
        if aff != 'FRIEND':
            continue

        meta = a.metadata or {}
        assessed = meta.get('assessed_type', '')
        atype = a.actor_type.value
        domain = ACTOR_TYPE_TO_DOMAIN.get(atype, 'LAND')

        node = {
            'id': str(a.id),
            'name': a.callsign,
            'domain': domain,
            'role': 'UNKNOWN',
            'position': {'latitude': a.position.latitude, 'longitude': a.position.longitude} if a.position else None,
        }

        # Classify into Mosaic roles: SENSOR, SHOOTER, C2, MULTI
        if any(kw in assessed.upper() for kw in ['RADAR', 'SIGINT', 'ISR', 'RECONNAISSANCE', 'P-8', 'RC-135', 'RQ-4', 'RC-2', 'AN/TPS']):
            node['role'] = 'SENSOR'
            sensors.append(node)
        elif any(kw in assessed.upper() for kw in ['MBT', 'DDG', 'FIGHTER', 'KF-21', 'MLRS', 'BATTERY']):
            node['role'] = 'SHOOTER'
            shooters.append(node)
        elif any(kw in assessed.upper() for kw in ['HQ', 'COMMAND', 'KC-330', 'TANKER', 'C2']):
            node['role'] = 'C2'
            c2_nodes.append(node)
        else:
            # Default: multi-role (both sensor and shooter capability assumed)
            node['role'] = 'MULTI'
            sensors.append(node)
            shooters.append(node)

    # Build kill web edges: every sensor connects to every shooter via C2
    for sensor in sensors:
        for shooter in shooters:
            if sensor['id'] == shooter['id']:
                continue
            # Calculate latency based on domain pairing
            same_domain = sensor['domain'] == shooter['domain']
            edge = {
                'from': sensor['id'],
                'from_name': sensor['name'],
                'to': shooter['id'],
                'to_name': shooter['name'],
                'link_type': 'SAME_DOMAIN' if same_domain else 'CROSS_DOMAIN',
                'estimated_latency_ms': 200 if same_domain else 1500,
                'datalink': 'Link-16' if same_domain else 'JADC2 Gateway',
            }
            edges.append(edge)

    total_nodes = len(sensors) + len(shooters) + len(c2_nodes)
    max_edges = len(sensors) * len(shooters)
    connectivity = round(len(edges) / max(max_edges, 1), 3)

    return {
        'doctrine': 'Mosaic Warfare (DARPA)',
        'concept': 'Kill webs — composable sensor-to-shooter paths replacing linear kill chains',
        'nodes': {
            'sensors': sensors,
            'shooters': shooters,
            'c2': c2_nodes,
            'total': total_nodes,
        },
        'edges': edges[:50],  # Cap for response size
        'total_edges': len(edges),
        'kill_web_metrics': {
            'connectivity': connectivity,
            'redundancy': max(0, len(edges) - len(shooters)),
            'cross_domain_links': sum(1 for e in edges if e['link_type'] == 'CROSS_DOMAIN'),
            'same_domain_links': sum(1 for e in edges if e['link_type'] == 'SAME_DOMAIN'),
            'avg_paths_per_shooter': round(len(edges) / max(len(shooters), 1), 1),
        },
        'force_packages': [
            {'name': 'PKG-ALPHA', 'composition': 'SENSOR(RAVEN-7) + C2(CYGNUS-9) + SHOOTER(EAGLE-21)', 'mission': 'Air Superiority'},
            {'name': 'PKG-BRAVO', 'composition': 'SENSOR(POSEIDON-1) + C2(RIVET-55) + SHOOTER(TRIDENT-3)', 'mission': 'Maritime Strike'},
            {'name': 'PKG-CHARLIE', 'composition': 'SENSOR(SENTINEL-6) + C2(ALPHA-1) + SHOOTER(VIPER-6)', 'mission': 'Ground Defense'},
        ],
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# JADC2 OODA Cycle Metrics
# =============================================================================


@app.get('/api/v1/doctrine/ooda-cycle')
async def ooda_cycle() -> dict:
    """JADC2 OODA loop metrics — Sense → Make Sense → Act decision cycle assessment."""
    container = get_container()
    actors = await container.actor_repo.find_recent(200)

    # Compute OODA metrics from actor data freshness and coverage
    now = datetime.now(timezone.utc)
    total_actors = len(actors)
    stale_actors = 0
    avg_age_sec = 0.0

    for a in actors:
        if a.last_seen:
            age = (now - a.last_seen).total_seconds()
            avg_age_sec += age
            if age > 300:  # > 5 min = stale
                stale_actors += 1

    avg_age_sec = avg_age_sec / max(total_actors, 1)

    # OBSERVE phase: sensor coverage and data freshness
    observe_score = max(0.0, 1.0 - stale_actors / max(total_actors, 1))

    # ORIENT phase: threat assessment completeness
    friendly_count = sum(1 for a in actors if a.affiliation.value in ('FRIENDLY',))
    hostile_count = sum(1 for a in actors if a.affiliation.value in ('HOSTILE',))
    unknown_count = sum(1 for a in actors if a.affiliation.value in ('UNKNOWN',))
    orient_score = max(0.0, 1.0 - unknown_count / max(total_actors, 1))

    # DECIDE phase: force ratio assessment (higher ratio = more decision options)
    force_ratio = friendly_count / max(hostile_count, 1)
    decide_score = min(1.0, force_ratio / 3.0)  # Normalize: 3:1 ratio = full score

    # ACT phase: simulated response readiness
    act_score = min(1.0, friendly_count / max(hostile_count + unknown_count, 1))

    # Overall OODA cycle speed (composite)
    ooda_composite = round((observe_score + orient_score + decide_score + act_score) / 4.0, 3)

    return {
        'doctrine': 'JADC2 OODA Loop (Boyd Cycle)',
        'concept': 'Observe → Orient → Decide → Act — accelerate decision cycle to outpace adversary',
        'ooda_phases': {
            'OBSERVE': {
                'score': round(observe_score, 3),
                'total_tracks': total_actors,
                'stale_tracks': stale_actors,
                'avg_track_age_sec': round(avg_age_sec, 1),
                'sensor_sources': ['ADS-B', 'AIS', 'SDR', 'HUMINT', 'SIGINT', 'IMINT'],
                'status': 'GREEN' if observe_score > 0.8 else 'AMBER' if observe_score > 0.5 else 'RED',
            },
            'ORIENT': {
                'score': round(orient_score, 3),
                'identified_tracks': friendly_count + hostile_count,
                'unidentified_tracks': unknown_count,
                'threat_assessment': 'ACTIVE' if hostile_count > 0 else 'NOMINAL',
                'status': 'GREEN' if orient_score > 0.8 else 'AMBER' if orient_score > 0.5 else 'RED',
            },
            'DECIDE': {
                'score': round(decide_score, 3),
                'force_ratio': round(force_ratio, 2),
                'decision_advantage': 'FAVORABLE' if force_ratio > 1.5 else 'CONTESTED' if force_ratio > 0.8 else 'UNFAVORABLE',
                'courses_of_action': max(1, int(force_ratio * 2)),
                'status': 'GREEN' if decide_score > 0.8 else 'AMBER' if decide_score > 0.5 else 'RED',
            },
            'ACT': {
                'score': round(act_score, 3),
                'response_readiness': 'HIGH' if act_score > 0.8 else 'MEDIUM' if act_score > 0.5 else 'LOW',
                'available_effectors': friendly_count,
                'engagement_capacity': min(hostile_count, friendly_count),
                'status': 'GREEN' if act_score > 0.8 else 'AMBER' if act_score > 0.5 else 'RED',
            },
        },
        'composite_score': ooda_composite,
        'cycle_assessment': (
            'SUPERIOR' if ooda_composite > 0.8 else
            'ADEQUATE' if ooda_composite > 0.6 else
            'DEGRADED' if ooda_composite > 0.4 else
            'CRITICAL'
        ),
        'ncw_principles': {
            'information_superiority': round(orient_score * observe_score, 3),
            'shared_awareness': round((total_actors - stale_actors) / max(total_actors, 1), 3),
            'self_synchronization': round(decide_score * act_score, 3),
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Force Package Composer (Mosaic Warfare composable force packages)
# =============================================================================


@app.get('/api/v1/doctrine/force-packages')
async def force_packages() -> dict:
    """Composable force packages for Mosaic Warfare operations."""
    container = get_container()
    actors = await container.actor_repo.find_recent(200)

    friendly_actors = []
    for a in actors:
        if a.affiliation.value not in ('FRIENDLY',):
            continue
        meta = a.metadata or {}
        assessed = meta.get('assessed_type', a.actor_type.value)
        domain = ACTOR_TYPE_TO_DOMAIN.get(a.actor_type.value, 'LAND')
        friendly_actors.append({
            'id': str(a.id),
            'name': a.callsign,
            'domain': domain,
            'type': assessed,
            'position': {'latitude': a.position.latitude, 'longitude': a.position.longitude} if a.position else None,
        })

    # Auto-compose force packages based on mission templates
    packages = []

    # Air Superiority Package
    air_assets = [a for a in friendly_actors if a['domain'] == 'AIR']
    ground_radar = [a for a in friendly_actors if 'RADAR' in a.get('type', '').upper() or 'AN/TPS' in a.get('type', '').upper()]
    if air_assets:
        packages.append({
            'id': 'PKG-AIRSUP',
            'name': 'Air Superiority',
            'mission_type': 'OFFENSIVE_COUNTER_AIR',
            'assets': air_assets[:4],
            'supporting': ground_radar[:2],
            'readiness': 'GREEN' if len(air_assets) >= 2 else 'AMBER',
            'capability': ['BVR Engagement', 'SEAD', 'DCA'],
        })

    # Maritime Strike Package
    sea_assets = [a for a in friendly_actors if a['domain'] == 'SEA']
    maritime_isr = [a for a in air_assets if any(kw in a.get('type', '').upper() for kw in ['P-8', 'POSEIDON', 'MPA'])]
    if sea_assets:
        packages.append({
            'id': 'PKG-MARSTK',
            'name': 'Maritime Strike',
            'mission_type': 'ANTI_SURFACE_WARFARE',
            'assets': sea_assets[:3],
            'supporting': maritime_isr[:2],
            'readiness': 'GREEN' if len(sea_assets) >= 1 and len(maritime_isr) >= 1 else 'AMBER',
            'capability': ['Anti-Ship Missile', 'ASW', 'Naval Gunfire Support'],
        })

    # Ground Defense Package
    land_assets = [a for a in friendly_actors if a['domain'] == 'LAND']
    if land_assets:
        packages.append({
            'id': 'PKG-GNDDEF',
            'name': 'Ground Defense',
            'mission_type': 'AREA_DEFENSE',
            'assets': land_assets[:4],
            'supporting': ground_radar[:1],
            'readiness': 'GREEN' if len(land_assets) >= 2 else 'AMBER',
            'capability': ['Direct Fire', 'Indirect Fire', 'Counter-Mobility'],
        })

    # ISR Package
    isr_assets = [a for a in friendly_actors if any(kw in a.get('type', '').upper() for kw in ['RQ-4', 'RC-135', 'RC-2', 'ISR', 'SIGINT', 'RECON'])]
    if isr_assets:
        packages.append({
            'id': 'PKG-ISR',
            'name': 'Multi-Domain ISR',
            'mission_type': 'INTELLIGENCE_SURVEILLANCE_RECONNAISSANCE',
            'assets': isr_assets[:4],
            'supporting': [],
            'readiness': 'GREEN' if len(isr_assets) >= 2 else 'AMBER',
            'capability': ['SIGINT', 'IMINT', 'ELINT', 'COMINT', 'ADS-B Monitoring'],
        })

    return {
        'doctrine': 'Mosaic Warfare — Composable Force Packages',
        'concept': 'Disaggregated, recomposable force elements assembled into mission-specific packages',
        'available_assets': len(friendly_actors),
        'packages': packages,
        'total_packages': len(packages),
        'composition_rules': {
            'minimum_package': 'SENSOR + C2 + EFFECTOR',
            'cross_domain_bonus': 'Multi-domain packages get priority for convergence windows',
            'redundancy_rule': 'No single point of failure — minimum 2 sensor paths per shooter',
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
