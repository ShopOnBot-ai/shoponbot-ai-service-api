"""
Eval catalog ko ek ALAG Qdrant collection (products_eval) mein daalta hai.
Production wali "products" collection ko ye script chhoota bhi nahi.

Chalane ka tareeka (ai-service project folder se):

    docker cp catalog.json ai_service:/tmp/eval_catalog.json
    docker exec -i -w /app ai_service python - < seed_eval_catalog.py

Text ka format wahi hai jo production index mein use hota hai:
    Product Title / Category / Keywords / Description / Price INR
"""
import asyncio
import json

from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.qdrant import client
from app.services.vector_service import embedding_model

CATALOG_PATH = "/tmp/eval_catalog.json"
COLLECTION = "products_eval"


def build_text(product: dict, keywords: str) -> str:
    return (
        f"Product Title: {product['title']}\n"
        f"Category: {product['category']}\n"
        f"Keywords: {keywords}\n"
        f"Description: {product['description']}\n"
        f"Price: {product['price']} INR"
    )


async def main() -> None:
    with open(CATALOG_PATH, encoding="utf-8") as f:
        catalog = json.load(f)

    categories = catalog["categories"]
    products = catalog["products"]

    # vector ka size embedding model se hi nikaal lete hain
    dim = len(await embedding_model.aembed_query("size check"))

    if await client.collection_exists(COLLECTION):
        await client.delete_collection(COLLECTION)
    await client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )

    points = []
    for p in products:
        text = build_text(p, categories[p["category"]])
        vector = await embedding_model.aembed_query(text)
        points.append(
            PointStruct(
                id=p["product_id"],
                vector=vector,
                payload={
                    "product_id": p["product_id"],
                    "title": p["title"],
                    "description": p["description"],
                    "category_name": p["category"],
                    "price": int(p["price"]),
                    "in_stock": bool(p["in_stock"]),
                    "stock_quantity": int(p["stock_quantity"]),
                    "text_metadata_content": text,
                },
            )
        )

    await client.upsert(collection_name=COLLECTION, points=points)
    total = await client.count(collection_name=COLLECTION)
    print(f"seeded {total.count} products into '{COLLECTION}' (vector size {dim})")

    # chhota sanity check: 3 queries ke top-3 results
    for q in ["smartphone", "running shoes", "laptop"]:
        vec = await embedding_model.aembed_query(q)
        res = await client.query_points(
            collection_name=COLLECTION, query=vec, limit=3, with_payload=True
        )
        print(f"\nQUERY: {q}")
        for r in res.points:
            pl = r.payload or {}
            print(round(r.score, 3), pl.get("product_id"), pl.get("title"))


asyncio.run(main())