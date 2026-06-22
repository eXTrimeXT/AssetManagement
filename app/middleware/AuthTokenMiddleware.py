import logging
import json
import jwt
from datetime import datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.service.auth.auth_service import (
    get_user_from_token,
    create_or_update_user_from_token,
    TokenValidationError,
    JWT_SECRET_KEY,
)
from app.service.redis.redis_client import redis_client
from app.database.connection import async_session

logger = logging.getLogger(__name__)

# Эндпоинты, которые не требуют автоматической авторизации
EXCLUDED_PATHS = {
    "/api/auth_token",
    "/api/login",
    "/api/logout",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/",
}


async def _auto_auth_logic(token: str) -> None:
    """
    Логика автоматической авторизации (повторяет /api/auth_token).
    Декодирует токен, создаёт/обновляет пользователя в БД, сохраняет сессию в Redis.
    """
    try:
        user_data = get_user_from_token(token)

        if user_data.is_expired:
            logger.warning("Автоматическая авторизация: срок действия токена истек")
            return

        # Создаём/обновляем пользователя в БД
        async with async_session() as db:
            await create_or_update_user_from_token(db, user_data)

        # Декодируем токен для получения TTL
        payload = jwt.decode(
            token,
            key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
            algorithms=["HS256"],
            options={
                "verify_signature": bool(JWT_SECRET_KEY),
                "verify_exp": False,
                "verify_iat": False,
            },
        )

        exp = payload.get("exp")
        ttl = int(exp - datetime.utcnow().timestamp()) if exp else 3600
        ttl = max(ttl, 60)

        # Сохраняем сессию в Redis
        session_key = f"session:{user_data.login}"
        session_data = {"token": token, "login": user_data.login}
        await redis_client.set(session_key, json.dumps(session_data), ex=ttl)

        logger.info(f"Автоматическая авторизация выполнена для пользователя: {user_data.login}")

    except TokenValidationError as e:
        logger.warning(f"Автоматическая авторизация: недопустимый токен: {str(e)}")
    except Exception as e:
        logger.error(f"Автоматическая авторизация: внутренняя ошибка: {str(e)}")


class AuthTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Пропускаем исключённые пути
        if path in EXCLUDED_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # Пытаемся извлечь токен
        token = None

        # 1. Из заголовка Authorization: Bearer <token>
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

        # 2. Из куки session_token
        if not token:
            token = request.cookies.get("session_token")
            if token:
                token = token.strip()

        # Если токен найден — проверяем наличие сессии в Redis
        if token:
            try:
                # Декодируем токен для получения login
                payload = jwt.decode(
                    token,
                    key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
                    algorithms=["HS256"],
                    options={
                        "verify_signature": bool(JWT_SECRET_KEY),
                        "verify_exp": False,
                        "verify_iat": False,
                    },
                )
                login = payload.get("login")

                if login:
                    session_key = f"session:{login}"
                    session_data = await redis_client.get(session_key)

                    # Если сессии нет в Redis — выполняем автоматическую авторизацию
                    if not session_data:
                        logger.info(f"Сессия не найдена для пользователя {login}, выполняем автоматическую авторизацию")
                        await _auto_auth_logic(token)
            except Exception as e:
                logger.error(f"Ошибка проверки сессии: {str(e)}")

        return await call_next(request)