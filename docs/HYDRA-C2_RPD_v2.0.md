# HYDRA-C2 Requirements & Planning Document v2.0

**Document ID:** HYDRA-C2-RPD-2026-002  
**Date:** 2026-03-05  
**Classification:** UNCLASSIFIED // FOR OFFICIAL USE ONLY  
**Status:** IMPLEMENTED — Phase 1-2 Complete, Phase 3-4 Verified & Deployed

---

## 1. BLUF (Bottom Line Up Front)

HYDRA-C2 (Hybrid Universal Dynamic Reconnaissance Architecture — Command & Control) is an open-source, multi-domain C2 system implementing 7-layer Clean Architecture. **Phase 1 (Design) through Phase 4 (Deploy) are complete.** The system is operational on both local development (Windows 11 Docker) and cloud infrastructure (DigitalOcean GPU droplet at 134.199.207.172:8080). Core layers L3 (Data Ingestion), L4 (Persistence), and L6 (Visualization) are connected and operational. Layers L0 (SDR/RF), L1 (Edge), L2 (Mesh), and L5 (Spark/ML) are planned for future phases.

---

## 2. System Overview

### 2.1 Architecture — 7-Layer Stack

```
┌──────────────────────────────────────────────────────┐
│  L6  Visualization     │ Grafana, FastAPI WebUI       │ ✅ OPERATIONAL
│  L5  Analytics          │ Spark, ML (Isolation Forest) │ ⏳ PLANNED
│  L4  Persistence        │ PostGIS 16, Neo4j 5          │ ✅ CONNECTED
│  L3  Data Ingestion     │ MQTT (Mosquitto 2), TAK      │ ✅ CONNECTED
│  L2  Mesh Transport     │ Meshtastic, LoRa mesh        │ ⏳ PLANNED
│  L1  Edge Computing     │ Raspberry Pi, Jetson          │ ⏳ PLANNED
│  L0  Physical / RF      │ RTL-SDR, KrakenSDR, HackRF   │ ⏳ PLANNED
└──────────────────────────────────────────────────────┘
```

### 2.2 Clean Architecture Layers (Software)

| Layer | Status | Components |
|-------|--------|------------|
| **Domain** | ✅ Complete | Entities (Actor, Event, Transmission, GeoPosition), Interfaces (4 repos + 2 messaging) |
| **Application** | ✅ Complete | 5 Use Cases (IngestCot, IngestSdr, CheckGeofence, TriangulateSource, QueryNetwork) |
| **Infrastructure** | ✅ Complete | PostGIS repos (544 LOC), Neo4j service (205 LOC), MQTT client, schema DDLs |
| **Presentation** | ✅ Complete | FastAPI (282 LOC, 8 endpoints), CORS, DI container |

---

## 3. Implementation Status

### 3.1 Completed Components

- **4 Domain Entities** with MIL-STD-2525B SIDC support
- **4 Repository Interfaces** (Actor, Event, Transmission, Geofence) + 2 Messaging Interfaces
- **5 Application Use Cases** with @dataclass result objects and structlog logging
- **PostGIS Repository** (544 lines) — full CRUD with ST_DWithin/ST_MakePoint spatial queries
- **Neo4j Graph Service** (205 lines) — actor nodes, event relationships, co-location, network traversal
- **MQTT Publisher/Subscriber** — paho-mqtt async wrappers
- **FastAPI REST API** (282 lines) — 8 endpoints with DI container integration
- **DI Container** (157 lines) — composition root wiring all infrastructure
- **Docker Compose** — 5 services (PostGIS, Neo4j, Mosquitto, Grafana, API)
- **Multi-stage Dockerfile** — Python 3.12-slim, uv package manager, non-root user

### 3.2 Test Results

| Category | Result |
|----------|--------|
| Unit Tests | 11/11 PASSED (GeoPosition: 6, Actor: 5) |
| Module Imports | 18/18 OK (full chain validated) |
| FastAPI Load | ✅ App loads, title: "HYDRA-C2 API v0.1.0" |
| Infrastructure | ✅ PostGIS + Neo4j + MQTT all connected |

---

## 4. Deployment Architecture

### 4.1 Local Development (Windows 11)

| Container | Image | Port | Status |
|-----------|-------|------|--------|
| hydra-postgis | postgis/postgis:16-3.4 | 5432 | ✅ Healthy |
| hydra-neo4j | neo4j:5-community | 7474, 7687 | ✅ Healthy |
| hydra-mqtt | eclipse-mosquitto:2 | 1883, 9001 | ✅ Healthy |
| hydra-grafana | grafana/grafana-oss:latest | 3000 | ✅ Running |
| hydra-api | docker-api (custom) | 8000 | ✅ Healthy |

