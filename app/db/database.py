from os import getenv

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)



DATABASE_URL = getenv("DATABASE_URL")

engine = create_async_engine(
    DATABASE_URL
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session