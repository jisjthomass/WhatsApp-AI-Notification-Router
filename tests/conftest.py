import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_router.db"

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import asyncio

from router.database import Base, get_db, engine
from router.api import app

TestingSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

@pytest.fixture(autouse=True)
def setup_db(request):
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    asyncio.run(_setup())
    def teardown():
        asyncio.run(_teardown())
    request.addfinalizer(teardown)

@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    yield session

@pytest.fixture
def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def anyio_backend():
    return 'asyncio'
import sys
import unittest.mock
from unittest.mock import MagicMock

class MockGoogleGenai:
    types = MagicMock()
    Client = MagicMock()

sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MockGoogleGenai()
sys.modules['google.genai.types'] = MockGoogleGenai.types
