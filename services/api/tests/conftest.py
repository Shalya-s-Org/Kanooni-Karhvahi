import os
import shutil
import tempfile
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app as fastapi_app
from app.database.base import Base
from app.database.session import get_db
import app.database.session as session_module
from app.document.storage import LocalDocumentStorage
from app.services.document_service import document_service
from app.document.storage import document_storage
import app.api.routes.documents as routes_doc_module
import app.models  # ensure models registered
from app.core.config import settings

# Force mock providers for testing environment
settings.EMBEDDING_PROVIDER = "mock"
settings.LLM_PROVIDER = "mock"


@pytest_asyncio.fixture(scope="session")
def test_temp_dir():
    temp_dir = tempfile.mkdtemp(prefix="kanooni_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest_asyncio.fixture
async def test_db_session(test_temp_dir):
    db_file = os.path.join(test_temp_dir, "test.db")
    db_url = f"sqlite+aiosqlite:///{db_file}"

    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Patch AsyncSessionLocal
    session_module.AsyncSessionLocal = session_factory
    routes_doc_module.AsyncSessionLocal = session_factory

    # Create isolated test storage
    test_storage = LocalDocumentStorage(base_dir=os.path.join(test_temp_dir, "storage"))
    document_service.storage = test_storage
    document_storage.base_dir = test_storage.base_dir

    async def _get_test_db():
        async with session_factory() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = _get_test_db

    async with session_factory() as session:
        yield session

    fastapi_app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def async_client(test_db_session):
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
