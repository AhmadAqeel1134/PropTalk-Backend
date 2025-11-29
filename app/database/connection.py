from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.engine.url import make_url
from app.config import settings

def get_database_url():
    """Parse database URL and convert to asyncpg-compatible format"""
    # Build URL manually like Alembic does to preserve password correctly
    original_url = make_url(settings.DATABASE_URL)
    port = original_url.port or 5432
    
    # Build the connection string manually to preserve special characters in password
    database_url = (
        f"postgresql+asyncpg://{original_url.username}:{original_url.password}"
        f"@{original_url.host}:{port}/{original_url.database}"
    )
    
    # Add query parameters (excluding sslmode which we handle in connect_args)
    query_params = {}
    if original_url.query:
        for key, value in original_url.query.items():
            if key not in ['sslmode', 'channel_binding']:
                query_params[key] = value
    
    if query_params:
        query_string = '&'.join([f"{k}={v}" for k, v in query_params.items()])
        database_url += f"?{query_string}"
    
    return database_url

def get_connect_args():
    """Get connection arguments for asyncpg, especially for SSL"""
    url = make_url(settings.DATABASE_URL)
    connect_args = {}
    
    # Check if SSL is required (Neon requires SSL)
    if url.query and url.query.get('sslmode') == 'require':
        # For asyncpg with Neon, use ssl='require' or True
        connect_args['ssl'] = 'require'
    
    return connect_args

engine = create_async_engine(
    get_database_url(),
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=3600,  # Recycle connections after 1 hour
    connect_args=get_connect_args()
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()


async def get_db():
    """Get database session (generator for FastAPI dependency injection)"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def close_db():
    """Close database connections"""
    await engine.dispose()
