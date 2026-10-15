import json

import httpx
from langchain_core.tools import tool

from app.core.config import settings
from app.core.logger import logger


@tool(description="Retrieves active shopping cart items and pricing details for a given user identifier.")
async def fetch_user_cart_data(cookies: dict) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            url = f"{settings.backend_api_url}/api/v1/cart/"
            response = await client.get(url, cookies=cookies)
            response.raise_for_status()
            cart_data = response.json()
            logger.info("Context array successfully fetched from backend: %s", cart_data)
            return json.dumps(cart_data, ensure_ascii=False)
        except Exception as e:
            logger.exception("Failed to connect to the backend service:")
            return f"Error: Failed to fetch user cart data payload due to internal system communication lag: {str(e)}"