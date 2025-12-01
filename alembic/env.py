from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import asyncio
from app.database.connection import Base
from app.config import settings
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Admin, RealEstateAgent, PhoneNumber, Document, Property, Contact

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

url = make_url(settings.DATABASE_URL)

if not url.password:
    raise ValueError("Database password is missing from DATABASE_URL")

url = url.set(drivername="postgresql+asyncpg")

query_params = {}
if url.query:
    for key, value in url.query.items():
        if key not in ['sslmode', 'channel_binding']:
            query_params[key] = value
    
    if 'sslmode' in url.query and url.query['sslmode'] == 'require':
        query_params['ssl'] = 'require'

url = url.set(query=query_params)

config.set_main_option("sqlalchemy.url", str(url))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create Engine and associate a connection with the context."""
    from sqlalchemy.ext.asyncio import create_async_engine
    
    original_url = make_url(settings.DATABASE_URL)
    needs_ssl = original_url.query.get('sslmode') == 'require'
    
    port = original_url.port or 5432
    database_url = (
        f"postgresql+asyncpg://{original_url.username}:{original_url.password}"
        f"@{original_url.host}:{port}/{original_url.database}"
    )
    
    connect_args = {}
    if needs_ssl:
        connect_args["ssl"] = "require"
    
    connectable = create_async_engine(
        database_url,
        connect_args=connect_args,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

