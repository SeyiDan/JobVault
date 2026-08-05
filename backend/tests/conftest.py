import os

# SECRET_KEY has no default in production (CWE-798 fix); Settings() runs at import
# via app.database -> get_settings(). Supply a test key before importing the app.
os.environ.setdefault("SECRET_KEY", "test-only-secret-not-a-real-key-0123456789abcdef")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

# Deterministic, dependency-free embeddings. The real backend downloads a model
# and pulls in torch, neither of which belongs in a unit test run. Retrieval
# QUALITY is measured separately by eval/run_eval.py against the real backend.
os.environ.setdefault("EMBEDDING_BACKEND", "hashing")
# No LLM call, so the suite needs no API key and makes no network request.
os.environ.setdefault("GENERATION_BACKEND", "extractive")

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app

from sqlalchemy import text

# Defaults to SQLite so a plain `pytest` needs no database container. Point
# DATABASE_URL at Postgres to run the same suite against the pgvector search
# path, which SQLite cannot exercise:
#
#   DATABASE_URL=postgresql+asyncpg://... pytest
#
# CI runs both. Without the Postgres pass, app/rag/store.py's pgvector branch is
# the code that only ever runs in production, which is the code most likely to
# be broken.
TEST_DATABASE_URL = os.environ["DATABASE_URL"]

# NullPool: do not hold connections open between tests. pytest-asyncio gives each
# test its own event loop, and an asyncpg connection is bound to the loop that
# opened it, so a pooled connection reused on the next test's loop raises
# "attached to a different loop". SQLite happens to tolerate it; Postgres does
# not. Opening a fresh connection per test costs milliseconds against a local
# database and removes the whole class of failure.
engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


# No custom `event_loop` fixture. Overriding it is deprecated in pytest-asyncio,
# and a session-scoped loop is what made asyncpg connections outlive the loop
# that created them. Each test now gets its own loop and its own connection.


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        # document_chunks.embedding is a pgvector column on Postgres and the type
        # does not exist until the extension is created. Mirrors the app lifespan.
        if conn.dialect.name == "postgresql":
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    await client.post("/auth/register", json={"email": "test@example.com", "password": "testpass123"})
    resp = await client.post("/auth/login", data={"username": "test@example.com", "password": "testpass123"})
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
