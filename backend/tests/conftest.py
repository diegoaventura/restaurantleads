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
from app.core.security import hash_password
from app.db.base import Base
from app.models import User
from app.models.enums import UserRole

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


@pytest_asyncio.fixture
async def client():
    """HTTP client bound to the app, with the DB overridden to the test DB."""
    from httpx import ASGITransport, AsyncClient

    from app.api.deps import get_db_session as dep_get_db_session
    from app.main import create_app

    app = create_app()
    engine = create_async_engine(_url_with_db(TEST_DB_NAME), pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[dep_get_db_session] = override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    await engine.dispose()


@pytest_asyncio.fixture
async def users(db_session: AsyncSession):
    """One admin + one sales user (fictional, per-test)."""
    admin = User(
        email="admin@example.com",
        full_name="Ana Admin",
        hashed_password=hash_password("admin-pass-1234"),
        role=UserRole.ADMIN,
    )
    sales = User(
        email="ventas@example.com",
        full_name="Sam Sales",
        hashed_password=hash_password("sales-pass-1234"),
        role=UserRole.SALES,
    )
    db_session.add_all([admin, sales])
    await db_session.commit()
    return {"admin": admin, "sales": sales}


@pytest_asyncio.fixture
async def auth_headers(client, users) -> dict[str, dict[str, str]]:
    """Bearer headers for both roles."""
    headers: dict[str, dict[str, str]] = {}
    for key, password in (
        ("admin", "admin-pass-1234"),
        ("sales", "sales-pass-1234"),
    ):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": users[key].email, "password": password},
        )
        assert response.status_code == 200, response.text
        headers[key] = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return headers
