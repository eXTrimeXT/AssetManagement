import logging
import jwt
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
from app.database.zup import get_employee_by_login_or_email
from app.database.zup.crud_zup_employees import update_employee_active_directory_login
from app.services.auth.system_users import SYSTEM_USERS, MockSystemEmployee

logger = logging.getLogger(__name__)
router_auth = APIRouter(tags=["Auth"])

async def get_employee_or_mock(
        db: AsyncSession,
        user_data: UserJWTData
) -> Employee:
    """
    Возвращает сотрудника из БД или мок для системного пользователя.
    """
    # Системные пользователи — призраки, их нет в БД
    if user_data.login in SYSTEM_USERS:
        return MockSystemEmployee(user_data.login)

    # Обычные пользователи
    employee = await get_employee_by_login_or_email(
        db,
        login=user_data.login,
        email=user_data.email
    )

    if not employee:
        logger.warning(f"Сотрудник {user_data.login} не найден в БД")
        raise HTTPException(
            status_code=404,
            detail=f"Сотрудник {user_data.login} не найден. Обратитесь к администратору для синхронизации из 1С."
        )

    if employee.dismissal_date:
        logger.warning(f"Сотрудник {user_data.login} уволен")
        raise HTTPException(status_code=403, detail="Учетная запись сотрудника деактивирована")

    # === Обновляем active_directory_login если он пустой ===
    if not employee.active_directory_login:
        logger.info(f"Обновляем active_directory_login для {user_data.login}")
        await update_employee_active_directory_login(db, employee, user_data.login)

    return employee


@router_auth.post(
    "/auth_token",
    response_model=UserInfoResponse,
    summary="Аутентификация по JWT-токену / JWT Token Authentication",
    description=(
            "RU: Аутентифицирует пользователя по предоставленному JWT-токену. Проверяет валидность и срок действия токена, "
            "ищет сотрудника в базе данных (или использует системного пользователя), проверяет дату увольнения и при необходимости "
            "обновляет поле active_directory_login. Устанавливает HTTP-only cookie 'session_token' и возвращает информацию о пользователе.\n\n"
            "EN: Authenticates the user using the provided JWT token. Validates the token and its expiration, "
            "looks up the employee in the database (or uses a system user), checks the dismissal date, and updates "
            "the active_directory_login field if necessary. Sets an HTTP-only 'session_token' cookie and returns user information."
    )
)
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

        employee = await get_employee_or_mock(db, user_data)

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
        result["permission_departments"] = payload.get("permission_departments")

        return result

    except TokenValidationError as e:
        logger.warning(f"Недопростимый токен: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Недопустимый токен: {str(e)}")
    except Exception as e:
        logger.error(f"Внутренняя ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка: {str(e)}")


@router_auth.post(
    "/logout",
    summary="Завершение сеанса / Logout",
    description=(
            "RU: Завершает сеанс пользователя путем очистки cookie 'session_token'. Сессия является stateless, "
            "данные не хранятся в Redis или других хранилищах на стороне сервера.\n\n"
            "EN: Terminates the user session by clearing the 'session_token' cookie. The session is stateless, "
            "no data is stored in Redis or other server-side storage."
    )
)
async def logout(
        request: Request,
        response: Response,
):
    try:
        response.delete_cookie(key="session_token", path="/")
        return {"status": "logged out"}
    except Exception as e:
        logger.error(f"Ошибка при logout: {str(e)}")
        response.delete_cookie(key="session_token", path="/")
        return {"status": "logged out"}