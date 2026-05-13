import os
import jwt
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import Security, Depends, HTTPException, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.UserJWTData import UserJWTData
from app.models.User import User
from app.database.crud_users import get_user_by_tab_id
from app.database.connection import get_db

logger = logging.getLogger(__name__)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

class TokenValidationError(Exception):
    """Исключение при ошибке валидации токена"""
    pass

# Создаём экземпляр схемы безопасности
security = HTTPBearer()

# === Dependency: получение токена из Security (Swagger-friendly) ===
async def get_token_from_security(
        credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """
    Извлекает токен из заголовка Authorization: Bearer <token>
    Работает как с curl, так и с Swagger UI (кнопка Authorize).
    """
    return credentials.credentials.strip()


# === Dependency для проверки авторизации ===
async def require_authorized_user(
        token: str = Depends(get_token_from_security),
        db: AsyncSession = Depends(get_db)
) -> User:
    """
    Проверяет токен и наличие пользователя в таблице Users.
    Возвращает пользователя из БД или выбрасывает 401/403.
    """
    try:
        user_data = get_user_from_token(token)

        if user_data.is_expired:
            raise HTTPException(status_code=401, detail="Token expired")

        db_user = await get_user_by_tab_id(db, user_data.login)
        if not db_user:
            raise HTTPException(
                status_code=403,
                detail="User not found in database. Please login first via /api/validate-token"
            )

        if not db_user.is_active:
            raise HTTPException(status_code=403, detail="User account is deactivated.")

        return db_user

    except TokenValidationError as e:
        raise HTTPException(status_code=401, detail=str(e))

def decode_token(token: str, secret_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Декодирует JWT токен и возвращает его payload.

    Args:
        token: JWT токен
        secret_key: Секретный ключ для проверки подписи.
                   Если None и JWT_SECRET_KEY не задан — декодирование без проверки подписи
                   (НЕ ДЛЯ ПРОДАКШЕНА!).

    Returns:
        Dict с данными из payload токена

    Raises:
        TokenValidationError: Если токен невалиден, просрочен или подпись не совпадает
    """
    key = secret_key or JWT_SECRET_KEY
    try:
        if key:
            # Проверяем подпись и срок действия
            payload = jwt.decode(
                token,
                key=key,
                algorithms=["HS256"],
                options={"verify_exp": True}
            )
            logger.warning(f"{payload=}")
        else:
            # ТОЛЬКО ДЛЯ ТЕСТОВ: декодируем без проверки подписи
            logger.warning(
                "JWT secret key not configured. Decoding token without signature verification! "
                "Set JWT_SECRET_KEY for production."
            )
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True}
            )
            # logger.warning(f"{payload=}")
        return payload

    except jwt.ExpiredSignatureError:
        raise TokenValidationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise TokenValidationError(f"Invalid token: {str(e)}")


def get_user_from_token(token: str, secret_key: Optional[str] = None) -> UserJWTData:
    """
    Извлекает и возвращает данные пользователя из JWT токена.

    Args:
        token: JWT токен
        secret_key: Секретный ключ для проверки подписи (опционально)

    Returns:
        UserData объект с данными пользователя

    Raises:
        TokenValidationError: Если токен невалиден или истек
    """
    key = secret_key or JWT_SECRET_KEY
    payload = decode_token(token, key)
    return UserJWTData(payload)


def is_token_valid(token: str, secret_key: Optional[str] = None) -> bool:
    """
    Проверяет валидность токена (подпись + срок действия).

    Args:
        token: JWT токен
        secret_key: Секретный ключ для проверки подписи (опционально)

    Returns:
        True если токен валиден, иначе False
    """
    key = secret_key or JWT_SECRET_KEY
    try:
        decode_token(token, key)
        return True
    except TokenValidationError:
        return False


def parse_distinguished_name(dn: str | None) -> dict[str, Any]:
    """
    Парсит distinguishedName из JWT токена.
    Пример: CN=Timur Malyshev,OU=INFORMATION SYSTEMS SUPPORT SECTION (ISSS),OU=Users,OU=HMMR,DC=local

    Returns: {'CN': str, 'OU': list[str], 'DC': list[str]}
    """
    if not dn:
        return {'CN': None, 'OU': [], 'DC': []}

    result = {'CN': None, 'OU': [], 'DC': []}

    for part in dn.split(','):
        if '=' in part:
            key, value = part.split('=', 1)
            key, value = key.strip(), value.strip()
            if key == 'CN':
                result['CN'] = value
            elif key == 'OU':
                result['OU'].append(value)
            elif key == 'DC':
                result['DC'].append(value)

    return result


def extract_role_from_dn(dn: str | None) -> str | None:
    """
    Извлекает роль из distinguishedName.
    Логика: если в OU есть 'Users' → роль = 'user'.
    Можно расширить под другие OU (Admins, Managers и т.д.).
    """
    parsed = parse_distinguished_name(dn)
    ou_list = parsed.get('OU', [])

    if 'Users' in ou_list:
        return 'user'
    # if 'Admins' in ou_list: return 'admin'  # Пример расширения
    return 'user'  # Default fallback


async def create_or_update_user_from_token(
        db: AsyncSession,
        user_data: UserJWTData
) -> User:
    """
    Создает или обновляет запись пользователя в таблице Users
    на основе данных из JWT токена.

    Маппинг полей:
    - user_tab_id = login
    - user_en_name = fullname
    - owner = fullname
    - email = email
    - department = department
    - role = распарсить из distinguished_name (OU=Users)
    """
    role = extract_role_from_dn(user_data.distinguished_name)

    existing_user = await get_user_by_tab_id(db, user_data.login)

    if existing_user:
        # Обновляем существующего
        existing_user.user_en_name = user_data.fullname
        existing_user.owner = user_data.fullname
        existing_user.email = user_data.email
        existing_user.department = user_data.department
        if role:
            existing_user.role = role
        existing_user.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(existing_user)
        return existing_user
    else:
        # Создаем нового
        new_user = User(
            user_tab_id=user_data.login,
            user_en_name=user_data.fullname,
            owner=user_data.fullname,
            email=user_data.email,
            department=user_data.department,
            role=role,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user