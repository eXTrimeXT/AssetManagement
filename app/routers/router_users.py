from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.responses import Response

from app.database.connection import get_db
from app.models.User import User
from app.schemas.users.UserCreate import UserCreate
from app.schemas.users.UserUpdate import UserUpdate
from app.schemas.users.UserResponse import UserResponse, UserShortResponse

router_users = APIRouter(prefix="/users", tags=["Users"])

@router_users.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Создать нового пользователя"""
    # Проверка на дубликат email
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    # Проверка на дубликат табельного номера
    if user_in.user_tab_id:
        result = await db.execute(select(User).where(User.user_tab_id == user_in.user_tab_id))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Табельный номер уже существует")

    db_user = User(**user_in.model_dump())
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router_users.get("/", response_model=list[UserShortResponse])
async def get_users(
        skip: int = 0,
        limit: int = 50,
        department: Optional[str] = None,
        is_active: bool = True,
        db: AsyncSession = Depends(get_db)
):
    """Получить список пользователей с фильтрацией"""
    query = select(User).where(User.is_active == is_active)

    if department:
        query = query.where(User.department == department)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

@router_users.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Получить пользователя по ID с назначениями"""
    result = await db.execute(
        select(User)
        .where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user

@router_users.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_data: UserUpdate, db: AsyncSession = Depends(get_db)):
    """Обновить данные пользователя"""
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Проверка на дубликат email при обновлении
    if user_data.email and user_data.email != user.email:
        existing = await db.execute(select(User).where(User.email == user_data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    # Проверка на дубликат табельного номера
    if user_data.user_tab_id and user_data.user_tab_id != user.user_tab_id:
        existing = await db.execute(select(User).where(User.user_tab_id == user_data.user_tab_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Табельный номер уже существует")

    update_data = user_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return user

# @router_users.patch("/deactivate/{user_id}", status_code=status.HTTP_200_OK)
# async def deactivate_user(user_id: int, db: AsyncSession = Depends(get_db)):
#     """Деактивация пользователя"""
#     result = await db.execute(select(User).where(User.id == user_id))
#     user = result.scalar_one_or_none()
#     if not user:
#         raise HTTPException(status_code=404, detail="Пользователь не найден")
#
#     user.is_active = False
#     await db.commit()
#     return {"user_id": user.id, "is_active": user.is_active}
#
# @router_users.patch("/activate/{user_id}", status_code=status.HTTP_200_OK)
# async def activate_user(user_id: int, db: AsyncSession = Depends(get_db)):
#     """Активация пользователя"""
#     result = await db.execute(select(User).where(User.id == user_id))
#     user = result.scalar_one_or_none()
#     if not user:
#         raise HTTPException(status_code=404, detail="Пользователь не найден")
#
#     user.is_active = True
#     await db.commit()
#     return {"user_id": user.id, "is_active": user.is_active}

@router_users.post("/{user_id}/activate", response_model=UserResponse)
async def activate_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Активация пользователя.
    Восстанавливает доступ пользователя к системе.
    """
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.is_active:
        raise HTTPException(status_code=400, detail="Пользователь уже активен")

    user.is_active = True
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)

    return user

@router_users.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Деактивация пользователя.
    Блокирует доступ пользователя к системе без удаления данных.
    """
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Пользователь уже деактивирован")

    user.is_active = False
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)

    return user

@router_users.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def hard_delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Жесткое удаление пользователя.
    Полностью удаляет запись из БД (безвозвратно).

    Требования:
    - Пользователь должен быть деактивирован (is_active = False)
    """
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Проверка 1: пользователь должен быть деактивирован
    if user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить активного пользователя. Сначала деактивируйте его."
        )

    # Удаляем пользователя
    await db.delete(user)
    await db.commit()

    # 204 No Content — стандартный ответ для успешного удаления
    return Response(status_code=status.HTTP_204_NO_CONTENT)