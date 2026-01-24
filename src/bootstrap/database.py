"""Database session factory bootstrap (PostgreSQL via SQLAlchemy).

This module provides the database session factory for production PostgreSQL
repositories.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → Connection errors logged
- CT-12: Witnessing creates accountability → Transactions auditable

Environment Variables:
- DATABASE_URL: PostgreSQL connection string (required for production)
  Format: postgresql://user:password@host:port/database

Usage:
    from src.bootstrap.database import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as session:
        # Use session for database operations
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from structlog import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger()

_session_factory: async_sessionmaker[AsyncSession] | None = None
_engine = None


def get_database_url() -> str:
    """Get PostgreSQL connection URL from environment.

    Converts standard PostgreSQL URL to async-compatible format.

    Returns:
        postgresql+asyncpg:// URL string.

    Raises:
        ValueError: If DATABASE_URL is not set.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError(
            "DATABASE_URL environment variable not set. "
            "Required for PostgreSQL repository."
        )

    # Convert to asyncpg format if needed
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif not url.startswith("postgresql+asyncpg://"):
        url = f"postgresql+asyncpg://{url}"

    return url


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the SQLAlchemy async session factory.

    Creates a singleton session factory on first call.
    The factory creates sessions connected to the PostgreSQL database
    specified by DATABASE_URL.

    Returns:
        SQLAlchemy async_sessionmaker for creating AsyncSession instances.

    Raises:
        ValueError: If DATABASE_URL is not configured.
    """
    global _session_factory, _engine

    if _session_factory is None:
        log = logger.bind(component="database_bootstrap")
        url = get_database_url()

        # Mask password in logs
        log_url = url
        if "@" in url:
            # Hide password in log
            before_at = url.split("@")[0]
            after_at = url.split("@")[1]
            if ":" in before_at:
                user_part = before_at.rsplit(":", 1)[0]
                log_url = f"{user_part}:***@{after_at}"

        log.info("creating_database_engine", url=log_url)

        _engine = create_async_engine(
            url,
            echo=os.environ.get("SQLALCHEMY_ECHO", "").lower() in ("1", "true", "yes"),
            pool_pre_ping=True,  # Enable connection health checks
        )

        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        log.info("database_session_factory_created")

    return _session_factory


def reset_database_bootstrap() -> None:
    """Reset database singleton for testing."""
    global _session_factory, _engine
    _session_factory = None
    _engine = None


async def close_database_engine() -> None:
    """Close the database engine (for graceful shutdown)."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
