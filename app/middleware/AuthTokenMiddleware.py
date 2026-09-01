import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from app.services.auth.auth_service import get_user_from_token, TokenValidationError

logger = logging.getLogger(__name__)

# Эндпоинты, которые не требуют проверки токена
EXCLUDED_PATHS = {
    "/api/auth_token",
    "/api/login",
    "/api/logout",
    "/api/pc-data",
    "/openapi.json",
    "/",
}

class AuthTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Пропускаем все методы OPTIONS чтобы не засорять логи
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        method = request.method

        if not path.startswith("/api/android-data"):
            logger.debug(f"[AuthTokenMiddleware] Обработка запроса: {method} {path}")

        # Пропускаем исключённые пути
        if path in EXCLUDED_PATHS or path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/api/android-data"):
            if not path.startswith("/api/android-data"):
                logger.debug(f"[AuthTokenMiddleware] Путь исключён из проверки: {path}")
            return await call_next(request)

        # === Извлечение токена ===
        token = None
        token_source = None

        # 1. Из заголовка Authorization: Bearer <token>
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            token_source = "Authorization header"
            logger.debug("[AuthTokenMiddleware] Токен найден в заголовке Authorization")

        # 2. Из куки session_token
        if not token:
            token = request.cookies.get("session_token")
            if token:
                token = token.strip()
                token_source = "cookie session_token"
                logger.debug("[AuthTokenMiddleware] Токен найден в cookie session_token")

        # Если токен не найден — пропускаем (require_authorized_user сам вернёт 401)
        if not token:
            logger.debug(f"[AuthTokenMiddleware] Токен не найден в запросе {method} {path}")
            return await call_next(request)

        logger.debug(f"[AuthTokenMiddleware] Токен получен из источника: {token_source}")

        # === Проверка валидности токена ===
        try:
            user_data = get_user_from_token(token)

            if user_data.is_expired:
                logger.warning(f"[AuthTokenMiddleware] Токен просрочен для login={user_data.login}")
                return await call_next(request)

            logger.debug(f"[AuthTokenMiddleware] Токен валиден для пользователя {user_data.login}")

        except TokenValidationError as e:
            logger.warning(f"[AuthTokenMiddleware] Недопустимый токен: {str(e)}")
        except Exception as e:
            logger.error(f"[AuthTokenMiddleware] Ошибка проверки токена: {str(e)}", exc_info=True)

        logger.debug(f"[AuthTokenMiddleware] Запрос {method} {path} передан дальше")
        return await call_next(request)