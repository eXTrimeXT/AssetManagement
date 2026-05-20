import logging
import uuid
import time
import os
import json
import structlog
from datetime import datetime
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.service.auth.auth_service import extract_login_from_request

# === НАСТРОЙКА ЛОГИРОВАНИЯ В ФАЙЛ ===
LOG_DIR = "/logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Создаём директорию, если не существует
os.makedirs(LOG_DIR, exist_ok=True)

# Файловый хендлер с ротацией (опционально)
file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)

# Форматтер для файла (текстовый или JSON)
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "user_login"):
            log_entry["user_login"] = record.user_login
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        return json.dumps(log_entry, ensure_ascii=False)

file_handler.setFormatter(JSONFormatter())

# Настройка root-логгера
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Убираем дублирующиеся хендлеры
root_logger.handlers = [h for h in root_logger.handlers if not isinstance(h, logging.FileHandler)]
root_logger.addHandler(file_handler)

# === НАСТРОЙКА STRUCTLOG (для консоли/отладки) ===
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if os.getenv("ENV", "dev") == "dev" else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Генерируем уникальный ID запроса
        request_id = str(uuid.uuid4())

        # Извлекаем логин пользователя (если есть)
        user_login = await extract_login_from_request(request)

        # Создаём логгер с контекстом
        log = logger.bind(
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            user_login=user_login
        )

        # Добавляем контекст в стандартный logging (для file_handler)
        std_log = logging.getLogger("app.requests")
        std_log_extra = {
            "request_id": request_id,
            "user_login": user_login
        }

        start_time = time.time()

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Логируем успех
            log.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(process_time * 1000, 2)
            )
            std_log.info(
                f"{request.method} {request.url.path} - {response.status_code}",
                extra={**std_log_extra, "duration_ms": round(process_time * 1000, 2), "status_code": response.status_code}
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            # Логируем ошибку
            log.error(
                "request_failed",
                error=str(e),
                duration_ms=round(process_time * 1000, 2),
                exc_info=True
            )
            std_log.error(
                f"{request.method} {request.url.path} - ERROR: {str(e)}",
                extra={**std_log_extra, "duration_ms": round(process_time * 1000, 2), "exc_info": True},
                exc_info=True
            )
            raise