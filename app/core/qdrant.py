from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings

QDRANT_HOST = settings.qdrant_host
QDRANT_PORT = settings.qdrant_port

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


async def init_qdrant_collection():
    if not client.collection_exists("products"):
        client.create_collection(
            collection_name="products",
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
