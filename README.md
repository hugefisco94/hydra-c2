
 ██╗  ██╗██╗   ██╗██████╗ ██████╗  █████╗       ██████╗██████╗ 
 ██║  ██║╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗     ██╔════╝╚════██╗
 ███████║ ╚████╔╝ ██║  ██║██████╔╝███████║     ██║      █████╔╝
 ██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗██╔══██║     ██║     ██╔═══╝ 
 ██║  ██║   ██║   ██████╔╝██║  ██║██║  ██║     ╚██████╗███████╗
 ╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝      ╚═════╝╚══════╝

 ┌──────────────────────────────────────────────────────────────────┐
 │  HYDRA-C2 // MULTI-DOMAIN COMMAND & CONTROL FRAMEWORK            │
 │  Hybrid Universal Dynamic Reconnaissance Architecture            │
 │  CLASSIFICATION: UNCLASSIFIED // OPEN SOURCE                     │
 └──────────────────────────────────────────────────────────────────┘

<p align="center">
  <a href="https://hugefisco94.github.io/hydra-c2/"><img src="https://img.shields.io/badge/COP_DASHBOARD-LIVE-39ff14?style=for-the-badge&labelColor=0a0a0f" alt="Live Dashboard"></a>
  <img src="https://img.shields.io/badge/VERSION-0.2.0-blue?style=for-the-badge&labelColor=0a0a0f" alt="Version 0.2.0">
  <img src="https://img.shields.io/badge/ACTORS-25-ff4d4f?style=for-the-badge&labelColor=0a0a0f" alt="25 Actors">
  <img src="https://img.shields.io/badge/API-18_ENDPOINTS-00b4d8?style=for-the-badge&labelColor=0a0a0f" alt="18 Endpoints">
  <img src="https://img.shields.io/badge/LICENSE-MIT-blue?style=for-the-badge&labelColor=0a0a0f" alt="License MIT">
</p>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/React_19-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/TypeScript_5-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/PostGIS_3.4-336791?style=flat-square&logo=postgresql&logoColor=white" alt="PostGIS">
  <img src="https://img.shields.io/badge/Neo4j_5-008CC1?style=flat-square&logo=neo4j&logoColor=white" alt="Neo4j">
  <img src="https://img.shields.io/badge/Leaflet-199900?style=flat-square&logo=leaflet&logoColor=white" alt="Leaflet">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
</p>

---

> **Multi-Domain Operations (MDO) Command & Control framework.**
> Real-time Common Operating Picture with MIL-STD-2525B symbology,
> OODA cycle assessment, kill-web topology, and force-package management
> across Land, Air, Sea, Cyber, Space, and EW domains.

```
 SYSTEM STATUS ──────────────────────────────────────────────────────
 [●] COP DASHBOARD     OPERATIONAL   ████████████████████  25 ACTORS
 [●] FASTAPI BACKEND   OPERATIONAL   ████████████████████  18 ROUTES
 [●] POSTGIS SPATIAL   CONNECTED     ████████████████████  GEOFENCE
 [●] NEO4J GRAPH       CONNECTED     ████████████████████  LINK-ANAL
 [●] MQTT BROKER       CONNECTED     ████████████████████  PUB/SUB
 [●] HTTPS PROXY       OPERATIONAL   ████████████████████  CADDY/SSL
 ────────────────────────────────────────────────────────────────────
```

## LIVE DASHBOARD

