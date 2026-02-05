from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine,async_sessionmaker
from config import DATABASE_URL
from sqlalchemy.orm import declarative_base

engine = create_async_engine(
    url=DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={
        "ssl": "require",
        "statement_cache_size": 0
    }
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session