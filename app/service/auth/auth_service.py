import os
import jwt
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.UserJWTData import UserJWTData
from app.models.User import User
from app.database.crud_users import get_user_by_tab_id
from app.database.connection import get_db
from app.service.redis.redis_client import redis_client

logger = logging.getLogger(__name__)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

class TokenValidationError(Exception):
    pass

security = HTTPBearer(auto_error=False)  # auto_error=False — чтобы не выбрасывал 403, если нет заголовка

async def get_token_from_request(request: Request) -> str:
    """
    Получает токен из:
    1. Заголовка Authorization: Bearer <token>
    2. Куки session_token
    """
    # 1. Пробуем взять из заголовка
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    # 2. Пробуем взять из куки
    token = request.cookies.get("session_token")
    if token:
        return token.strip()

    raise HTTPException(status_code=401, detail="Токен не предоставлен")

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
    except Exception:
        # Любая ошибка → возвращаем None, чтобы не ломать запрос
        return None

async def get_session_from_redis(login: str) -> Optional[Dict[str, Any]]:
    session_key = f"session:{login}"
    data = await redis_client.get(session_key)
    return json.loads(data) if data else None

async def require_authorized_user(
        request: Request,
        db: AsyncSession = Depends(get_db)
) -> User:
    # pass
    try:
        token = await get_token_from_request(request)
        user_data = get_user_from_token(token)

        if user_data.is_expired:
            raise HTTPException(status_code=401, detail="Срок действия токена истек")

        session = await get_session_from_redis(user_data.login)
        if not session or session.get("token") != token:
            raise HTTPException(status_code=401, detail="Недействительный или просроченный сеанс")

        db_user = await get_user_by_tab_id(db, user_data.login)
        if not db_user:
            raise HTTPException(
                status_code=403,
                detail="Пользователь не найден в базе данных. Войдите в систему через /api/login или /api/auth_token"
            )

        if not db_user.is_active:
            raise HTTPException(status_code=403, detail="Учетная запись пользователя деактивирована")

        return db_user

    except TokenValidationError as e:
        raise HTTPException(status_code=401, detail=f"Недопустимый токен: {str(e)}")

async def get_current_user_id(
        current_user: User = Depends(require_authorized_user)
) -> int:
    """
    Зависимость для получения ID текущего авторизованного пользователя.
    Используется в эндпоинтах, где нужен только user_id для аудита/логирования.
    """
    return current_user.user_id

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
        # logger.info(f"{payload=}")
        # print(f"{payload=}")
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenValidationError("Срок действия токена истек")
    except jwt.InvalidTokenError as e:
        raise TokenValidationError(f"Недопустимый токен: {str(e)}")

def get_user_from_token(token: str, secret_key: Optional[str] = None) -> UserJWTData:
    key = secret_key or JWT_SECRET_KEY
    payload = decode_token(token, key)
    # logger.info(f"{payload}")
    return UserJWTData(payload)

def is_token_valid(token: str, secret_key: Optional[str] = None) -> bool:
    key = secret_key or JWT_SECRET_KEY
    try:
        decode_token(token, key)
        return True
    except TokenValidationError:
        return False


async def create_or_update_user_from_token(
        db: AsyncSession,
        user_data: UserJWTData
) -> User:
    existing_user = await get_user_by_tab_id(db, user_data.login)

    if existing_user:
        existing_user.user_en_name = user_data.fullname
        existing_user.owner = user_data.fullname
        existing_user.email = user_data.email
        # existing_user.department_id = user_data.department_id
        # === Сохраняем права в новом формате ===
        existing_user.permissions = user_data.permissions
        existing_user.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(existing_user)
        return existing_user
    else:
        new_user = User(
            user_tab_id=user_data.login,
            user_en_name=user_data.fullname,
            owner=user_data.fullname,
            email=user_data.email,
            # department_id=user_data.department_id,
            permissions=user_data.permissions,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user