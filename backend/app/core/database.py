"""Async SQLAlchemy engine, session factory and the declarative base."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.sql_echo,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — one session per request, rolled back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def create_all() -> None:
    """Create any missing tables directly from the models.

    Alembic owns the schema. This is kept only for the legacy `migrate.py` path
    and for building a throwaway database in a test; nothing in the running
    application calls it, because it silently ignores every change that is not
    a whole new table — which is what let the schema drift in the first place.
    """
    from app import models  # noqa: F401  (registers mappers on Base.metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def schema_revision() -> str | None:
    """The Alembic revision this database is stamped at, or None if unmigrated.

    Returns None both when `alembic_version` does not exist and when it exists
    but is empty; from the caller's point of view those are the same problem —
    `alembic upgrade head` has not been run here.
    """
    async with engine.connect() as conn:
        exists = await conn.scalar(text("SELECT to_regclass('public.alembic_version')"))
        if exists is None:
            return None
        return await conn.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
