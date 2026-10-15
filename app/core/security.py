import jwt

from app.core.config import settings


async def verify_token(token: str) -> dict | None:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )
    return {
        "user_id": int(payload.get("sub"))
    }
