from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.logger import logger
from app.core.qdrant import init_qdrant_collection
from app.messaging.consumer import kafka_consumer_manager
from app.services.agent_brain import checkpointer, pool


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    await init_qdrant_collection()
    await kafka_consumer_manager.start()
    await pool.open()
    await checkpointer.setup()
    logger.info("LangGraph Postgres Checkpointer Tables Created Successfully!")
    yield
    await kafka_consumer_manager.stop()
    await pool.close()

app = FastAPI(
    title="E-commerce AI Service",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(api_router)

@app.get("/health")
async def health_check():
    return { "status": "AI service is healthy" }



