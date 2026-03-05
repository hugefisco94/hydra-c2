"""
L3: Intelligence Retrieval Layer
ColBERT-inspired Late Interaction + OSINT Integration
MDO-NEXUS-OODA-HYDRA v3.0

Architecture ref: D:\\MDO-NEXUS-OODA-HYDRA-v3.0.md
Learning sources:
  - Late Interaction Retrieval (ColBERT/ColPali/ColQwen, MaxSim operator)
  - ODNI IC OSINT Strategy 2024-2026 (INT of First Resort, federated enterprise)
  - Weaviate Agent Skills (multi-collection routing, query decomposition, reranking)
  - D:\\requirement.MD (strategic-osint v2, RAND RRA573-1)
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Domain primitives
# ---------------------------------------------------------------------------


class SourceType(Enum):
    """OSINT source classification per ODNI INT taxonomy."""
    SIGINT = "SIGINT"       # L0 SDR feeds
    GEOINT = "GEOINT"       # L1 TAK positions
    COMINT = "COMINT"       # L2 Mesh messages
    OSINT  = "OSINT"        # Open-source (web, docs, social)
    HUMINT = "HUMINT"       # Human intelligence (manual entry)
    MASINT = "MASINT"       # Measurement & signature


@dataclass
class IntelEntry:
    """
    Immutable intelligence entry (Tape pattern).
    Once created, content is never mutated — append-only.
    """
    entry_id: str
    source_type: SourceType
    content: str
    timestamp: float = field(default_factory=time.time)
    geo_lat: float | None = None
    geo_lon: float | None = None
    confidence: float = 1.0          # 0.0 – 1.0
    token_embeddings: list[list[float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.entry_id:
            digest = hashlib.sha256(
                f"{self.content}{self.timestamp}".encode()
            ).hexdigest()[:16]
            object.__setattr__(self, "entry_id", digest)

    @property
    def token_count(self) -> int:
        return len(self.token_embeddings)


@dataclass
class QueryResult:
    """Result from MaxSim retrieval."""
    entry: IntelEntry
    score: float
    matched_tokens: int


# ---------------------------------------------------------------------------
# Late Interaction Retrieval (ColBERT MaxSim pattern)
# S(Q, D) = Σ_{i∈Q} max_{j∈D} (qi · dj)
# ---------------------------------------------------------------------------


class LateInteractionRetriever:
    """
    ColBERT-inspired late interaction retrieval.

    Each query token independently retrieves the most similar document token
    (MaxSim), then scores are summed over all query tokens.

    Reference: ColBERT (Khattab & Zaharia 2020),
               ColPali (Faysse et al. 2024 — PDF images, no OCR),
               ColQwen (Qwen2-VL Vision Encoder).

    In HYDRA context: retrieves relevant intelligence entries for OODA Orient
    phase without requiring OCR or explicit chunking.
    """

    def __init__(self, embedding_dim: int = 128) -> None:
        self._dim = embedding_dim
        self._index: list[IntelEntry] = []

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def index(self, entry: IntelEntry) -> None:
        """Add IntelEntry to offline index."""
        if not entry.token_embeddings:
            entry = self._embed(entry)
        self._index.append(entry)

    def index_batch(self, entries: list[IntelEntry]) -> None:
        for e in entries:
            self.index(e)

    # ------------------------------------------------------------------
    # Online MaxSim search
    # ------------------------------------------------------------------

    def search(
        self,
        query_tokens: list[list[float]],
        top_k: int = 5,
        source_filter: SourceType | None = None,
    ) -> list[QueryResult]:
        """
        Late interaction search.
        S(Q, D) = Σ_{i∈Q} max_{j∈D} (qi · dj)
        """
        candidates = self._index
        if source_filter is not None:
            candidates = [e for e in candidates if e.source_type == source_filter]

        results: list[QueryResult] = []
        for entry in candidates:
            if not entry.token_embeddings:
                continue
            score = self._maxsim(query_tokens, entry.token_embeddings)
            matched = len(query_tokens)
            results.append(QueryResult(entry=entry, score=score, matched_tokens=matched))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dot(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    def _maxsim(
        self,
        query_tokens: list[list[float]],
        doc_tokens: list[list[float]],
    ) -> float:
        """Sum of per-query-token maximum similarity scores."""
        total = 0.0
        for qi in query_tokens:
            max_sim = max(
                (self._dot(qi, dj) for dj in doc_tokens),
                default=0.0,
            )
            total += max_sim
        return total

    def _embed(self, entry: IntelEntry) -> IntelEntry:
        """
        Stub tokenizer + embedding.
        Production: replace with sentence-transformers or ColBERT checkpoint.
        ColPali variant: treat PDF pages as images → ViT patch tokens.
        """
        words = entry.content.lower().split()[:64]
        embeddings: list[list[float]] = []
        for w in words:
            seed = int(hashlib.md5(w.encode()).hexdigest(), 16)
            vec = [
                math.sin(seed * (i + 1) * 0.001) for i in range(self._dim)
            ]
            norm = math.sqrt(sum(x**2 for x in vec)) or 1.0
            embeddings.append([x / norm for x in vec])
        # Return new entry with embeddings (immutable pattern)
        return IntelEntry(
            entry_id=entry.entry_id,
            source_type=entry.source_type,
            content=entry.content,
            timestamp=entry.timestamp,
            geo_lat=entry.geo_lat,
            geo_lon=entry.geo_lon,
            confidence=entry.confidence,
            token_embeddings=embeddings,
        )

    @property
    def index_size(self) -> int:
        return len(self._index)


# ---------------------------------------------------------------------------
# OSINT Collector (INT of First Resort — ODNI 2024-2026)
# ---------------------------------------------------------------------------


class OsintCollector:
    """
    Open-source intelligence collection.
    Implements ODNI OSINT Strategy 2024-2026:
      - INT of First Resort: OSINT before classified collection
      - Federated enterprise: distributed collection nodes
      - Information cycle: collect → process → analyze → disseminate

    Integrates with strategic-osint v2 skill (D:\requirement.MD).
    """

    def __init__(self, retriever: LateInteractionRetriever) -> None:
        self._retriever = retriever
        self._collection_log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Collection interface
    # ------------------------------------------------------------------

    def ingest_raw(
        self,
        content: str,
        source_type: SourceType = SourceType.OSINT,
        geo_lat: float | None = None,
        geo_lon: float | None = None,
        confidence: float = 0.8,
    ) -> IntelEntry:
        """
        Ingest raw intelligence. Auto-embeds and indexes.
        INT of First Resort: OSINT entries have priority flag.
        """
        entry = IntelEntry(
            entry_id="",
            source_type=source_type,
            content=content,
            geo_lat=geo_lat,
            geo_lon=geo_lon,
            confidence=confidence,
        )
        self._retriever.index(entry)
        self._collection_log.append({
            "entry_id": entry.entry_id,
            "source": source_type.value,
            "ts": entry.timestamp,
            "len": len(content),
        })
        return entry

    def ingest_sigint(self, frequency_mhz: float, signal_data: str, bearing: float | None = None) -> IntelEntry:
        """Ingest L0 KrakenSDR/HackRF signal intercept."""
        content = f"SIGINT freq={frequency_mhz}MHz "
        if bearing is not None:
            content += f"bearing={bearing:.1f}deg "
        content += signal_data[:512]
        return self.ingest_raw(content, SourceType.SIGINT, confidence=0.9)

    def ingest_tak_position(self, callsign: str, lat: float, lon: float, message: str = "") -> IntelEntry:
        """Ingest L1 TAK CoT position report."""
        content = f"GEOINT callsign={callsign} pos=({lat:.5f},{lon:.5f}) {message}"
        return self.ingest_raw(content, SourceType.GEOINT, geo_lat=lat, geo_lon=lon, confidence=0.95)

    def ingest_mesh_message(self, node_id: str, message: str) -> IntelEntry:
        """Ingest L2 Meshtastic mesh message."""
        content = f"COMINT node={node_id} msg={message[:256]}"
        return self.ingest_raw(content, SourceType.COMINT, confidence=0.85)

    # ------------------------------------------------------------------
    # Query interface (Weaviate-style multi-collection routing)
    # ------------------------------------------------------------------

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        source_filter: SourceType | None = None,
    ) -> list[QueryResult]:
        """
        Query intelligence index via late interaction MaxSim.
        Multi-collection routing: no source_filter = search all collections.
        """
        query_tokens = self._retriever._embed(
            IntelEntry(
                entry_id="q",
                source_type=SourceType.OSINT,
                content=query_text,
            )
        ).token_embeddings
        return self._retriever.search(query_tokens, top_k=top_k, source_filter=source_filter)

    def collection_stats(self) -> dict[str, Any]:
        """Weaviate-style collection statistics."""
        by_source: dict[str, int] = {}
        for log in self._collection_log:
            by_source[log["source"]] = by_source.get(log["source"], 0) + 1
        return {
            "total_entries": self._retriever.index_size,
            "by_source": by_source,
            "collection_log_size": len(self._collection_log),
        }


# ---------------------------------------------------------------------------
# Kill Web Intelligence Fusion (RAND RRA573-1 / DARPA Mosaic)
# ---------------------------------------------------------------------------


class KillWebFusion:
    """
    Multi-source intelligence fusion for Kill Web.

    Mosaic Warfare principle: decompose into small, composable kill nodes.
    Any node can contribute intelligence fragments; fusion reconstitutes
    the operational picture.

    STITCHES integration: composable software-defined Kill Chain assembly.
    """

    def __init__(self, collector: OsintCollector) -> None:
        self._collector = collector
        self._fusion_anchors: list[dict[str, Any]] = []

    def fuse(
        self,
        query: str,
        top_k: int = 10,
    ) -> dict[str, Any]:
        """
        Multi-domain intelligence fusion.
        Returns fused picture with confidence aggregation.
        """
        results = self._collector.query(query, top_k=top_k)

        # Aggregate by source type (federated enterprise pattern)
        by_source: dict[str, list[QueryResult]] = {}
        for r in results:
            key = r.entry.source_type.value
            by_source.setdefault(key, []).append(r)

        # Confidence-weighted aggregation (Lancaster's law analog)
        # Aggregate power = Σ (score × confidence)
        aggregate_score = sum(
            r.score * r.entry.confidence for r in results
        )

        # Create fusion anchor (Tape pattern)
        anchor = {
            "query": query,
            "aggregate_score": aggregate_score,
            "source_count": len(by_source),
            "entry_count": len(results),
            "sources": {k: len(v) for k, v in by_source.items()},
            "timestamp": time.time(),
        }
        self._fusion_anchors.append(anchor)

        return {
            "anchor": anchor,
            "results": results,
            "kill_web_coverage": len(by_source) / len(SourceType),
        }

    @property
    def anchor_count(self) -> int:
        return len(self._fusion_anchors)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------


def create_intelligence_layer() -> tuple[LateInteractionRetriever, OsintCollector, KillWebFusion]:
    """
    Factory: create wired L3 Intelligence layer.
    Returns (retriever, collector, fusion) tuple for DI container.
    """
    retriever = LateInteractionRetriever(embedding_dim=128)
    collector = OsintCollector(retriever=retriever)
    fusion = KillWebFusion(collector=collector)
    return retriever, collector, fusion


__all__ = [
    "SourceType",
    "IntelEntry",
    "QueryResult",
    "LateInteractionRetriever",
    "OsintCollector",
    "KillWebFusion",
    "create_intelligence_layer",
]
