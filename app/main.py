from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import router as v1_router
from app.services.redis import redis_client



@asynccontextmanager
async def lifespan(app: FastAPI):
    #startup
    await redis_client.ping()

    yield

    #shutdown
    await redis_client.aclose()


app = FastAPI(
    title="E-commerce AI Service",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(
    v1_router.router,
    prefix="/api/v1"
)