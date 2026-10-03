"""Pytest fixtures: throwaway PostgreSQL test database migrated with Alembic.

The test DB (restaurant_leads_test) is dropped/created and migrated once per
session — running the real migrations validates them, not just the models.
Tests share the DB; rows are truncated after each test for isolation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.eventloop import ensure_compatible_event_loop
from app.db.base import Base

ensure_compatible_event_loop()  # Windows + psycopg async (ProactorEventLoop)

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB_NAME = "restaurant_leads_test"


def _url_with_db(db_name: str) -> str:
    parts = urlsplit(get_settings().database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{db_name}", "", ""))


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Drop/create the test database and run all Alembic migrations."""
    admin = create_engine(_url_with_db("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(
            text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
        )
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    admin.dispose()

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", _url_with_db(TEST_DB_NAME))
    command.upgrade(cfg, "head")

    yield

    admin = create_engine(_url_with_db("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)"))
    admin.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Session per test; all tables truncated afterwards for isolation."""
    engine = create_async_engine(_url_with_db(TEST_DB_NAME), pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
        await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))

    await engine.dispose()
