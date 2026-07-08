import logging
import jwt
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.database.connection import get_db
from app.schemas.auth.AuthSchemas import UserInfoResponse, TokenRequest, LoginRequest
from app.services.auth.auth_service import (
    get_user_from_token,
    TokenValidationError,
    JWT_SECRET_KEY
)
from app.models.UserJWTData import UserJWTData
from app.models.zup.employee import Employee
from app.services.auth.external_auth import external_login
from app.database.zup import get_employee_by_login_or_email
from app.services.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)
router_auth = APIRouter(tags=["auth"])

async def create_or_update_user_from_token(
        db: AsyncSession,
        user_data: UserJWTData
) -> Employee:
    """
    Создаёт/обновляет сотрудника из 1С и возвращает его.
    """
    employee = await get_employee_by_login_or_email(db, login=user_data.login, email=user_data.email)

    if not employee:
        logger.warning(f"Сотрудник {user_data.login} не найден в БД. Синхронизируйте данные из 1С через /api/zup/sync")
        raise HTTPException(
            status_code=404,
            detail=f"Сотрудник {user_data.login} не найден. Обратитесь к администратору для синхронизации из 1С."
        )

    # Проверяем, действующий ли сотрудник
    if employee.dismissal_date:
        logger.warning(f"Сотрудник {user_data.login} уволен")
        raise HTTPException(status_code=403, detail="Учетная запись сотрудника деактивирована")

    return employee

@router_auth.post("/login", response_model=UserInfoResponse)
async def login_by_credentials(
        credentials: LoginRequest,
        request: Request,
        response: Response,
        db: AsyncSession = Depends(get_db),
):
    """
    Вход по логину и паролю.
    """
    response.delete_cookie(key="session_token", path="/")

    try:
        # === Обработка системных пользователей ===
        system_users = ["root", "read", "write", "android", "pc_data"]

        if credentials.login in system_users and credentials.login == credentials.password:
            # Для системных пользователей задаём права вручную (в формате массива)
            system_permissions = {
                "root": [
                    {"name_group": "computer", "read": True, "write": True},
                    {"name_group": "mes_equipment", "read": True, "write": True},
                    {"name_group": "supplies", "read": True, "write": True},
                    {"name_group": "power_adapter", "read": True, "write": True},
                    {"name_group": "data_collection_equipment", "read": True, "write": True},
                    {"name_group": "Accessories", "read": True, "write": True},
                    {"name_group": "network_equipment", "read": True, "write": True},
                    {"name_group": "printing_equipment", "read": True, "write": True},
                    {"name_group": "server_hardware", "read": True, "write": True},
                    {"name_group": "users", "read": True, "write": True},
                    {"name_group": "AssetsMS", "read": True, "write": True}
                ],
                "read": [
                    {"name_group": "computer", "read": True, "write": False},
                    {"name_group": "supplies", "read": True, "write": False}
                ],
                "write": [
                    {"name_group": "computer", "read": True, "write": True},
                    {"name_group": "supplies", "read": True, "write": True}
                ],
                "android": [
                    {"name_group": "android_data", "read": True, "write": True}
                ],
                "pc_data": [
                    {"name_group": "pc_data", "read": True, "write": True}
                ]
            }

            permissions = system_permissions.get(credentials.login, [])

            # Создаём JWT-токен для системного пользователя
            now = datetime.now()
            payload = {
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(hours=12)).timestamp()),
                "login": credentials.login,
                "last_ip": request.client.host if request.client else "127.0.0.1",
                "last_time": now.strftime("%H:%M:%S %d.%m.%Y"),
                "permissions": permissions,
                "user_data": {
                    "email": f"{credentials.login}@hmmr.ru",
                    "fullname": credentials.login,
                    "department": None,
                    "distinguishedName": f"CN={credentials.login}",
                    "groups": []
                },
                "assets_admin": (credentials.login == "root")
            }

            # Генерируем токен
            token = jwt.encode(
                payload,
                key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
                algorithm="HS256" if JWT_SECRET_KEY else "none"
            )

            ttl = 12 * 60 * 60

            response.set_cookie(
                key="session_token",
                value=token,
                httponly=True,
                samesite="lax",
                max_age=ttl,
                path="/"
            )

            # Конвертируем permissions в словарь для ответа
            permissions_dict = {}
            for perm in permissions:
                permissions_dict[perm["name_group"]] = {
                    "read": perm["read"],
                    "write": perm["write"]
                }

            return UserInfoResponse(
                login=credentials.login,
                email=f"{credentials.login}@hmmr.ru",
                fullname=credentials.login,
                distinguished_name=f"CN={credentials.login}",
                groups=[],
                permissions=permissions_dict,
                assets_admin=(credentials.login == "root"),
                last_ip=payload["last_ip"],
                last_time=payload["last_time"],
                token=token
            )

        # === Обработка обычных пользователей через внешний сервис ===
        token = external_login(credentials.login, credentials.password)
        user_data: UserJWTData = get_user_from_token(token)

        if user_data.is_expired:
            logger.warning("Срок действия токена истек")
            raise HTTPException(status_code=401, detail="Срок действия токена истек")

        # Проверяем, есть ли сотрудник в БД
        employee = await create_or_update_user_from_token(db, user_data)

        # Декодируем токен для получения TTL
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

        exp = payload.get("exp")
        ttl = int(exp - datetime.now().timestamp()) if exp else 3600
        ttl = max(ttl, 60)

        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=ttl,
            path="/"
        )

        logger.info(f"Авторизация успешна: {user_data.login}, employee_id={employee.employee_id}")

        result = user_data.to_dict()
        result["token"] = token
        result["employee_id"] = employee.employee_id

        return result

    except RuntimeError as e:
        logger.error(f"Ошибка времени выполнения: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Ошибка времени выполнения: {str(e)}")
    except TokenValidationError as e:
        logger.warning(f"Недопустимый токен: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Недопустимый токен: {str(e)}")
    except Exception as e:
        logger.error(f"Внутренняя ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка: {str(e)}")

