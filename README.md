
 ██╗  ██╗██╗   ██╗██████╗ ██████╗  █████╗       ██████╗██████╗
 ██║  ██║╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗     ██╔════╝╚════██╗
 ███████║ ╚████╔╝ ██║  ██║██████╔╝███████║     ██║      █████╔╝
 ██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗██╔══██║     ██║     ██╔═══╝
 ██║  ██║   ██║   ██████╔╝██║  ██║██║  ██║     ╚██████╗███████╗
 ╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝      ╚═════╝╚══════╝

 ┌──────────────────────────────────────────────────────────────────┐
 │  HYDRA-C2 // OSINT-DRIVEN BAYESIAN THREAT INTELLIGENCE          │
 │  Hybrid Universal Dynamic Reconnaissance Architecture            │
 │  CLASSIFICATION: UNCLASSIFIED // OPEN SOURCE                     │
 └──────────────────────────────────────────────────────────────────┘

<p align="center">
  <a href="https://hugefisco94.github.io/hydra-c2/"><img src="https://img.shields.io/badge/COP_DASHBOARD-LIVE-39ff14?style=for-the-badge&labelColor=0a0a0f" alt="Live Dashboard"></a>
  <img src="https://img.shields.io/badge/VERSION-0.4.0-blue?style=for-the-badge&labelColor=0a0a0f" alt="Version 0.4.0">
  <img src="https://img.shields.io/badge/OSINT-GDELT_+_OPENSKY-ff4d4f?style=for-the-badge&labelColor=0a0a0f" alt="OSINT Fusion">
  <img src="https://img.shields.io/badge/API-16_ENDPOINTS-00b4d8?style=for-the-badge&labelColor=0a0a0f" alt="16 Endpoints">
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

> **OSINT-driven Bayesian threat intelligence Common Operating Picture.**
> Real-time GDELT/OpenSky fusion, causal DAG inference, MIL-STD-2525B symbology,
> and systems-theoretic assessment engine for multi-domain situational awareness
> across Land, Air, Sea, Subsurface, Space, and Cyber domains.

```
 SYSTEM STATUS ──────────────────────────────────────────────────────
 [●] COP DASHBOARD     OPERATIONAL   ████████████████████  OSINT COP
 [●] FASTAPI BACKEND   OPERATIONAL   ████████████████████  16 ROUTES
 [●] GDELT v2 FEED     CONNECTED     ████████████████████  DOC API
 [●] OPENSKY NETWORK   CONNECTED     ████████████████████  STATE-VEC
 [●] BAYESIAN DAG      OPERATIONAL   ████████████████████  CAUSAL
 [●] POSTGIS SPATIAL   CONNECTED     ████████████████████  GEOFENCE
 [●] NEO4J GRAPH       CONNECTED     ████████████████████  LINK-ANAL
 [●] HTTPS PROXY       OPERATIONAL   ████████████████████  CADDY/SSL
 ────────────────────────────────────────────────────────────────────
```

## LIVE DASHBOARD

