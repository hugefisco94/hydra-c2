"""Neo4j async connection factory and lifecycle helpers."""

from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase
import structlog
from structlog.typing import FilteringBoundLogger

from hydra_c2.config import Neo4jSettings

logger: FilteringBoundLogger = structlog.get_logger()


def create_neo4j_driver(settings: Neo4jSettings) -> AsyncDriver:
    """Create an async Neo4j driver from application settings."""
    driver = AsyncGraphDatabase.driver(
        settings.uri,
        auth=(settings.user, settings.password),
    )
    logger.info("neo4j_driver_created", uri=settings.uri, user=settings.user)
    return driver


async def close_neo4j_driver(driver: AsyncDriver) -> None:
    """Close an async Neo4j driver."""
    await driver.close()
    logger.info("neo4j_driver_closed")
