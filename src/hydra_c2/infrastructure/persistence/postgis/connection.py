"""Async PostGIS engine and session factory utilities."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import os
from typing import Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

try:
    from hydra_c2.config import get_settings as _get_settings
except ModuleNotFoundError:
    _get_settings = None


class _PostGISConfig(Protocol):
    dsn: str


class _SettingsLike(Protocol):
    postgis: _PostGISConfig


logger = structlog.get_logger()

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _default_dsn() -> str:
    user = os.getenv("POSTGIS_USER", "hydra")
    password = os.getenv("POSTGIS_PASSWORD", "hydra_dev_2026")
    host = os.getenv("POSTGIS_HOST", "localhost")
    port = os.getenv("POSTGIS_PORT", "5432")
    database = os.getenv("POSTGIS_DATABASE", "hydra_c2")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


def get_engine(settings: _SettingsLike | None = None) -> AsyncEngine:
    """Create or return a cached async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        effective_settings = settings or (_get_settings() if _get_settings is not None else None)
        dsn = effective_settings.postgis.dsn if effective_settings is not None else _default_dsn()
        _engine = create_async_engine(
            dsn,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            echo=False,
        )
        logger.info("postgis_engine_initialized", dsn=dsn)
    return _engine


def get_session_factory(settings: _SettingsLike | None = None) -> async_sessionmaker[AsyncSession]:
    """Create or return a cached async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(settings),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session(settings: _SettingsLike | None = None) -> AsyncIterator[AsyncSession]:
    """Yield an async PostGIS session with automatic close."""
    session_factory = get_session_factory(settings)
    async with session_factory() as session:
        yield session


async def dispose_engine() -> None:
    """Dispose cached engine connections."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        logger.info("postgis_engine_disposed")
    _engine = None
    _session_factory = None


__all__ = ["get_engine", "get_session_factory", "get_session", "dispose_engine"]
