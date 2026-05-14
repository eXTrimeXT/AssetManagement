import logging
import uuid
import time
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.service.auth.auth_service import extract_login_from_request

# Настройка structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if __debug__ else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Middleware для логирования каждого запроса
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Генерируем уникальный ID запроса
        request_id = str(uuid.uuid4())

        user_login = await extract_login_from_request(request)

        # Добавляем ID в контекст логов для этого запроса
        log = logger.bind(request_id=request_id, method=request.method, url=str(request.url), user_login=user_login or None)

        start_time = time.time()

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Логируем результат
            log.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(process_time * 1000, 2)
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            # Логируем ошибку
            log.error(
                "request_failed",
                error=str(e),
                duration_ms=round(process_time * 1000, 2),
                exc_info=True # Важно для стектрейса
            )
            raise