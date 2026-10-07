import asyncio
from uuid import uuid4

from app.services.session import SessionService
from app.services.redis import redis_client


async def main():
    # --------------------------------------------------
    # Scenario 1: Retrieve an existing session
    # --------------------------------------------------

    created_session = await SessionService.create_session(
        user_id="test-user-123"
    )

    session_id = created_session["session_id"]

    retrieved_session = await SessionService.get_session(
        session_id
    )

    print("\n--- Scenario 1: Existing Session ---")
    print("Created Session:")
    print(created_session)

    print("\nRetrieved Session:")
    print(retrieved_session)

    print("\nSession Found:")
    print(retrieved_session is not None)

    # --------------------------------------------------
    # Scenario 2: Retrieve a non-existing session
    # --------------------------------------------------

    fake_session_id = str(uuid4())

    missing_session = await SessionService.get_session(
        fake_session_id
    )

    print("\n--- Scenario 2: Non-Existing Session ---")
    print("Fake Session ID:")
    print(fake_session_id)

    print("\nRetrieved Session:")
    print(missing_session)

    print("\nSession Not Found:")
    print(missing_session is None)  


if __name__ == "__main__":
    asyncio.run(main())    