### 4.2 Cloud Deployment (DigitalOcean GPU)

| Parameter | Value |
|-----------|-------|
| **Public IP** | 134.199.207.172 |
| **API Port** | 8080 (mapped to internal 8000) |
| **GPU** | AMD Instinct MI300X (ROCm 7.0) |
| **RAM** | 235 GB |
| **Disk** | 697 GB (631 GB free) |
| **OS** | Ubuntu 24.04.3 LTS |
| **Docker** | 28.4.0 + Compose v5.1.0 |

All 5 containers healthy on cloud deployment. API accessible via `http://134.199.207.172:8080/health`.

---

## 5. API Reference

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| GET | `/health` | System health + layer status | ✅ Operational |
| POST | `/api/v1/cot/ingest` | Ingest CoT XML from TAK Server | ⚠️ GeoAlchemy2 fix needed |
| GET | `/api/v1/actors` | List all tracked actors | ✅ Operational |
| GET | `/api/v1/actors/{id}/network` | Query actor's Neo4j network graph | ✅ Operational |
| GET | `/api/v1/sdr/detections` | List SDR signal detections | ✅ Operational |
| POST | `/api/v1/geofences` | Create geofence zone | ⚠️ API interface adjustment |
| POST | `/api/v1/geofences/check` | Check position against geofences | ⚠️ API interface adjustment |
| GET | `/docs` | Swagger/OpenAPI documentation | ✅ Operational |

---

## 6. Technology Stack

| Category | Technology | Version |
|----------|-----------|---------|
| **Language** | Python | 3.12 (Docker), 3.14 (local dev) |
| **Web Framework** | FastAPI | 0.135+ |
| **ORM** | SQLAlchemy + GeoAlchemy2 | 2.0 + 0.18 |
| **Async DB Driver** | asyncpg | 0.31 |
| **Graph Database** | Neo4j (Python driver) | 6.1 |
| **Message Broker** | paho-mqtt | 2.1 |
| **Config** | pydantic-settings | 2.13 |
| **Logging** | structlog | 25.5 |
| **Spatial** | PostGIS, Shapely, GeoPandas | 3.4, 2.1, 1.1 |
| **ML** | scikit-learn, NetworkX | 1.8, 3.6 |
| **Build** | hatchling + uv | latest |
| **Container** | Docker Compose | 5.1 |

---

## 7. Synergy Integration

31 GitHub repositories evaluated against 7-layer architecture. Top synergy candidates:
- **mission-control** (17/35) — C2 orchestration dashboard
- **ghidra** (16/35) — SIGINT/protocol reverse engineering
- **ruvector** (16/35) — Runtime container security
- **CyberStrikeAI** (15/35) — AI threat analysis
- **datasette** (15/35) — Data exploration overlay

Full evaluation: `docs/synergy-evaluation.md`

---

## 8. Roadmap

### Phase 2 (Next) — Sensor Integration
- [ ] L0: RTL-SDR driver integration (pyrtlsdr)
- [ ] L0: KrakenSDR direction-finding
- [ ] L1: Raspberry Pi edge node deployment
- [ ] L2: Meshtastic mesh transport layer

### Phase 3 — Analytics & ML
- [ ] L5: Spark/Delta Lake pipeline on DO GPU
- [ ] L5: Isolation Forest anomaly detection
- [ ] L5: DBSCAN geospatial clustering
- [ ] L5: Neo4j graph analytics (centrality, community detection)

### Phase 4 — Production Hardening
- [ ] TLS/mTLS for all service communication
- [ ] RBAC (Role-Based Access Control)
- [ ] Integration tests with testcontainers
- [ ] CI/CD pipeline (Harness.io)
- [ ] Grafana dashboards for COP (Common Operating Picture)

---

## 9. File Structure

```
hydra-c2/
├── src/hydra_c2/
│   ├── domain/           # Entities + Interfaces (ABCs)
│   ├── application/      # Use Cases
│   ├── infrastructure/   # PostGIS, Neo4j, MQTT implementations
│   ├── presentation/     # FastAPI REST API
│   ├── config.py         # Pydantic Settings
│   └── container.py      # DI Composition Root
├── deploy/docker/
│   ├── docker-compose.yml
│   ├── Dockerfile.api
│   └── mosquitto/
├── tests/unit/
├── docs/
├── pyproject.toml
└── README.md
```

---

**END OF DOCUMENT**
