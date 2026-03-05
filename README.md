```text
 ██╗  ██╗ ██╗   ██╗ ██████╗  ██████╗   █████╗        ██████╗ ██████╗
 ██║  ██║ ╚██╗ ██╔╝ ██╔══██╗ ██╔══██╗ ██╔══██╗      ██╔════╝ ╚════██╗
 ███████║  ╚████╔╝  ██║  ██║ ██████╔╝ ███████║      ██║       █████╔╝
 ██╔══██║   ╚██╔╝   ██║  ██║ ██╔══██╗ ██╔══██║      ██║      ██╔═══╝
 ██║  ██║    ██║    ██████╔╝ ██║  ██║ ██║  ██║      ╚██████╗ ███████╗
 ╚═╝  ╚═╝    ╚═╝    ╚═════╝  ╚═╝  ╚═╝ ╚═╝  ╚═╝       ╚═════╝ ╚══════╝
```

```text
 ┌──────────────────────────────────────────────────────────────────┐
 │  HYDRA-C2 // MULTI-DOMAIN COMMAND & CONTROL FRAMEWORK           │
 │  Hybrid Universal Dynamic Reconnaissance Architecture           │
 │  CLASSIFICATION: UNCLASSIFIED // OPEN SOURCE                    │
 └──────────────────────────────────────────────────────────────────┘
```

<p align="center">
  <img src="https://img.shields.io/badge/STATUS-OPERATIONAL-39ff14?style=for-the-badge&labelColor=0a0a0f" alt="Status Operational">
  <img src="https://img.shields.io/badge/VERSION-0.1.0-blue?style=for-the-badge&labelColor=0a0a0f" alt="Version 0.1.0">
  <img src="https://img.shields.io/badge/LICENSE-MIT-blue?style=for-the-badge&labelColor=0a0a0f" alt="License MIT">
</p>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/PostGIS-3.4-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostGIS">
  <img src="https://img.shields.io/badge/Neo4j-5.x-008CC1?style=for-the-badge&logo=neo4j&logoColor=white" alt="Neo4j">
  <img src="https://img.shields.io/badge/TypeScript-5.0-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript">
</p>

> Multi-domain Command & Control framework for distributed operations. Real-time COP dashboard with MIL-STD-2525B symbology, PostGIS spatial analysis, and encrypted mesh networking.

```text
 SYSTEM STATUS ─────────────────────────────────────────────────────
 [●] COP DASHBOARD      ONLINE    ████████████████████  100%
 [●] FASTAPI BACKEND    ONLINE    ████████████████████  100%
 [●] POSTGIS SPATIAL    ONLINE    ████████████████████  100%
 [●] NEO4J GRAPH        ONLINE    ████████████████████  100%
 [●] MQTT BROKER        ONLINE    ████████████████████  100%
 ───────────────────────────────────────────────────────────────────
```

```text
 HYDRA-C2 ARCHITECTURE // CLEAN ARCHITECTURE + 7-LAYER STACK
 ══════════════════════════════════════════════════════════════════

 ┌────────────────────────────────────────────────────────────────┐
 │                    L6 — VISUALIZATION LAYER                    │
 │                                                                │
 │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
 │  │  REACT COP   │  │  MILSYMBOL   │  │  LEAFLET MAP         │ │
 │  │  DASHBOARD   │  │  2525B       │  │  + DARK TILES        │ │
 │  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘ │
 └─────────┼─────────────────┼─────────────────────┼─────────────┘
           └─────────────────┼─────────────────────┘
                             │
                      REST / WebSocket
                             │
 ┌───────────────────────────▼──────────────────────────────────┐
 │                    L5 — ANALYTICS ENGINE                      │
 │  Pandas · GeoPandas · scikit-learn · NetworkX · Folium       │
 └───────────────────────────┬──────────────────────────────────┘
                             │
 ┌───────────────────────────▼──────────────────────────────────┐
 │                    L4 — PERSISTENCE LAYER                     │
 │                                                               │
 │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │
 │  │  POSTGIS     │  │  NEO4J       │  │  MQTT BROKER       │  │
 │  │  SPATIAL DB  │  │  GRAPH DB    │  │  (MOSQUITTO)       │  │
 │  └──────┬───────┘  └──────┬───────┘  └─────────┬──────────┘  │
 └─────────┼─────────────────┼────────────────────┼──────────────┘
           │                 │                    │
 ┌─────────▼────┐  ┌────────▼───────┐  ┌─────────▼──────────┐
 │  L0: RF/SDR  │  │  L1: ATAK/TAK  │  │  L2: MESHTASTIC    │
 │  KrakenSDR   │  │  TAK Server    │  │  LoRa Mesh Net     │
 │  RTL-SDR     │  │  CoT Gateway   │  │  Encrypted P2P     │
 └──────────────┘  └────────────────┘  └────────────────────┘
```

## FEATURES
- Real-time Common Operating Picture (COP) with Leaflet + dark CartoDB tiles
- MIL-STD-2525B military symbology via milsymbol
- KrakenSDR direction-finding & RF triangulation
- PostGIS spatial queries (radius search, geofencing)
- Neo4j graph analysis (co-location, network traversal)
- Zero-trust architecture with encrypted mesh transport
- Grafana monitoring dashboards
- Docker Compose one-command deployment

## QUICK START

```bash
# Clone & deploy
git clone https://github.com/hugefisco94/hydra-c2.git
cd hydra-c2

# Option 1: Full stack via Docker Compose
docker compose -f deploy/docker/docker-compose.yml up -d

# Option 2: Standalone local mode (no external DBs required)
pip install -e .
python -m hydra_c2.standalone

# Seed operational data
python scripts/seed_data.py --direct

# Open COP Dashboard
open https://hugefisco94.github.io/hydra-c2/
```

## API ENDPOINTS

```text
 METHOD │ ENDPOINT                       │ DESCRIPTION
 ───────┼────────────────────────────────┼──────────────────────────────
 GET    │ /health                        │ System health & layer status
 GET    │ /api/v1/actors                 │ List actors (spatial filter)
 GET    │ /api/v1/actors/{id}/network    │ Neo4j network traversal
 POST   │ /api/v1/cot/ingest            │ CoT XML ingestion
 GET    │ /api/v1/sdr/detections         │ SDR transmission detections
 POST   │ /api/v1/geofences             │ Create geofence polygon
 POST   │ /api/v1/geofences/check       │ Check geofence breach
```

## TECH STACK

```text
 LAYER     │ TECHNOLOGY
 ──────────┼───────────────────────────────────────────────────────
 DOMAIN    │ Python 3.12 · FastAPI · Pydantic · structlog
 SPATIAL   │ PostgreSQL 16 · PostGIS 3.4 · GeoAlchemy2
 GRAPH     │ Neo4j 5.x · Cypher · Bolt protocol
 FRONTEND  │ React 19 · TypeScript · Vite 7 · Tailwind CSS 4
 MAPPING   │ Leaflet · react-leaflet v5 · milsymbol v3
 MESSAGING │ Mosquitto MQTT · WebSocket
 INFRA     │ Docker Compose · AMD MI300X GPU · DO Cloud
 CI/CD     │ Harness.io · GitHub Pages · gh-pages deploy
```

## LICENSE
MIT

```text
 ─────────────────────────────────────────────────────────────────
 ⚠  UNCLASSIFIED // OPEN SOURCE // FOR AUTHORIZED USE ONLY  ⚠
 ─────────────────────────────────────────────────────────────────
```
