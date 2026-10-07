import asyncio

from app.services.redis import redis_client


async def main():
    try:
        key = "learning:user:101"

        # 1. HSET
        await redis_client.hset(
            key,
            mapping={
                "name": "Deepak",
                "role": "developer",
                "experience": "4",
            },
        )
        print("HSET: user data stored")

        # 2. HGET
        name = await redis_client.hget(key, "name")
        print("HGET name:", name)

        # 3. HGETALL
        user = await redis_client.hgetall(key)
        print("HGETALL:", user)

        # 4. HEXISTS
        role_exists = await redis_client.hexists(key, "role")
        print("HEXISTS role:", role_exists)

        # 5. HDEL
        await redis_client.hdel(key, "experience")
        print("HDEL: experience removed")

        # 6. HGETALL after HDEL
        user_after_delete = await redis_client.hgetall(key)
        print("HGETALL after HDEL:", user_after_delete)

        # 7. Cleanup
        await redis_client.delete(key)
        print("DELETE: hash removed")

    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())