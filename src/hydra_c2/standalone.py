"""HYDRA-C2 Standalone Mode — Run locally without external databases.

Serves the FastAPI backend with in-memory mock data so the COP dashboard
can be demonstrated without PostGIS, Neo4j, or MQTT.

Usage:
    python -m hydra_c2.standalone          # default port 8000
    python -m hydra_c2.standalone --port 8080
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import structlog
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logger = structlog.get_logger()

# ─── In-memory actor data ────────────────────────────────────────────────────

ACTOR_TYPE_TO_DOMAIN = {
    "PERSON": "LAND", "VEHICLE": "LAND", "UNIT": "LAND", "EQUIPMENT": "LAND",
    "AIRCRAFT": "AIR", "UAV": "AIR",
    "VESSEL": "SEA",
    "TRANSMISSION_SOURCE": "CYBER",
    "UNKNOWN": "LAND",
}

AFFILIATION_MAP = {
    "FRIENDLY": "FRIEND", "HOSTILE": "HOSTILE",
    "NEUTRAL": "NEUTRAL", "UNKNOWN": "UNKNOWN",
}

# SIDC codes per actor type + affiliation
SIDC_TABLE = {
    ("UNIT", "FRIENDLY"):              "SFGPUCI----D---",
    ("VEHICLE", "FRIENDLY"):           "SFGPUCVAM--D---",
    ("AIRCRAFT", "FRIENDLY"):          "SFAPMF------D--",
    ("VESSEL", "FRIENDLY"):            "SFSPCLDD---D---",
    ("UAV", "FRIENDLY"):               "SFAPMFQ----D---",
    ("UNIT", "HOSTILE"):               "SHGPUCI----D---",
    ("AIRCRAFT", "HOSTILE"):           "SHAPMF------D--",
    ("VEHICLE", "HOSTILE"):            "SHGPUCVAM--D---",
    ("VESSEL", "HOSTILE"):             "SHSPCLDD---D---",
    ("TRANSMISSION_SOURCE", "HOSTILE"): "SHGPE------D---",
    ("VESSEL", "NEUTRAL"):             "SNSPCLDD---D---",
    ("AIRCRAFT", "NEUTRAL"):           "SNAPMF------D--",
    ("UNKNOWN", "UNKNOWN"):            "SUGPUCI----D---",
    ("UAV", "UNKNOWN"):                "SUAPMFQ----D---",
    ("PERSON", "UNKNOWN"):             "SUGPUCP----D---",
}

MOCK_ACTORS = [
    {"callsign": "ALPHA-1",       "type": "UNIT",     "aff": "FRIENDLY", "lat": 37.5665, "lon": 126.9780, "alt": 50.0},
    {"callsign": "VIPER-6",       "type": "VEHICLE",  "aff": "FRIENDLY", "lat": 37.4563, "lon": 126.7052, "alt": 15.0},
    {"callsign": "EAGLE-21",      "type": "AIRCRAFT", "aff": "FRIENDLY", "lat": 36.9600, "lon": 127.0300, "alt": 8500.0},
    {"callsign": "TRIDENT-3",     "type": "VESSEL",   "aff": "FRIENDLY", "lat": 35.0794, "lon": 129.0800, "alt": 0.0},
    {"callsign": "RAVEN-7",       "type": "UAV",      "aff": "FRIENDLY", "lat": 37.9000, "lon": 126.8500, "alt": 3000.0},
    {"callsign": "BEAR-1",        "type": "UNIT",     "aff": "HOSTILE",  "lat": 38.3200, "lon": 126.5500, "alt": 120.0},
    {"callsign": "FENCER-2",      "type": "AIRCRAFT", "aff": "HOSTILE",  "lat": 39.0200, "lon": 125.7500, "alt": 10000.0},
    {"callsign": "VENOM-5",       "type": "VEHICLE",  "aff": "HOSTILE",  "lat": 38.5100, "lon": 127.0100, "alt": 85.0},
    {"callsign": "SHARK-9",       "type": "VESSEL",   "aff": "HOSTILE",  "lat": 37.5000, "lon": 124.5000, "alt": 0.0},
    {"callsign": "GHOST-4",       "type": "TRANSMISSION_SOURCE", "aff": "HOSTILE", "lat": 38.7500, "lon": 125.9000, "alt": 0.0},
    {"callsign": "JADE-EXPRESS",  "type": "VESSEL",   "aff": "NEUTRAL",  "lat": 34.5000, "lon": 128.5000, "alt": 0.0},
    {"callsign": "KE-801",        "type": "AIRCRAFT", "aff": "NEUTRAL",  "lat": 36.5700, "lon": 126.8000, "alt": 11000.0},
    {"callsign": "CONTACT-ALPHA", "type": "UNKNOWN",  "aff": "UNKNOWN",  "lat": 37.7500, "lon": 125.2000, "alt": 500.0},
    {"callsign": "SHADOW-X",      "type": "UAV",      "aff": "UNKNOWN",  "lat": 38.0000, "lon": 126.2000, "alt": 1500.0},
    {"callsign": "NOMAD-12",      "type": "PERSON",   "aff": "UNKNOWN",  "lat": 37.8200, "lon": 126.7500, "alt": 200.0},
]

# Build full actor list with IDs
_actors = []
for a in MOCK_ACTORS:
    sidc = SIDC_TABLE.get((a["type"], a["aff"]), "SUGPUCI----D---")
    _actors.append({
        "id": str(uuid4()),
        "name": a["callsign"],
        "sidc": sidc,
        "affiliation": AFFILIATION_MAP[a["aff"]],
        "domain": ACTOR_TYPE_TO_DOMAIN.get(a["type"], "LAND"),
        "position": {
            "latitude": a["lat"],
            "longitude": a["lon"],
            "altitude": a["alt"],
        },
        "last_seen": (datetime.now(UTC) - timedelta(minutes=hash(a["callsign"]) % 60)).isoformat(),
        "source": "STANDALONE",
        "metadata": {"actor_type": a["type"], "standalone_mode": True},
    })


# ─── FastAPI application ─────────────────────────────────────────────────────

app = FastAPI(
    title="HYDRA-C2 API (Standalone)",
    description="Standalone mode — in-memory mock data, no external dependencies",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict:
    return {
        "status": "operational",
        "system": "HYDRA-C2",
        "version": "0.1.0",
        "mode": "standalone",
        "infrastructure": "in-memory",
        "layers": {
            "L0_physical_rf": "simulated",
            "L1_edge_computing": "simulated",
            "L2_mesh_transport": "simulated",
            "L3_data_ingestion": "simulated",
            "L4_persistence": "in-memory",
            "L5_analytics": "simulated",
            "L6_visualization": "operational",
        },
    }


@app.get("/api/v1/actors")
async def list_actors(
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    radius_m: float = Query(10000),
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    return {"actors": _actors[:limit], "total": len(_actors)}


@app.get("/api/v1/actors/{actor_id}/network")
async def get_actor_network(actor_id: str, depth: int = Query(3, ge=1, le=10)) -> dict:
    return {
        "actor_id": actor_id,
        "depth": depth,
        "network": [],
        "total": 0,
    }


@app.get("/api/v1/sdr/detections")
async def list_sdr_detections(limit: int = Query(100)) -> dict:
    return {"detections": [], "total": 0}


@app.post("/api/v1/cot/ingest")
async def ingest_cot() -> dict:
    return {"status": "acknowledged", "mode": "standalone"}


@app.post("/api/v1/geofences")
async def create_geofence() -> dict:
    return {"status": "created", "geofence_id": str(uuid4()), "mode": "standalone"}


@app.post("/api/v1/geofences/check")
async def check_geofence(lat: float = Query(...), lon: float = Query(...)) -> dict:
    return {"position": {"lat": lat, "lon": lon}, "breached": False, "geofences": []}


# ─── Static file serving for frontend ────────────────────────────────────────

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def mount_frontend(application: FastAPI) -> None:
    """Mount frontend static files if the build directory exists."""
    if FRONTEND_DIST.is_dir():
        # Serve index.html for SPA routing
        @application.get("/hydra-c2/{full_path:path}")
        async def serve_spa(full_path: str = "") -> FileResponse:
            file_path = FRONTEND_DIST / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(FRONTEND_DIST / "index.html")

        application.mount("/hydra-c2-assets", StaticFiles(directory=str(FRONTEND_DIST)), name="frontend")
        logger.info("frontend_mounted", path=str(FRONTEND_DIST))
    else:
        logger.warning("frontend_dist_not_found", expected=str(FRONTEND_DIST))


mount_frontend(app)


# ─── Entrypoint ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="HYDRA-C2 Standalone Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    args = parser.parse_args()

    banner = f"""
 ┌──────────────────────────────────────────────────────────────┐
 │                  HYDRA-C2 // STANDALONE MODE                 │
 │                                                              │
 │  API Server : http://{args.host}:{args.port}                        │
 │  Health     : http://{args.host}:{args.port}/health                 │
 │  Actors API : http://{args.host}:{args.port}/api/v1/actors          │
 │  COP Dashboard : http://{args.host}:{args.port}/hydra-c2/           │
 │                                                              │
 │  Mode: IN-MEMORY (no PostGIS/Neo4j/MQTT required)            │
 │  Actors loaded: {len(_actors):>3}                                     │
 └──────────────────────────────────────────────────────────────┘
"""
    print(banner)

    uvicorn.run(
        "hydra_c2.standalone:app",
        host=args.host,
        port=args.port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
