from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db


router = APIRouter()


@router.get("/health")
async def health_check():
    return { "status": "ok" }


@router.get("/health/db")
async def database_health_check(db: AsyncSession = Depends(get_db)):
    return {"status": "dababase session created"}