import asyncio

from app.services.redis import redis_client


async def main():
    try:
        key = "learning:messages"

        # 1. RPUSH
        await redis_client.rpush(
            key,
            "Hello",
            "How are you?",
        )
        print("RPUSH: messages added")

        # 2. LPUSH
        await redis_client.lpush(
            key,
            "Start of conversation",
        )
        print("LPUSH: message added")

        # 3. LRANGE
        messages = await redis_client.lrange(key, 0, -1)
        print("LRANGE:", messages)

        # 4. LLEN
        length = await redis_client.llen(key)
        print("LLEN:", length)

        # 5. LPOP
        left_message = await redis_client.lpop(key)
        print("LPOP:", left_message)

        # 6. RPOP
        right_message = await redis_client.rpop(key)
        print("RPOP:", right_message)

        # 7. LRANGE after POP operations
        remaining_messages = await redis_client.lrange(key, 0, -1)
        print("LRANGE after POP:", remaining_messages)

        # 8. Cleanup
        await redis_client.delete(key)
        print("DELETE: list removed")

    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())