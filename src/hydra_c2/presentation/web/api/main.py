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
