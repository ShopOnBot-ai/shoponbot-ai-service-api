import time

from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

from app.core.logger import logger
from app.core.qdrant import client
from app.services.vector_service import embedding_model

COLLECTION_NAME = "products"
MAX_LIMIT = 5
MIN_SCORE = 0.35


async def search_products(
    query: str,
    max_price: int | None = None,
    limit: int = 5,
    collection_name: str = COLLECTION_NAME,
    min_score: float = MIN_SCORE,
    include_score: bool = False,
) -> list[dict]:
    """Semantic product search. Always returns only in-stock products."""
    limit = max(1, min(limit, MAX_LIMIT))
    t0 = time.perf_counter()
    vector = await embedding_model.aembed_query(query)
    t_embed = time.perf_counter() - t0

    conditions = [FieldCondition(key="in_stock", match=MatchValue(value=True))]
    if max_price is not None:
        conditions.append(FieldCondition(key="price", range=Range(lte=max_price)))
    query_filter = Filter(must=conditions)

    t1 = time.perf_counter()
    response = await client.query_points(
        collection_name=collection_name,
        query=vector,
        query_filter=query_filter,
        limit=limit,
        score_threshold=min_score,
        with_payload=True,
    )
    t_search = time.perf_counter() - t1

    results = []
    for point in response.points:
        payload = point.payload or {}
        item = {
            "product_id": payload.get("product_id"),
            "title": payload.get("title"),
            "price": payload.get("price"),
            "description": payload.get("description"),
        }
        if include_score:
            item["score"] = round(point.score, 4)
        results.append(item)

    logger.info(
        "search_products: query=%r max_price=%s found=%d embed=%.3fs search=%.3fs",
        query,
        max_price,
        len(results),
        t_embed,
        t_search,
    )
    return results