**[`https://hugefisco94.github.io/hydra-c2/`](https://hugefisco94.github.io/hydra-c2/)**

Korean Peninsula MDO scenario with 25 real-time actors:

| Affiliation | Count | Examples                                              |
|:------------|------:|:------------------------------------------------------|
| FRIENDLY    |     8 | ALPHA-1 (ROK Army), EAGLE-21 (KF-21), POSEIDON-1     |
| HOSTILE     |     8 | VENOM-5 (TEL), BEAR-1, FOXHOUND-3 (Tu-214R)          |
| NEUTRAL     |     3 | KE-801 (Korean Air), JADE-EXPRESS (Container Ship)    |
| UNKNOWN     |     4 | DARKSTAR-1 (High-Alt Balloon), SHADOW-X (Small UAS)   |

---

## ARCHITECTURE

```
 HYDRA-C2 // 7-LAYER CLEAN ARCHITECTURE
 ═══════════════════════════════════════════════════════════════

 ┌─────────────────────────────────────────────────────────────┐
 │                    L6 — VISUALIZATION                       │
 │                                                             │
 │  React 19 COP Dashboard                                    │
 │  ├─ Leaflet Map (Dark Tactical / Esri Satellite)           │
 │  ├─ MIL-STD-2525B Symbology (milsymbol)                    │
 │  ├─ Threat Range Rings (TEL 80km / AIR 50km / SEA 30km)   │
 │  ├─ Korean DMZ Geofence + MDL Overlay                      │
 │  ├─ Actor Movement Trails (domain-adaptive)                │
 │  └─ CRT Scanline Effect (toggle)                           │
 │                                                             │
 │  Sidebar Panels                                             │
 │  ├─ Force Status (by affiliation + domain)                 │
 │  ├─ Threat Assessment Board (CRITICAL / HIGH / MEDIUM)     │
 │  ├─ MDO Doctrine Status (phase + domain readiness)         │
 │  └─ OODA Cycle Assessment (observe / orient / decide / act)│
 └────────────────────────┬────────────────────────────────────┘
                          │  HTTPS / REST
 ┌────────────────────────▼────────────────────────────────────┐
 │                    L5 — ANALYTICS                            │
 │                                                             │
 │  FastAPI Backend (18 endpoints)                             │
 │  ├─ Threat Scoring Engine (proximity + capability + intent) │
 │  ├─ Force Composition Analytics                             │
 │  ├─ OODA Cycle Degradation Calculator                      │
 │  ├─ Kill-Web Topology (20 nodes / 90 edges)                │
 │  ├─ Force Package Manager (3 packages / 10 assets)         │
 │  ├─ ADS-B State Model (8 DF17 msg types / 21 fields)      │
 │  ├─ AIS Vessel Model (8 msg types / 22 fields)             │
 │  └─ SDR Signal Processing Chain (8 stages / 30+ modes)     │
 └────────────────────────┬────────────────────────────────────┘
                          │
 ┌────────────────────────▼────────────────────────────────────┐
 │                    L4 — PERSISTENCE                          │
 │  PostGIS 3.4          Neo4j 5.x          Mosquitto MQTT    │
 │  (spatial queries)    (graph analysis)   (pub/sub events)  │
 └─────────┬──────────────────┬──────────────────┬────────────┘
           │                  │                  │
 ┌─────────▼───────┐ ┌───────▼────────┐ ┌───────▼───────────┐
 │  L0: RF / SDR   │ │  L1: ATAK/CoT  │ │  L2: Meshtastic   │
 │  KrakenSDR      │ │  TAK Server    │ │  LoRa Mesh        │
 └─────────────────┘ └────────────────┘ └───────────────────┘
```

---

## API ENDPOINTS

### Core Operations

| Endpoint                          | Method | Description                              |
|:----------------------------------|:------:|:-----------------------------------------|
| `/health`                         |  GET   | System health & 7-layer status           |
| `/api/v1/actors`                  |  GET   | All actors with spatial positions         |
| `/api/v1/actors/{id}/network`     |  GET   | Neo4j network traversal for actor        |
| `/api/v1/cot/ingest`              |  POST  | Cursor-on-Target XML ingestion           |
| `/api/v1/sdr/detections`          |  GET   | SDR transmission detections              |
| `/api/v1/geofences`               |  POST  | Create geofence polygon                  |
| `/api/v1/geofences/check`         |  POST  | Check geofence breach                    |

### Threat & Analytics

| Endpoint                          | Method | Description                              |
|:----------------------------------|:------:|:-----------------------------------------|
| `/api/v1/threat-assessment`       |  GET   | 25 actors scored (3 CRITICAL)            |
| `/api/v1/analytics/overview`      |  GET   | Force composition by affiliation/domain  |
| `/api/v1/analytics/distance-matrix` | GET  | Pairwise distance & bearing matrix       |
| `/api/v1/sdr/reference`           |  GET   | URH-derived modulation reference         |

### MDO Doctrine

| Endpoint                          | Method | Description                              |
|:----------------------------------|:------:|:-----------------------------------------|
| `/api/v1/doctrine/mdo-status`     |  GET   | MDO phase & 6-domain readiness           |
| `/api/v1/doctrine/ooda-cycle`     |  GET   | OODA degradation score (0.522)           |
| `/api/v1/doctrine/kill-web`       |  GET   | Kill-web topology (20 nodes / 90 edges)  |
| `/api/v1/doctrine/force-packages` |  GET   | 3 force packages with 10 assets          |

### Signal Intelligence Reference

| Endpoint                          | Method | Description                              |
|:----------------------------------|:------:|:-----------------------------------------|
| `/api/v1/adsb/state-model`        |  GET   | ADS-B DF17 model (8 types / 21 fields)   |
| `/api/v1/ais/vessel-model`        |  GET   | AIS vessel model (8 types / 22 fields)   |
| `/api/v1/signals/processing-chain`|  GET   | 8-stage SDR pipeline (30+ modes)         |

---

## FEATURES

```
 CAPABILITY MATRIX ──────────────────────────────────────────────
 VISUALIZATION    Leaflet COP · Dark/Satellite tiles · Layer toggles
 SYMBOLOGY        MIL-STD-2525B SIDC · Affiliation coloring
 THREAT           Range rings (TEL/AIR/SEA/LAND) · Scoring engine
 GEOFENCE         Korean DMZ polygon · MDL overlay · Panmunjom
 TRAILS           Domain-adaptive movement trails (AIR/SEA/LAND)
 DOCTRINE         MDO status · OODA cycle · Kill-web · Force packages
 SIGINT           ADS-B decode model · AIS vessel model · SDR chain
 ANALYTICS        Force composition · Distance matrix · Threat board
 RESILIENCE       Error boundary · Connection banner · Polling retry
 ────────────────────────────────────────────────────────────────
```

---

## QUICK START

```bash
# Clone
git clone https://github.com/hugefisco94/hydra-c2.git
cd hydra-c2

# Deploy backend (PostGIS, Neo4j, MQTT, Grafana, API)
docker compose -f deploy/docker/docker-compose.yml up -d

# Seed 25 actors
psql -h localhost -U hydra -d hydra_c2 -f scripts/seed.sql
psql -h localhost -U hydra -d hydra_c2 -f scripts/seed_enhanced.sql

# Frontend dev
cd frontend && npm install && npm run dev

# Production build & deploy
npm run build && npx gh-pages -d dist --no-history
```

---

## TECH STACK

```
 DOMAIN      │  Python 3.12 · FastAPI · Pydantic · structlog
 SPATIAL     │  PostgreSQL 16 · PostGIS 3.4 · GeoAlchemy2
 GRAPH       │  Neo4j 5.x · Cypher · Bolt protocol
 FRONTEND    │  React 19 · TypeScript 5 · Vite 7 · Tailwind CSS 4
 MAPPING     │  Leaflet · react-leaflet v5 · milsymbol v3
 MESSAGING   │  Mosquitto MQTT · WebSocket
 PROXY       │  Caddy (auto-HTTPS via sslip.io)
 INFRA       │  Docker Compose · AMD MI300X GPU · DO Cloud
 CI/CD       │  Harness.io · GitHub Pages · gh-pages deploy
```

---

## REFERENCE ANALYSIS

Patterns and protocols extracted from 16 reference repositories:

| Repository          | Domain     | Extracted Pattern                          |
|:--------------------|:-----------|:-------------------------------------------|
| plane-alert-db      | ADS-B      | ICAO hex codes, aircraft type database     |
| panopticon          | AI/C2      | Multi-agent wargaming architecture         |
| urh                 | SDR        | Protocol analysis, modulation types        |
| SDRPlusPlus         | SDR        | Multi-band receiver pipeline               |
| AIS-catcher         | Maritime   | AIS message decoding (8 types)             |
| openwebrx           | SDR        | WebSocket spectrum streaming               |
| noaa-apt            | SIGINT     | NOAA APT satellite image decode            |
| plane-notify        | ADS-B      | Real-time aircraft alerting                |
| airplanejs          | ADS-B      | Mode-S/ADS-B DF17 state model             |
| docker-shipfeeder   | Maritime   | AIS feeding architecture                   |
| palantir-*          | Ontology   | Entity resolution, link analysis           |
| taipy               | Dashboard  | Pipeline-driven analytics UI               |
| mage-ai             | Pipeline   | Data orchestration patterns                |
| prisma              | ORM        | Type-safe database access patterns         |

---

## LICENSE

MIT

```
 ─────────────────────────────────────────────────────────────
 UNCLASSIFIED // OPEN SOURCE // FOR AUTHORIZED USE ONLY
 ─────────────────────────────────────────────────────────────
```
