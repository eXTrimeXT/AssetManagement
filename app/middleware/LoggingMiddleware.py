import logging
import uuid
import time
import sys
import json
import re
import traceback
import structlog
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.services.auth.auth_service import extract_login_from_request

# === КОНФИГУРАЦИЯ ===
PROJECT_ROOT = Path("/app")
LOG_DIR = Path("/logs")
LOG_FILE = LOG_DIR / "app.log"
EXCLUDED_MODULE = "LoggingMiddleware"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Regex для ANSI-кодов
ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')

def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub('', text)

def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub('', text)


def _sanitize_data(data: any, sensitive_keys: set = None) -> any:
    """
    Рекурсивно маскирует чувствительные поля в dict/list.
    """
    if sensitive_keys is None:
        sensitive_keys = {
            "password", "passwd", "pwd", "secret", "token", "api_key",
            "access_token", "refresh_token", "private_key", "credential"
        }

    if isinstance(data, dict):
        return {
            k: "***" if k.lower() in sensitive_keys else _sanitize_data(v, sensitive_keys)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [_sanitize_data(item, sensitive_keys) for item in data]
    else:
        return data

def _get_relative_path(filepath: str) -> str:
    try:
        return str(Path(filepath).relative_to(PROJECT_ROOT))
    except ValueError:
        return filepath

# === ФОРМАТТЕР ДЛЯ КОНСОЛИ ===
class ConsoleFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m", "INFO": "\033[32m", "WARNING": "\033[33m",
        "ERROR": "\033[31m", "CRITICAL": "\033[35m", "RESET": "\033[0m",
        "BOLD": "\033[1m", "GRAY": "\033[90m"
    }

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = record.levelname
        color = self.COLORS.get(level, self.COLORS["RESET"])
        # Путь до файла (middleware видит только url, а не путь к файлу эндпоинта)
        # Поэтому логировать надо внутри эндпоинта
        # Тогда будет точно видно номер строки
        rel_path = _get_relative_path(record.pathname)
        msg = _strip_ansi(record.getMessage())

        parts = [
            f"{color}{self.COLORS['BOLD']}{level}{self.COLORS['RESET']}",
            f"{self.COLORS['RESET']}{timestamp}{self.COLORS['RESET']}",
            f"{self.COLORS['GRAY']}[{rel_path}:{record.funcName}:{record.lineno}]{self.COLORS['RESET']}",
            f"- {msg}"
        ]

        ctx = {}
        for key in ["request_id", "client_ip", "user_login", "duration_ms", "query_params", "request_body",
                    "error_type", "error_message", "permission_check"]:
            val = getattr(record, key, None)
            if val is not None:
                ctx[key] = val

        if ctx:
            ctx_str = " | ".join(f"{k}={v}" for k, v in ctx.items())
            parts.append(f"{self.COLORS['GRAY']}[{ctx_str}]{self.COLORS['RESET']}")

        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            filtered = []
            for line in exc_text.split("\n"):
                clean = _strip_ansi(line)
                if "/app/" in clean and EXCLUDED_MODULE not in clean:
                    filtered.append(f"{self.COLORS['GRAY']}{clean}{self.COLORS['RESET']}")
                elif clean.strip() and not any(s in clean for s in ["site-packages", "starlette", "fastapi"]):
                    filtered.append(f"{color}{clean}{self.COLORS['RESET']}")
            if filtered:
                parts.append("\n" + "\n".join(filtered))

        return " ".join(parts)

# === ФОРМАТТЕР ДЛЯ ФАЙЛА (JSON) ===
class FileJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rel_path = _get_relative_path(record.pathname)
        log_entry = {
            "timestamp": datetime.now(ZoneInfo("Europe/Moscow")).isoformat(),
            # "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "level": record.levelname,
            "message": _strip_ansi(record.getMessage()),
            "logger": record.name,
            "location": {
                "filename": Path(record.pathname).name,
                "filepath": rel_path,
                "full_path": record.pathname,
                "function": record.funcName,
                "line": record.lineno,
            },
        }

        for key in [
            "request_id", "client_ip", "user_login", "route", "url",
            "duration_ms", "status_code", "error_type", "error_message",
            "query_params", "request_body", "permission_check"
        ]:
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "value": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": [_strip_ansi(l) for l in traceback.format_exception(*record.exc_info)]
            }

        return json.dumps(log_entry, ensure_ascii=False, default=str)


# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
_logging_configured = False

def setup_logging():
    global _logging_configured
    if _logging_configured:
        return
    _logging_configured = True

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ConsoleFormatter())

    file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(FileJSONFormatter())

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)
    root.propagate = False

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("structlog").setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.stdlib.ExtraAdder(),
            structlog.processors.KeyValueRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


setup_logging()
logger = logging.getLogger("app.middleware")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        user_login = await extract_login_from_request(request)
        client_ip = request.client.host if request.client else None
        route_path = request.url.path
        method = request.method

        request_body = None
        if method in ("POST", "PUT", "PATCH") and request.headers.get("content-type", " ").startswith("application/json"):
            try:
                body = await request.body()
                raw_body = json.loads(body.decode("utf-8"))
                request_body = _sanitize_data(raw_body)  # ← Маскируем перед логированием
                request._body = body  # ← Оригинальное тело сохраняем для дальнейшего использования
            except Exception:
                pass

        # Привязываем контекст ко ВСЕМ логам в рамках этого запроса
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            client_ip=client_ip,
            user_login=user_login,
            route=route_path,
            method=method,
            query_params=dict(request.query_params) if request.query_params else None,
            request_body=request_body
        )

        start_time = time.time()

        try:
            response: Response = await call_next(request)
            process_time = time.time() - start_time
            response_status_code = response.status_code
            # Добавляем ID запроса в заголовок ответа
            response.headers["X-Request-ID"] = request_id

            # Логируем успешный ответ
            log_level = logging.INFO if response_status_code < 400 else logging.WARNING
            logger.log(
                log_level,
                f"{method} {route_path} → {response_status_code}",
                extra={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "user_login": user_login,
                    "url": str(request.url),
                    "duration_ms": round(process_time * 1000, 2),
                    "query_params": dict(request.query_params) if request.query_params else None,
                    "request_body": request_body
                }
            )

            return response

        except HTTPException as e:
            process_time = time.time() - start_time
            response_status_code = e.status_code

            # Логируем HTTP исключение
            logger.error(
                f"{method} {route_path} → HTTP {response_status_code}: {e.detail}",
                exc_info=False,  # HTTP исключения не требуют traceback
                extra={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "user_login": user_login,
                    "url": str(request.url),
                    "duration_ms": round(process_time * 1000, 2),
                    "error_type": "HTTPException",
                    "error_message": str(e.detail),
                    "query_params": dict(request.query_params) if request.query_params else None,
                    "request_body": request_body
                }
            )
            raise

        except Exception as e:
            process_time = time.time() - start_time
            # Логируем внутреннюю ошибку сервера
            logger.error(
                f"{method} {route_path} → ERROR 500: {type(e).__name__}: {str(e)}",
                exc_info=True,  # Внутренние ошибки требуют traceback
                extra={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "user_login": user_login,
                    "url": str(request.url),
                    "duration_ms": round(process_time * 1000, 2),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "query_params": dict(request.query_params) if request.query_params else None,
                    "request_body": request_body
                }
            )
            raise

        finally:
            # Очищаем контекст
            structlog.contextvars.clear_contextvars()