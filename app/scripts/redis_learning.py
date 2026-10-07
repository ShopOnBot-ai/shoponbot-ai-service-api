import asyncio

from app.services.redis import redis_client


async def main():
    try:
        key = "learning:redis"

        # 1. SET
        await redis_client.set(key, "Hello Redis")
        print("SET:", key)

        # 2. GET
        value = await redis_client.get(key)
        print("GET:", value)

        # 3. EXISTS
        exists = await redis_client.exists(key)
        print("EXISTS:", exists)

        # 4. EXPIRE
        await redis_client.expire(key, 30)

        # 5. TTL
        ttl = await redis_client.ttl(key)
        print("TTL:", ttl)

        # 6. DELETE
        await redis_client.delete(key)

        # 7. EXISTS after DELETE
        exists_after_delete = await redis_client.exists(key)
        print("EXISTS after DELETE:", exists_after_delete)

    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())