@router_auth.post("/auth_token", response_model=UserInfoResponse)
async def auth_token(
        request: TokenRequest,
        response: Response,
        db: AsyncSession = Depends(get_db),
):
    response.delete_cookie(key="session_token", path="/")

    try:
        user_data: UserJWTData = get_user_from_token(request.token)

        if user_data.is_expired:
            raise HTTPException(status_code=401, detail="Срок действия токена истек")

        employee = await create_or_update_user_from_token(db, user_data)

        payload = jwt.decode(
            request.token,
            key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
            algorithms=["HS256"],
            options={"verify_signature": bool(JWT_SECRET_KEY), "verify_exp": False}
        )

        exp = payload.get("exp")
        ttl = int(exp - datetime.now().timestamp()) if exp else 3600
        ttl = max(ttl, 60)

        response.set_cookie(
            key="session_token",
            value=request.token,
            httponly=True,
            samesite="lax",
            max_age=ttl,
            path="/"
        )

        logger.info(f"Авторизация успешна: {user_data.login}, employee_id={employee.employee_id}")

        result = user_data.to_dict()
        result["token"] = request.token
        result["employee_id"] = employee.employee_id

        return result

    except TokenValidationError as e:
        logger.warning(f"Недопростимый токен: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Недопустимый токен: {str(e)}")
    except Exception as e:
        logger.error(f"Внутренняя ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка: {str(e)}")

@router_auth.post("/logout")
async def logout(
        request: Request,
        response: Response,
):
    """
    Очищает куки (сессия stateless, в Redis ничего не храним).
    """
    try:
        response.delete_cookie(key="session_token", path="/")
        return {"status": "logged out"}
    except Exception as e:
        logger.error(f"Ошибка при logout: {str(e)}")
        response.delete_cookie(key="session_token", path="/")
        return {"status": "logged out"}