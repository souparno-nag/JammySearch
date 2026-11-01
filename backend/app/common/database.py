"""Async database engine, session factory, and the shared declarative base.

This module owns the single SQLAlchemy `AsyncEngine` for the process. Every module
obtains sessions from here rather than constructing its own engine, so connection
pooling is shared and the process holds one pool rather than one per module.

`Base` is the declarative base every module's ORM models inherit from. A single
shared `MetaData` is what lets Alembic autogenerate see the whole schema at once;
it does not weaken the module boundary in Constitution II, which is about which
module may *query* which tables, not about which metadata object they register on.

External systems touched: PostgreSQL.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Deterministic constraint and index names. Without these, PostgreSQL invents names
# for unnamed constraints, and an Alembic migration that has to DROP one later cannot
# refer to it portably. Setting the convention before the first model exists means
# every constraint this project ever creates is named predictably.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every module's ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# `create_async_engine` does not connect; the first connection is opened lazily on
# first use, so importing this module never performs I/O.
engine: AsyncEngine = create_async_engine(
    settings.database_url.get_secret_value(),
    pool_size=5,
    max_overflow=10,
    # Verify a pooled connection is still alive before handing it out. Without this,
    # a connection dropped by the server (container restart, idle timeout) surfaces as
    # a failed request rather than a transparent reconnect.
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False,
)

# `expire_on_commit=False` keeps ORM objects readable after the session commits.
# With the default, every attribute access after a commit triggers a refresh query —
# which in an async session raises rather than lazily loading.
session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped session, committing on success and rolling back on error.

    Intended as the FastAPI dependency behind every route that reads or writes the
    database. Owning the transaction boundary here means service functions do not each
    commit independently, so a request that fails part-way leaves nothing half-written.

    External systems touched: PostgreSQL.
    """
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Close every pooled connection.

    Called on application shutdown, and by any script or worker that finishes with the
    database, so the process does not exit holding open server-side connections.

    External systems touched: PostgreSQL.
    """
    await engine.dispose()
