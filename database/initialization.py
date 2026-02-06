from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from config import DATABASE_URL
import logging

logger = logging.getLogger(__name__)

# Validate DATABASE_URL exists
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in environment variables")

engine = create_async_engine(
    url=DATABASE_URL,
    echo=False,  # Turn off in production
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,  # Supabase free tier has connection limits
    max_overflow=5,  # Keep total connections low for free tier
    connect_args={
        "ssl": "require",
        "statement_cache_size": 0,
        "server_settings": {"jit": "off"}  # Helps with Supabase performance
    }
)

AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=False  # Better for async
)

Base = declarative_base()

async def get_db():
    """Dependency for getting async database sessions"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Initialize database tables (optional - use Alembic in production)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")