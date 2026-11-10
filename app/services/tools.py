import json

import httpx
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.core.config import settings
from app.core.logger import logger
from app.services.product_search import search_products


@tool(description="Retrieves active shopping cart items and pricing details for a given user identifier.")
async def fetch_user_cart_data(config: RunnableConfig) -> str:
    cookies = config.get("configurable", {}).get("auth_cookies", {})
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            url = f"{settings.backend_api_url}/api/v1/cart"
            response = await client.get(url, cookies=cookies)
            response.raise_for_status()
            cart_data = response.json()
            logger.info("Context array successfully fetched from backend: %s", cart_data)
            return json.dumps(cart_data, ensure_ascii=False)
        except Exception as e:
            logger.exception("Failed to connect to the backend service:")
            return f"Error: Failed to fetch user cart data payload due to internal system communication lag: {str(e)}"


@tool("search_products")
async def search_products_tool(query: str, max_price: int | None = None, limit: int = 5) -> str:
    """Search the store's in-stock products by meaning.
    Use when the user wants to find, browse or compare products,
    e.g. "running shoes under 700".
    Put only the product description in `query` (no price words).
    Put the price limit in `max_price`, in rupees.
    Do NOT use for cart or order questions."""

    results = await search_products(query=query, max_price=max_price, limit=limit)
    if not results:
        return "No matching products found."
    return json.dumps(results, ensure_ascii=False)