import os
import jwt
import logging
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.UserJWTData import UserJWTData
from app.models.zup.employee import Employee
from app.database.connection import get_db
from app.database.zup.crud_zup_employees import get_employee_by_login_or_email
from app.services.zup.zup_integration import sync_all_data

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
                "Секретный ключ JWT не настроен. Токен декодирования без проверки подписи! "
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

def get_user_permissions_from_token(token: str) -> Optional[Dict[str, Dict[str, bool]]]:
    """
    Получает права пользователя из JWT-токена.
    Permissions в токене хранятся как массив:
    [{"name_group": "computer", "read": false, "write": false}, ...]

    Конвертирует в словарь для удобной работы:
    {"computer": {"read": False, "write": False}, ...}
    """
    try:
        payload = decode_token(token)

        # Permissions могут быть в разных форматах
        permissions_raw = payload.get("permissions", [])

        # Если permissions - это массив
        if isinstance(permissions_raw, list):
            permissions_dict = {}
            for perm in permissions_raw:
                name_group = perm.get("name_group")
                if name_group:
                    permissions_dict[name_group] = {
                        "read": perm.get("read", False),
                        "write": perm.get("write", False)
                    }
            return permissions_dict

        # Если permissions уже словарь (для обратной совместимости)
        elif isinstance(permissions_raw, dict):
            return permissions_raw

        return None
    except Exception as e:
        logger.error(f"Ошибка получения permissions из токена: {e}")
        return None

async def require_authorized_user(
        request: Request,
        db: AsyncSession = Depends(get_db)
) -> Employee:
    """
    Проверяет авторизацию и возвращает сотрудника из ZUP.
    Все данные берутся из JWT-токена.
    """
    try:
        token = await get_token_from_request(request)
        user_data = get_user_from_token(token)

        if user_data.is_expired:
            logger.warning("Срок действия токена истек")
            raise HTTPException(status_code=401, detail="Срок действия токена истек")

        # === Системные пользователи ===
        if user_data.login in ["root", "read", "write", "android", "pc_data"]:
            class SystemEmployee:
                def __init__(self, login):
                    self.employee_id = login
                    self.login = login
                    self.email = f"{login}@system.local"
                    self.dismissal_date = None
            return SystemEmployee(user_data.login)

        # === Обычные пользователи ===
        # Ищем сотрудника в БД по login или email
        employee = await get_employee_by_login_or_email(
            db,
            login=user_data.login,
            email=user_data.email
        )

        if not employee:
            logger.info(f"Сотрудник {user_data.login} не найден. Попытка синхронизации из 1С...")
            try:
                await sync_all_data(db)
                employee = await get_employee_by_login_or_email(
                    db,
                    login=user_data.login,
                    email=user_data.email
                )
            except Exception as e:
                logger.error(f"Ошибка синхронизации из 1С: {e}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Сотрудник {user_data.login} не найден и синхронизация не удалась"
                )

        if not employee:
            raise HTTPException(
                status_code=404,
                detail=f"Сотрудник {user_data.login} не найден в системе"
            )

        # Проверяем, действующий ли сотрудник
        if employee.dismissal_date:
            logger.warning(f"Сотрудник {user_data.login} уволен")
            raise HTTPException(status_code=403, detail="Учетная запись сотрудника деактивирована")

        return employee

    except TokenValidationError as e:
        logger.warning(f"Недопустимый токен: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Недопустимый токен: {str(e)}")

async def get_current_user_id(
        current_user: Employee = Depends(require_authorized_user)
) -> str:
    """
    Зависимость для получения employee_id текущего авторизованного сотрудника.
    """
    return current_user.employee_id

async def extract_login_from_request(request: Request) -> dict:
    """
    Извлекает login из токена.
    Возвращает dict с login.
    """
    try:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        else:
            token = request.cookies.get("session_token")
            if not token:
                return {"login": None}

        payload = jwt.decode(
            token,
            key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
            algorithms=["HS256"],
            options={
                "verify_signature": bool(JWT_SECRET_KEY),
                "verify_exp": False,
                "verify_iat": False
            }
        )
        login = payload.get("login")
        return {"login": login}

    except Exception as e:
        logger.error(f"Ошибка извлечения login: {str(e)}")
        return {"login": None}