# HYDRA-C2

**Hybrid Universal Dynamic Reconnaissance Architecture**  
Open-source Multi-Domain C2 System

## 7-Layer Architecture

| Layer | Component | Technology |
|-------|-----------|------------|
| L0 | Physical/RF | KrakenSDR, RTL-SDR, HackRF |
| L1 | Edge Computing | ATAK, TAK Server |
| L2 | Mesh Transport | Meshtastic LoRa |
| L3 | Data Ingestion | MQTT (Mosquitto), Kafka |
| L4 | Persistence | PostgreSQL/PostGIS + Neo4j |
| L5 | Analytics | Databricks/Spark, Python ML |
| L6 | Visualization | QGIS, WebTAK, Grafana |

## Quick Start

```bash
# Start infrastructure
docker compose -f deploy/docker/docker-compose.yml up -d

# Run API
uv run uvicorn hydra_c2.presentation.web.api.main:app --reload

# Run tests
uv run pytest tests/ -v
```

## License

MIT
