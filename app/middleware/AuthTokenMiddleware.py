# import logging
# import json
# import jwt
# from datetime import datetime
#
# from fastapi import Request
# from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
# from starlette.responses import Response
#
# from app.services.auth.auth_service import (
#     get_user_from_token,
#     create_or_update_user_from_token,
#     TokenValidationError,
#     JWT_SECRET_KEY,
# )
# from app.services.redis.redis_client import redis_client
# from app.database.connection import async_session
#
# logger = logging.getLogger(__name__)
#
# # Эндпоинты, которые не требуют автоматической авторизации
# EXCLUDED_PATHS = {
#     "/api/auth_token",
#     "/api/login",
#     "/api/logout",
#     "/docs",
#     "/api/android-data",
#     "/api/pc-data",
#     "/redoc",
#     "/openapi.json",
#     "/",
# }
#
#
# async def _auto_auth_logic(token: str) -> None:
#     """
#     Логика автоматической авторизации (повторяет /api/auth_token).
#     Декодирует токен, создаёт/обновляет пользователя в БД, сохраняет сессию в Redis.
#     """
#     try:
#         logger.info("Начало автоматической авторизации пользователя")
#         user_data = get_user_from_token(token)
#
#         if user_data.is_expired:
#             logger.warning(
#                 f"Автоматическая авторизация прервана: срок действия токена истёк "
#                 f"(login={user_data.login})"
#             )
#             return
#
#         # Создаём/обновляем пользователя в БД
#         logger.info(f"Создание/обновление пользователя в БД: {user_data.login}")
#         async with async_session() as db:
#             await create_or_update_user_from_token(db, user_data)
#
#         # Декодируем токен для получения TTL
#         payload = jwt.decode(
#             token,
#             key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
#             algorithms=["HS256"],
#             options={
#                 "verify_signature": bool(JWT_SECRET_KEY),
#                 "verify_exp": False,
#                 "verify_iat": False,
#             },
#         )
#
#         exp = payload.get("exp")
#         ttl = int(exp - datetime.now().timestamp()) if exp else 3600
#         ttl = max(ttl, 60)
#         logger.debug(f"Вычислен TTL сессии: {ttl} секунд")
#
#         # Сохраняем сессию в Redis
#         session_key = f"session:{user_data.login}"
#         session_data = {"token": token, "login": user_data.login}
#         await redis_client.set(session_key, json.dumps(session_data), ex=ttl)
#         logger.info(f"Сессия сохранена в Redis: ключ={session_key}, TTL={ttl}с")
#
#         logger.info(f"Автоматическая авторизация выполнена для пользователя: {user_data.login}")
#
#     except TokenValidationError as e:
#         logger.warning(f"Автоматическая авторизация: недопустимый токен: {str(e)}")
#     except Exception as e:
#         logger.error(f"Автоматическая авторизация: внутренняя ошибка: {str(e)}", exc_info=True)
#
#
# class AuthTokenMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
#         path = request.url.path
#         method = request.method
#
#         logger.debug(f"[AuthTokenMiddleware] Обработка запроса: {method} {path}")
#
#         # Пропускаем исключённые пути
#         if path in EXCLUDED_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
#             logger.debug(f"[AuthTokenMiddleware] Путь исключён из проверки: {path}")
#             return await call_next(request)
#
#         # Пытаемся извлечь токен
#         token = None
#         token_source = None
#
#         # 1. Из заголовка Authorization: Bearer <token>
#         auth_header = request.headers.get("Authorization")
#         if auth_header and auth_header.startswith("Bearer "):
#             token = auth_header[7:].strip()
#             token_source = "Authorization header"
#             logger.debug(f"[AuthTokenMiddleware] Токен найден в заголовке Authorization")
#
#         # 2. Из куки session_token
#         if not token:
#             token = request.cookies.get("session_token")
#             if token:
#                 token = token.strip()
#                 token_source = "cookie session_token"
#                 logger.debug(f"[AuthTokenMiddleware] Токен найден в cookie session_token")
#
#         # Если токен не найден — пропускаем (require_authorized_user сам вернёт 401)
#         if not token:
#             logger.debug(f"[AuthTokenMiddleware] Токен не найден в запросе {method} {path}")
#             return await call_next(request)
#
#         logger.debug(f"[AuthTokenMiddleware] Токен получен из источника: {token_source}")
#
#         # Если токен найден — проверяем наличие сессии в Redis
#         try:
#             # Декодируем токен для получения login
#             payload = jwt.decode(
#                 token,
#                 key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
#                 algorithms=["HS256"],
#                 options={
#                     "verify_signature": bool(JWT_SECRET_KEY),
#                     "verify_exp": False,
#                     "verify_iat": False,
#                 },
#             )
#             login = payload.get("login")
#
#             if not login:
#                 logger.warning(f"[AuthTokenMiddleware] В токене отсутствует поле 'login'")
#                 return await call_next(request)
#
#             logger.debug(f"[AuthTokenMiddleware] Извлечён login из токена: {login}")
#
#             session_key = f"session:{login}"
#             session_data = await redis_client.get(session_key)
#
#             # Если сессии нет в Redis — выполняем автоматическую авторизацию
#             if not session_data:
#                 logger.info(
#                     f"[AuthTokenMiddleware] Сессия не найдена в Redis для пользователя {login}. "
#                     f"Запускаем автоматическую авторизацию."
#                 )
#                 await _auto_auth_logic(token)
#             else:
#                 logger.debug(
#                     f"[AuthTokenMiddleware] Сессия найдена в Redis для пользователя {login}"
#                 )
#         except jwt.PyJWTError as e:
#             logger.warning(f"[AuthTokenMiddleware] Ошибка декодирования JWT: {str(e)}")
#         except Exception as e:
#             logger.error(f"[AuthTokenMiddleware] Ошибка проверки сессии: {str(e)}", exc_info=True)
#
#         logger.debug(f"[AuthTokenMiddleware] Запрос {method} {path} передан дальше")
#         return await call_next(request)