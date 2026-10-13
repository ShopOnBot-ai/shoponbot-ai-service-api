from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status

from app.core.logger import logger
from app.core.security import verify_token


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    logger.info("token: %s", token)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail= "Unauthorized"
        )

    try:
        user_claims = await verify_token(token)
        user_id = int(user_claims["user_id"])

    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None

    return user_id

currentUser = Annotated[int, Depends(get_current_user)]
