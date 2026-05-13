"""SQLAlchemy base and session management."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from functools import lru_cache

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Create and cache the async engine (lazy initialization)."""
    from tsilo.config import get_settings

    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.is_development,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the async session factory."""
    return async_sessionmaker(
        get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Import all models so SQLAlchemy mappers are fully configured
from tsilo.models.api_token import APIToken  # noqa: E402, F401
from tsilo.models.metric import DownloadMetric  # noqa: E402, F401
from tsilo.models.module import Module  # noqa: E402, F401
from tsilo.models.namespace import Namespace  # noqa: E402, F401
from tsilo.models.oauth_code import OAuthAuthorizationCode  # noqa: E402, F401
from tsilo.models.permission import NamespacePermission  # noqa: E402, F401
from tsilo.models.user import User  # noqa: E402, F401
from tsilo.models.version import ModuleVersion  # noqa: E402, F401
