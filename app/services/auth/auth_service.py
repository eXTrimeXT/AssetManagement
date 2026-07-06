import os
import jwt
import json
import logging
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.UserJWTData import UserJWTData
from app.models.zup.employee import Employee
from app.database.connection import get_db
from app.database.zup.crud_zup_employees import get_employee_by_login_or_email, get_employee_by_id
from app.services.redis.redis_client import redis_client
from app.services.zup.zup_integration import sync_all_data  # Добавлено для автосинхронизации

logger = logging.getLogger(__name__)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")


class TokenValidationError(Exception):
    pass


security = HTTPBearer(auto_error=False)


async def get_token_from_request(request: Request) -> str:
    """
    Получает токен из:
    1. Заголовка Authorization: Bearer <token>
    2. Куки session_token
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    token = request.cookies.get("session_token")
    if token:
        return token.strip()

    logger.warning("Токен не предоставлен")
    raise HTTPException(status_code=401, detail="Токен не предоставлен")


async def require_authorized_user(
        request: Request,
        db: AsyncSession = Depends(get_db)
) -> Employee:
    try:
        token = await get_token_from_request(request)
        user_data = get_user_from_token(token)

        if user_data.is_expired:
            raise HTTPException(status_code=401, detail="Срок действия токена истек")

        session = await get_session_from_redis(user_data.login)
        if not session or session.get("token") != token:
            raise HTTPException(status_code=401, detail="Недействительный или просроченный сеанс")

        # === Получаем employee_id из Redis ===
        employee_id = session.get("employee_id")

        if not employee_id:
            # Если employee_id нет в Redis — ищем в БД
            employee = await get_employee_by_login_or_email(
                db,
                login=user_data.login,
                email=user_data.email
            )
            if not employee:
                raise HTTPException(status_code=404, detail="Сотрудник не найден")
            employee_id = employee.employee_id

        # === Создаём объект Employee с employee_id ===
        # Для системных пользователей создаём заглушку
        if user_data.login in ["root", "read", "write", "android", "pc_data"]:
            pass
            # return create_system_employee(user_data.login)

        # Для обычных пользователей — ищем в БД
        employee = await get_employee_by_id(db, employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail="Сотрудник не найден")

        if employee.dismissal_date:
            raise HTTPException(status_code=403, detail="Сотрудник уволен")

        return employee

    except TokenValidationError as e:
        raise HTTPException(status_code=401, detail=f"Недопустимый токен: {str(e)}")


async def get_current_user_id(
        current_user: Employee = Depends(require_authorized_user)
) -> str:
    """
    Зависимость для получения employee_id текущего авторизованного сотрудника.
    """
    return current_user.employee_id

async def get_employee_id_from_redis(login: str) -> Optional[str]:
    """Получает employee_id из Redis"""
    session = await get_session_from_redis(login)
    if session:
        return session.get("employee_id")
    return None


def decode_token(token: str, secret_key: Optional[str] = None) -> Dict[str, Any]:
    key = secret_key or JWT_SECRET_KEY
    try:
        if key:
            payload = jwt.decode(
                token,
                key=key,
                algorithms=["HS256"],
                options={"verify_exp": True}
            )
        else:
            logger.warning(
                "Секретный ключ JWT не настроен. Токен декодирования без проверки подписи!"
                "Установите JWT_SECRET_KEY для работы."
            )
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True}
            )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Срок действия токена истек")
        raise TokenValidationError("Срок действия токена истек")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Недопустимый токен: {str(e)}")
        raise TokenValidationError(f"Недопустимый токен: {str(e)}")

def get_user_from_token(token: str, secret_key: Optional[str] = None) -> UserJWTData:
    key = secret_key or JWT_SECRET_KEY
    payload = decode_token(token, key)
    return UserJWTData(payload)

def is_token_valid(token: str, secret_key: Optional[str] = None) -> bool:
    key = secret_key or JWT_SECRET_KEY
    try:
        decode_token(token, key)
        return True
    except TokenValidationError:
        logger.error("Исключение: TokenValidationError")
        return False

async def get_session_from_redis(login: str) -> Optional[Dict[str, Any]]:
    """Получить данные сессии из Redis"""
    session_key = f"session:{login}"
    session_data = await redis_client.get(session_key)
    if session_data:
        return json.loads(session_data)
    return None


async def get_user_permissions_from_redis(login: str) -> Optional[dict]:
    """
    Получает права пользователя из Redis.
    Возвращает словарь прав или None, если сессия не найдена.
    """
    session = await get_session_from_redis(login)
    if session:
        return session.get("permissions", {})
    return None


# === Извлечение login из токена для логирования ===
async def extract_login_from_request(request: Request) -> Optional[str]:
    """
    Пытается извлечь login из токена (заголовок или куки).
    Возвращает login или None, если токен отсутствует/невалиден.
    Не выбрасывает исключения — для безопасного использования в мидлваре.
    """
    try:
        # 1. Пробуем взять токен из заголовка Authorization
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        else:
            # 2. Пробуем взять из куки
            token = request.cookies.get("session_token")
            if not token:
                return None

        # Декодируем токен БЕЗ строгой проверки (только для логирования)
        payload = jwt.decode(
            token,
            key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
            algorithms=["HS256"],
            options={
                "verify_signature": bool(JWT_SECRET_KEY),
                "verify_exp": False,  # не блокируем логирование, если токен просрочен
                "verify_iat": False
            }
        )
        return payload.get("login")
    except Exception as e:
        # Любая ошибка → возвращаем None, чтобы не ломать запрос
        logger.error(f"Ошибка: {str(e)}")
        return None


async def extract_employee_id_from_request(request: Request) -> Optional[str]:
    """
    Извлекает employee_id из Redis-сессии по login из токена.
    Возвращает employee_id или None, если не удалось получить.
    Не выбрасывает исключения — для безопасного использования в мидлваре.
    """
    try:
        # 1. Получаем login из токена
        login = await extract_login_from_request(request)
        if not login:
            return None

        # 2. Получаем employee_id из Redis-сессии
        session = await get_session_from_redis(login)
        if session:
            return session.get("employee_id")

        return None
    except Exception as e:
        logger.error(f"Ошибка извлечения employee_id: {str(e)}")
        return None


async def extract_user_info_from_request(request: Request) -> dict:
    """
    Извлекает login и employee_id из токена (заголовок или куки).
    Возвращает dict с login и employee_id.
    Не выбрасывает исключения — для безопасного использования в мидлваре.
    """
    try:
        # 1. Пробуем взять токен из заголовка Authorization
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        else:
            # 2. Пробуем взять из куки
            token = request.cookies.get("session_token")
            if not token:
                return {"login": None, "employee_id": None}

        # Декодируем токен БЕЗ строгой проверки (только для логирования)
        payload = jwt.decode(
            token,
            key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
            algorithms=["HS256"],
            options={
                "verify_signature": bool(JWT_SECRET_KEY),
                "verify_exp": False,  # не блокируем логирование, если токен просрочен
                "verify_iat": False
            }
        )

        login = payload.get("login")
        employee_id = payload.get("employee_id")

        # Если employee_id нет в токене — пробуем получить из Redis (fallback для старых токенов)
        if not employee_id and login:
            session = await get_session_from_redis(login)
            if session:
                employee_id = session.get("employee_id")

        return {"login": login, "employee_id": employee_id}
    except Exception as e:
        logger.error(f"Ошибка извлечения user_info: {str(e)}")
        return {"login": None, "employee_id": None}