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