**[`https://hugefisco94.github.io/hydra-c2/`](https://hugefisco94.github.io/hydra-c2/)**

Iran/Middle East OSINT theater with real-time multi-domain actors and
Bayesian causal threat assessment fusing GDELT geopolitical events
with OpenSky military flight tracking:

| Affiliation | Description                                                  |
|:------------|:-------------------------------------------------------------|
| HOSTILE     | Ballistic TELs, patrol boats, combat aircraft, EW platforms  |
| FRIENDLY    | Naval task groups, air patrol, ground QRF, cyber defense     |
| NEUTRAL     | Commercial aviation, maritime shipping, SATCOM relays        |
| UNKNOWN     | Unidentified UAS, submarine contacts, SIGINT signatures      |

---

## OSINT INTELLIGENCE ENGINE

```
 BAYESIAN CAUSAL DAG ── GDELT/OPENSKY FUSION
 ═══════════════════════════════════════════════════════════════

   GDELT v2 DOC API                    OpenSky Network
   ┌─────────────────┐                 ┌─────────────────┐
   │ Geopolitical     │                 │ ADS-B State     │
   │ Event Monitoring │                 │ Vector Tracking │
   │ (tone analysis)  │                 │ (mil callsigns) │
   └────────┬────────┘                 └────────┬────────┘
            │                                    │
            ▼                                    ▼
   ┌─────────────────┐                 ┌─────────────────┐
   │ GDELT_TONE_AVG  │                 │ AIRCRAFT_DENSITY │
   │ (sentiment node) │                 │ (posture node)   │
   └────────┬────────┘                 └────────┬────────┘
            │ 0.35 weight                       │ 0.25 weight
            ▼                                    ▼
   ┌─────────────────┐                 ┌─────────────────┐
   │ ESCALATION_PROB  │                 │ MIL_POSTURE_IDX  │
   │ P(escalation|    │                 │ P(posture|       │
   │   tone,history)  │                 │   density,type)  │
   └────────┬────────┘                 └────────┬────────┘
            │                                    │
            └──────────────┬─────────────────────┘
                           ▼ 0.40 weight
                  ┌─────────────────┐
                  │ COMPOSITE_SCORE  │
                  │ Bayesian fusion  │
                  │ → THREAT_LEVEL   │
                  └─────────────────┘
                    CRITICAL | HIGH | ELEVATED | LOW | MINIMAL
```

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
 │  ├─ Strategic Zones (Strait of Hormuz / Persian Gulf)      │
 │  ├─ Actor Movement Trails (domain-adaptive)                │
 │  └─ CRT Scanline Effect (toggle)                           │
 │                                                             │
 │  Sidebar Panels                                             │
 │  ├─ Force Status (by affiliation + domain)                 │
 │  ├─ Threat Assessment Board (CRITICAL / HIGH / MEDIUM)     │
 │  ├─ OSINT Intel Panel (Bayesian composite + causal factors)│
 │  └─ OSINT Feed Activity (GDELT / OpenSky breakdown)        │
 └────────────────────────┬────────────────────────────────────┘
                          │  HTTPS / REST
 ┌────────────────────────▼────────────────────────────────────┐
 │                    L5 — ANALYTICS                            │
 │                                                             │
 │  FastAPI Backend (16 endpoints)                             │
 │  ├─ Threat Scoring Engine (proximity + capability + intent) │
 │  ├─ Bayesian Causal DAG (GDELT tone → escalation prob)     │
 │  ├─ OSINT Feed Aggregator (GDELT v2 DOC + OpenSky REST)   │
 │  ├─ Military Posture Index (flight density analysis)       │
 │  ├─ Force Composition Analytics                             │
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
| `/health`                         |  GET   | System health & infrastructure status    |
| `/api/v1/actors`                  |  GET   | All actors with spatial positions         |
| `/api/v1/actors/{id}`             |  GET   | Single actor by ID                       |
| `/api/v1/actors/{id}/network`     |  GET   | Neo4j network traversal for actor        |
| `/api/v1/cot/ingest`              |  POST  | Cursor-on-Target XML ingestion           |
| `/api/v1/sdr/detections`          |  GET   | SDR transmission detections              |
| `/api/v1/geofences`               |  POST  | Create geofence polygon                  |
| `/api/v1/geofences/check`         |  POST  | Check geofence breach                    |

### Threat & Analytics

| Endpoint                          | Method | Description                              |
|:----------------------------------|:------:|:-----------------------------------------|
| `/api/v1/threat-assessment`       |  GET   | Actor threat scoring (composite scores)  |
| `/api/v1/analytics/overview`      |  GET   | Force composition by affiliation/domain  |
| `/api/v1/sdr/reference`           |  GET   | URH-derived modulation reference         |

### OSINT Intelligence

| Endpoint                              | Method | Description                              |
|:--------------------------------------|:------:|:-----------------------------------------|
| `/api/v1/osint/feeds`                 |  GET   | GDELT + OpenSky aggregated feed events   |
| `/api/v1/osint/threat-assessment`     |  GET   | Bayesian causal DAG threat level         |

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
 OSINT            GDELT v2 DOC feed · OpenSky state vectors · Fusion
 BAYESIAN         Causal DAG inference · Escalation probability
 POSTURE          Military posture index · Flight density analysis
 STRATEGIC        Strait of Hormuz zone · Persian Gulf monitoring
 TRAILS           Domain-adaptive movement trails (AIR/SEA/LAND)
 SIGINT           ADS-B decode model · AIS vessel model · SDR chain
 ANALYTICS        Force composition · Threat board · Feed breakdown
 RESILIENCE       Error boundary · Connection banner · Polling retry
 ────────────────────────────────────────────────────────────────
```

---

## DESIGN PHILOSOPHY

HYDRA-C2 is grounded in systems-theoretic foundations:

```
 THEORETICAL FRAMEWORK ─────────────────────────────────────────
 CYBERNETICS          Wiener (feedback) · Ashby (requisite variety)
 2ND-ORDER            von Foerster (observing systems) · autopoiesis
 VIABLE SYSTEM        Beer VSM mapping → 5-system architecture
 SYSTEM DYNAMICS      Forrester (stock-flow) · Sterman (feedback)
 SOCIAL SYSTEMS       Luhmann (functional differentiation · closure)
 ────────────────────────────────────────────────────────────────
```

See [`docs/DESIGN_PHILOSOPHY.md`](docs/DESIGN_PHILOSOPHY.md) for the complete
design document with 24 academic references, VSM mapping, OODA phase mapping,
and MDO-NEXUS-OODA compatibility contract.

---

## QUICK START

```bash
# Clone
git clone https://github.com/hugefisco94/hydra-c2.git
cd hydra-c2

# Deploy backend (PostGIS, Neo4j, MQTT, API)
docker compose -f deploy/docker/docker-compose.yml up -d

# Frontend dev
cd frontend && npm install && npm run dev

# Production build & deploy
npm run build && npx gh-pages -d dist --no-history
```

---

## TECH STACK

```
 DOMAIN      │  Python 3.12 · FastAPI · Pydantic · structlog
 OSINT       │  GDELT v2 DOC API · OpenSky Network REST API
 INFERENCE   │  Bayesian Causal DAG · Weighted Fusion (0.35/0.25/0.40)
 SPATIAL     │  PostgreSQL 16 · PostGIS 3.4 · GeoAlchemy2
 GRAPH       │  Neo4j 5.x · Cypher · Bolt protocol
 FRONTEND    │  React 19 · TypeScript 5 · Vite 7 · Tailwind CSS 4
 STATE       │  Zustand 5 (immutable selectors · memoized filters)
 MAPPING     │  Leaflet · react-leaflet v5 · milsymbol v3
 MESSAGING   │  Mosquitto MQTT · WebSocket
 PROXY       │  Caddy (auto-HTTPS via sslip.io)
 INFRA       │  Docker Compose · AMD MI300X GPU · DO Cloud
 CI/CD       │  Harness.io · GitHub Pages · gh-pages deploy
```

---

## MDO-NEXUS-OODA COMPATIBILITY

HYDRA-C2 maintains modular compatibility with the
[MDO-NEXUS-OODA](https://github.com/hugefisco94/mdo-command-center) engine:

```
 MQTT TOPIC CONTRACT ───────────────────────────────────────────
 hydra/cot/{type}           CoT position reports
 hydra/sdr/rdf|adsb|ais     Signal intelligence
 hydra/graph/network         Neo4j topology events
 hydra/osint/gdelt           GDELT event stream
 hydra/osint/opensky         OpenSky state vectors
 ────────────────────────────────────────────────────────────────
```

The OSINT intelligence layer maps directly to MDO OODA phases:
OBSERVE (GDELT/OpenSky collection) / ORIENT (Bayesian DAG fusion) /
DECIDE (threat classification) / ACT (COP visualization).

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
