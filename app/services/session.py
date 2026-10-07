from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.redis import redis_client


class SessionService:
    """
    Handles lifecycle management of AI chatbot sessions in Redis.
    """

    SESSION_PREFIX = "ai:chat:session"
    INACTIVITY_TTL = 30 * 60  # 30 minutes
    MAX_SESSION_LIFETIME = 4 * 60 * 60  # 4 hours

    @classmethod
    def _build_session_key(cls, session_id: str) -> str:
        """
        Build the Redis key for a chat session.
        """
        return f"{cls.SESSION_PREFIX}:{session_id}"
    
    @classmethod
    async def create_session(cls, user_id: str | None = None) -> dict:
        """
        Create a new chat session and store it in Redis.
        """

        session_id = str(uuid4())

        now = datetime.now(timezone.utc)

        expires_at = now + timedelta(
            seconds=cls.MAX_SESSION_LIFETIME
        )

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": now.isoformat(),
            "last_activity_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        session_key = cls._build_session_key(session_id)

        await redis_client.hset(
            session_key,
            mapping=session_data,
        )

        await redis_client.expire(
            session_key,
            cls.INACTIVITY_TTL,
        )

        return session_data

    @classmethod
    async def get_session(cls, session_id: str) -> dict | None:
        """
        Retrieve an existing chat session from Redis.
        """

        session_key = SessionService._build_session_key(session_id)

        session_data = await redis_client.hgetall(session_key)

        if not session_data:
            return None

        return session_data

