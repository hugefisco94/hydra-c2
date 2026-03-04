"""Application Use Case: Query actor relationship network graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import structlog

from hydra_c2.domain.entities.actor import Actor
from hydra_c2.domain.interfaces.messaging import MessagePublisher
from hydra_c2.domain.interfaces.repositories import ActorRepository

logger = structlog.get_logger(__name__)


@dataclass
class NetworkNode:
    """Graph node projection returned by network query."""

    id: UUID
    callsign: str
    actor_type: str
    affiliation: str


@dataclass
class NetworkRelationship:
    """Graph relationship projection returned by network query."""

    source_id: UUID
    target_id: UUID
    relationship_type: str


@dataclass
class QueryNetworkResult:
    """Result of actor network query."""

    actor_id: UUID | None = None
    nodes: list[NetworkNode] = field(default_factory=list)
    relationships: list[NetworkRelationship] = field(default_factory=list)
    success: bool = True
    error: str | None = None


class QueryNetworkUseCase:
    """Query actor-centric graph neighborhood and return serializable shape."""

    def __init__(self, actor_repo: ActorRepository, publisher: MessagePublisher) -> None:
        self._actor_repo: ActorRepository = actor_repo
        self._publisher: MessagePublisher = publisher

    async def execute(self, actor_id: UUID, max_depth: int = 3) -> QueryNetworkResult:
        """Return graph nodes and relationships for one actor neighborhood."""
        try:
            seed_actor = await self._actor_repo.find_by_id(actor_id)
            network_actors = list(await self._actor_repo.find_network(actor_id, max_depth=max_depth))

            nodes = self._build_nodes(seed_actor, actor_id, network_actors)
            relationships = self._build_relationships(actor_id, nodes)

            payload = {
                "actor_id": str(actor_id),
                "max_depth": max_depth,
                "queried_at": datetime.now(UTC).isoformat(),
                "nodes": [
                    {
                        "id": str(node.id),
                        "callsign": node.callsign,
                        "actor_type": node.actor_type,
                        "affiliation": node.affiliation,
                    }
                    for node in nodes
                ],
                "relationships": [
                    {
                        "source_id": str(rel.source_id),
                        "target_id": str(rel.target_id),
                        "relationship_type": rel.relationship_type,
                    }
                    for rel in relationships
                ],
            }
            await self._publisher.publish("hydra/graph/network", payload)

            logger.info(
                "network_queried",
                actor_id=str(actor_id),
                max_depth=max_depth,
                node_count=len(nodes),
                relationship_count=len(relationships),
            )
            return QueryNetworkResult(
                actor_id=actor_id,
                nodes=nodes,
                relationships=relationships,
            )
        except Exception as exc:
            logger.exception("network_query_failed", actor_id=str(actor_id), error=str(exc))
            return QueryNetworkResult(actor_id=actor_id, success=False, error=str(exc))

    @staticmethod
    def _build_nodes(seed_actor: Actor | None, actor_id: UUID, network_actors: list[Actor]) -> list[NetworkNode]:
        """Build unique node list from seed actor and connected actors."""
        by_id: dict[UUID, NetworkNode] = {}

        if seed_actor is not None:
            by_id[seed_actor.id] = NetworkNode(
                id=seed_actor.id,
                callsign=seed_actor.callsign,
                actor_type=seed_actor.actor_type.value,
                affiliation=seed_actor.affiliation.value,
            )
        else:
            by_id[actor_id] = NetworkNode(
                id=actor_id,
                callsign="UNKNOWN",
                actor_type="UNKNOWN",
                affiliation="UNKNOWN",
            )

        for actor in network_actors:
            by_id[actor.id] = NetworkNode(
                id=actor.id,
                callsign=actor.callsign,
                actor_type=actor.actor_type.value,
                affiliation=actor.affiliation.value,
            )
        return list(by_id.values())

    @staticmethod
    def _build_relationships(actor_id: UUID, nodes: list[NetworkNode]) -> list[NetworkRelationship]:
        """Build relationship projections from seed actor to connected nodes."""
        return [
            NetworkRelationship(
                source_id=actor_id,
                target_id=node.id,
                relationship_type="CONNECTED",
            )
            for node in nodes
            if node.id != actor_id
        ]
