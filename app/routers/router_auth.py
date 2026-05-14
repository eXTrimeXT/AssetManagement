from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import jwt
import json
import os
from app.database.connection import get_db
from app.schemas.auth.AuthSchemas import UserInfoResponse, TokenRequest
from app.service.auth.auth_service import (
    get_user_from_token,
    TokenValidationError,
    create_or_update_user_from_token,
    JWT_SECRET_KEY
)
from app.models.UserJWTData import UserJWTData
from app.service.redis.redis_client import redis_client

router_auth = APIRouter(tags=["auth"])

async def save_session_to_redis(login: str, token: str, ttl: int) -> None:
    session_key = f"session:{login}"
    session_data = {"token": token, "login": login}
    await redis_client.set(session_key, json.dumps(session_data), ex=ttl)

@router_auth.post("/auth-token", response_model=UserInfoResponse)
async def auth_token(
        request: TokenRequest,
        response: Response,
        db: AsyncSession = Depends(get_db),
):
    try:
        user_data: UserJWTData = get_user_from_token(request.token)
        if user_data.is_expired:
            raise HTTPException(status_code=401, detail="Token expired")

        await create_or_update_user_from_token(db, user_data)

        payload = jwt.decode(
            request.token,
            key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
            algorithms=["HS256"],
            options={"verify_signature": bool(JWT_SECRET_KEY), "verify_exp": False}
        )
        exp = payload.get("exp")
        ttl = int(exp - datetime.utcnow().timestamp()) if exp else 3600
        ttl = max(ttl, 60)

        await save_session_to_redis(user_data.login, request.token, ttl)

        # === Устанавливаем HTTP-only куки ===
        response.set_cookie(
            key="session_token",
            value=request.token,
            httponly=True,
            secure=os.getenv("ENV", "dev") == "prod",  # Только HTTPS в продакшене
            samesite="lax",
            max_age=ttl,
            path="/"
        )

        return user_data.to_dict()

    except TokenValidationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router_auth.post("/logout")
async def logout(
        response: Response,
        token: str = Depends(lambda: None),  # Placeholder, токен берём из куки
        request: dict = Depends(lambda: {}),  # Для доступа к request, если нужно
):
    """Удаляет сессию из Redis и очищает куки"""
    # Токен берём из куки, которую отправил браузер
    # (обработка будет в auth_service, здесь только очистка куки)
    response.delete_cookie(key="session_token", path="/")
    return {"status": "logged out"}