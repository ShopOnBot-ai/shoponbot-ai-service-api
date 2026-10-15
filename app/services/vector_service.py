from langchain_ollama import OllamaEmbeddings
from qdrant_client.models import PointStruct

from app.core.config import settings
from app.core.logger import logger
from app.core.qdrant import client

embedding_model = OllamaEmbeddings(
    base_url=settings.ollama_base_url, model="all-minilm"
)


async def process_vector_events(event_type: str, payload: dict) -> None:
    product_id = payload.get("product_id")

    if not product_id:
        logger.error(
            "Payload error: Missing product_id token constraint inside outbox tracking block."
        )
        return

    try:
        if event_type in ["ProductCreated", "ProductUpdated"]:
            title = payload.get("title")
            description = payload.get("description")
            price = payload.get("price")

            logger.info(
                "Vectorizing text context for RAG storage processing. Product ID: %s",
                product_id,
            )

            text_chunk_document = f"Product Title: {title}\nDescription: {description}\nPrice: {price} INR"

            vector_embeddings_array = embedding_model.embed_query(text_chunk_document)

            point_entry = PointStruct(
                id=int(product_id),
                vector=vector_embeddings_array,
                payload={
                    "product_id": product_id,
                    "title": title,
                    "description": description,
                    "price": price,
                    "text_metadata_content": text_chunk_document,
                },
            )

            client.upsert(collection_name="products", points=[point_entry])

        elif event_type == "ProductDeleted":
            logger.info(
                "Executing vector permanent deletion wipeout from Qdrant indexes for Product ID: %s",
                product_id,
            )

            client.delete(collection_name="products", points_selector=[int(product_id)])
            logger.info(
                "SUCCESS: Stale product vectors completely flushed out from RAG index storage."
            )

    except Exception as e:
        logger.error(
            "Fail: Vector transformation service collapsed during execution: %s", str(e)
        )
        raise
