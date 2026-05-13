from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.database.connection import get_db
from app.schemas.users.UserCreate import UserCreate
from app.schemas.users.UserUpdate import UserUpdate
from app.schemas.users.UserResponse import UserResponse, UserShortResponse
from app.service.auth.auth_service import get_user_from_token, TokenValidationError

from app.models.User import User

# Импорт CRUD функций
from app.database.crud_users import (
    create_user,
    get_users_list,
    get_user_by_id,
    get_user_by_tab_id,
    update_user,
    deactivate_user,
    activate_user,
    hard_delete_user,
    check_email_exists,
    check_tab_id_exists
)


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


router_users = APIRouter(
    prefix="/users",
    tags=["Users"],
    # dependencies=[Depends(require_authorized_user)]  # <-- Глобальная защита
)


@router_users.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Создать нового пользователя"""
    # Проверка на дубликат email
    if await check_email_exists(db, user_in.email):
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    # Проверка на дубликат табельного номера
    if user_in.user_tab_id:
        if await check_tab_id_exists(db, user_in.user_tab_id):
            raise HTTPException(status_code=400, detail="Табельный номер уже существует")

    return await create_user(db, user_in)

@router_users.get("/", response_model=list[UserShortResponse])
async def get_users_endpoint(
        skip: int = 0,
        limit: int = 50,
        department: Optional[str] = None,
        is_active: bool = True,
        db: AsyncSession = Depends(get_db)
):
    """Получить список пользователей с фильтрацией"""
    return await get_users_list(db, skip, limit, department, is_active)


@router_users.get("/id/{user_id}", response_model=UserResponse)
async def get_user_by_id_endpoint(user_id: int, db: AsyncSession = Depends(get_db)):
    """Получить пользователя по ID"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user

@router_users.get("/tab_id/{user_tab_id}", response_model=UserResponse)
async def get_user_by_tab_id_endpoint(user_tab_id: str, db: AsyncSession = Depends(get_db)):
    """Получить пользователя по TAB_ID"""
    user = await get_user_by_tab_id(db, user_tab_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user

@router_users.patch("/{user_id}", response_model=UserResponse)
async def update_user_endpoint(user_id: int, user_data: UserUpdate, db: AsyncSession = Depends(get_db)):
    """Обновить данные пользователя"""
    # Предварительные проверки перед обновлением
    current_user = await get_user_by_id(db, user_id)
    if not current_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Проверка Email
    if user_data.email and user_data.email != current_user.email:
        if await check_email_exists(db, user_data.email, exclude_id=user_id):
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    # Проверка Табельного номера
    if user_data.user_tab_id and user_data.user_tab_id != current_user.user_tab_id:
        if await check_tab_id_exists(db, user_data.user_tab_id, exclude_id=user_id):
            raise HTTPException(status_code=400, detail="Табельный номер уже существует")

    updated_user = await update_user(db, user_id, user_data)
    if not updated_user:
        raise HTTPException(status_code=404, detail="Ошибка при обновлении")

    return updated_user

@router_users.post("/{user_id}/activate", response_model=UserResponse)
async def activate_user_endpoint(user_id: int, db: AsyncSession = Depends(get_db)):
    """Активация пользователя"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.is_active:
        raise HTTPException(status_code=400, detail="Пользователь уже активен")

    return await activate_user(db, user_id)

@router_users.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user_endpoint(user_id: int, db: AsyncSession = Depends(get_db)):
    """Деактивация пользователя"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Пользователь уже деактивирован")

    return await deactivate_user(db, user_id)

@router_users.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def hard_delete_user_endpoint(user_id: int, db: AsyncSession = Depends(get_db)):
    """Жесткое удаление пользователя (только если деактивирован)"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить активного пользователя. Сначала деактивируйте его."
        )

    success = await hard_delete_user(db, user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Ошибка при удалении")

    return Response(status_code=status.HTTP_204_NO_CONTENT)

# === Новый эндпоинт /me ===
@router_users.get("/me", response_model=UserResponse)
async def get_current_user(
        current_user: User = Depends(require_authorized_user)  # <-- Проверка авторизации
):
    """
    Возвращает информацию о текущем авторизованном пользователе.
    Доступен только если пользователь есть в таблице Users.
    """
    return current_user