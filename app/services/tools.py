import json
import uuid
from typing import Annotated

import httpx
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool
from langgraph.types import StreamWriter, interrupt

from app.core.config import settings
from app.core.logger import logger
from app.services.product_search import search_products


@tool("get_user_address")
async def get_user_address_tool(config: RunnableConfig) -> str:
    """
    Fetches all saved delivery addresses for the current user along with their address_id.
    Always call this before place_order to get the user's address_id.
    """

    cookies = config.get("configurable", {}).get("auth_cookies", {}) if config else {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{settings.backend_api_url}/api/v1/address"
            response = await client.get(url=url, cookies=cookies)
            response.raise_for_status()
            addresses_data = response.json()

            if not addresses_data:
                return "No saved addresses found for this user. Ask the user to add a delivery address on the app/website first."
            return json.dumps(addresses_data, ensure_ascii=False)
    except Exception as e:
        logger.exception("Failed to connect to the backend service:")
        return f"Error: Failed to fetch user address data payload due to internal system communication lag: {str(e)}"
             


@tool("fetch_cart")
async def fetch_user_cart_data_tool(config: RunnableConfig) -> str:
    """Retrieves the logged-in user's current shopping cart items and pricing.
    Use ONLY for questions about the cart.
    Do NOT use for orders, order status, tracking, payments or delivery."""

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
    Put the price limit in `max_price`, in rupees, ONLY when the user states
    an explicit number. Never guess a number from words like cheap, sasta or budget.
    Do NOT use for cart or order questions."""

    results = await search_products(query=query, max_price=max_price, limit=limit)
    if not results:
        return "No matching products found."
    return json.dumps(results, ensure_ascii=False)


@tool("place_order")
async def place_order_tool(address_id: int, address_summary: str, writer: Annotated[StreamWriter, InjectedToolArg], config: RunnableConfig = None) -> str:
    """
    Places an order for the items currently in the user's cart.
    Always requires shipping_address. Default payment_method is COD.
    """

    user_approval = interrupt({
        "action": "place_order",
        "message": f"Confirm order placement to '{address_summary}' ? (Reply 'yes' to confirm)",
        "address_id": address_id,
    })

    if str(user_approval).strip().lower() not in ["yes", "ya", "y", "confirm", "haan", "ha"]:
        return "Order cancelled by the user. No order was placed."

    cookies = config.get("configurable", {}).get("auth_cookies", {}) if config else None
    logger.info("user_id from place order tool: %s", cookies)
    payload = {
        "address_id": address_id,
        "idempotency_key": str(uuid.uuid4()),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{settings.order_api_url}/api/v1/orders/checkout/place-order"
            response = await client.post(url=url, json=payload, cookies=cookies)
            response.raise_for_status()
            order_data = response.json()
            writer({
                 "payment": {
                    "order_number": order_data.get("order_number"),
                    "razorpay_order_id": order_data.get("razorpay_order_id"),
                    "amount": order_data.get("total_amount"),
                }
            })
            return json.dumps(order_data, ensure_ascii=False)
    except Exception as e:
                logger.exception("Failed to connect to the order service:")
                return f"Error: Failed to fetch user order data payload due to internal system communication lag: {str(e)}"
    