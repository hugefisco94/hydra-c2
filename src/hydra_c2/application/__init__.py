"""Application Layer — Use cases and service orchestration.

This layer coordinates domain entities and infrastructure to fulfill
user requirements. It depends on domain interfaces only (never on
concrete infrastructure).

Use Cases:
- IngestCotUseCase: TAK Server CoT → Parse → Persist → Publish
- IngestSdrUseCase: SDR data → Parse → Persist → Publish
- AnalyzeNetworkUseCase: Neo4j graph analysis queries
- GeofenceCheckUseCase: Spatial breach detection
- TriangulateUseCase: KrakenSDR multi-station RDF fusion
"""
