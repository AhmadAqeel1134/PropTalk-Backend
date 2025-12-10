"""
Test Configuration and Fixtures
Provides shared test setup for all test cases
"""
import pytest
import pytest_asyncio
import asyncio
import uuid
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database.connection import get_db, Base
from app.models.admin import Admin
from app.models.real_estate_agent import RealEstateAgent
from app.utils.security import get_password_hash
import os

# Test database URL (use in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a fresh database session for each test"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """Create test HTTP client"""
    async def override_get_db():
        yield db_session
    
    # Override get_db dependency
    app.dependency_overrides[get_db] = override_get_db
    
    # Create a context manager that returns our test session
    class TestSessionContext:
        def __init__(self, session):
            self.session = session
        async def __aenter__(self):
            return self.session
        async def __aexit__(self, *args):
            pass
    
    # Create a mock AsyncSessionLocal that returns our test session
    def make_test_session_local(session):
        return lambda: TestSessionContext(session)
    
    # Patch AsyncSessionLocal in the connection module
    from app.database import connection as db_connection_module
    original_session_local = db_connection_module.AsyncSessionLocal
    
    # Replace with test session local
    db_connection_module.AsyncSessionLocal = make_test_session_local(db_session)
    
    # Also need to patch in services that have already imported it
    import sys
    modules_to_patch = [
        'app.services.auth_service',
        'app.services.real_estate_agent_auth_service',
        'app.services.admin_service',
        'app.services.call_service',
        'app.services.voice_agent_service',
        'app.services.document_service',
        'app.services.ai.context_service',
        'app.services.call_statistics_service',
        'app.services.real_estate_agent.document_service',
        'app.services.real_estate_agent.profile_service',
        'app.services.real_estate_agent.property_service',
        'app.services.real_estate_agent.contact_service',
        'app.services.real_estate_agent.dashboard_service',
        'app.services.real_estate_agent_service',
        'app.services.admin_dashboard_service',
        'app.services.twilio_service.webhook_service',
        'app.services.phone_number_service',
        'app.database.connection',
    ]
    
    patches = []
    for module_name in modules_to_patch:
        if module_name in sys.modules:
            module = sys.modules[module_name]
            if hasattr(module, 'AsyncSessionLocal'):
                patches.append(patch.object(module, 'AsyncSessionLocal', make_test_session_local(db_session)))
    
    # Start patches
    for p in patches:
        p.start()
    
    try:
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    finally:
        # Stop patches
        for p in patches:
            p.stop()
        # Restore original
        db_connection_module.AsyncSessionLocal = original_session_local
        app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def authenticated_agent(client: AsyncClient, db_session):
    """Create and authenticate a real estate agent for testing"""
    agent = RealEstateAgent(
        id=str(uuid.uuid4()),
        email=f"agent_{uuid.uuid4().hex[:10]}@example.com".lower(),
        hashed_password=get_password_hash("StrongPass123!"),
        full_name="Test Real Estate Agent",
        phone="+923331234567",
        is_verified=True,
        is_active=True
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    
    resp = await client.post("/auth/real-estate-agent/login", json={
        "email": agent.email,
        "password": "StrongPass123!"
    })
    
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
    else:
        # Log error for debugging
        print(f"Warning: Agent login failed with status {resp.status_code}")
        if resp.status_code == 422:
            print(f"Response: {resp.text}")
    
    return client, agent


@pytest_asyncio.fixture(scope="function")
async def authenticated_admin(client: AsyncClient, db_session):
    """Create and authenticate an admin user for testing"""
    admin = Admin(
        id=str(uuid.uuid4()),
        email="admin@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="System Administrator",
        is_active=True,
        is_super_admin=True
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    
    resp = await client.post("/auth/admin/login", json={
        "email": admin.email,
        "password": "AdminPass123!"
    })
    
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
    else:
        # Log error for debugging
        print(f"Warning: Admin login failed with status {resp.status_code}")
        if resp.status_code == 422:
            print(f"Response: {resp.text}")
    
    return client, admin


@pytest.fixture(scope="function")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
