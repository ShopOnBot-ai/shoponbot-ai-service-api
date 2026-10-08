from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.qdrant import init_qdrant_collection
from app.messaging.consumer import kafka_consumer_manager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    await init_qdrant_collection()
    await kafka_consumer_manager.start()
    yield
    await kafka_consumer_manager.stop()

app = FastAPI(
    title="E-commerce AI Service",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(api_router, prefix="/api/v1/ai")

@app.get("/health")
async def health_check():
    return { "status": "AI service is healthy" }



