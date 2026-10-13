from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings
from app.core.logger import logger

QDRANT_HOST = settings.qdrant_host
QDRANT_PORT = settings.qdrant_port

client = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


async def init_qdrant_collection():
    collection_status_exists = await client.collection_exists("products")
    if not collection_status_exists:
        logger.info("Target collection 'products' index schema not found. Creating brand new index mesh.")
        await client.create_collection(
            collection_name="products",
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        logger.info("Qdrant 'products' collection initialised successfully.")
