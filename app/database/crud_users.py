from datetime import datetime
from typing import List, Optional, Any, Sequence, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.User import User
from app.schemas.users.UserCreate import UserCreate
from app.schemas.users.UserUpdate import UserUpdate


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ПРОВЕРКИ
async def check_email_exists(db: AsyncSession, email: str, exclude_id: Optional[int] = None) -> bool:
    """
    Проверяет, существует ли пользователь с таким email.
    Возвращает True, если найден.
    """
    query = select(User).where(User.email == email)
    if exclude_id:
        query = query.where(User.user_id != exclude_id)

    result = await db.execute(query)
    return result.scalar_one_or_none() is not None

async def check_tab_id_exists(db: AsyncSession, tab_id: str, exclude_id: Optional[int] = None) -> bool:
    """
    Проверяет, существует ли пользователь с таким табельным номером.
    Возвращает True, если найден.
    """
    if not tab_id:
        return False

    query = select(User).where(User.user_tab_id == tab_id)
    if exclude_id:
        query = query.where(User.user_id != exclude_id)

    result = await db.execute(query)
    return result.scalar_one_or_none() is not None

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """ Получает пользователя по ID """
    result = await db.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()

async def get_user_by_tab_id(db: AsyncSession, user_tab_id: str) -> Optional[User]:
    """ Получает пользователя по TAB_ID """
    result = await db.execute(select(User).where(User.user_tab_id == user_tab_id))
    return result.scalar_one_or_none()

# CRUD ОПЕРАЦИИ
async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """ Создает нового пользователя """
    db_user = User(**user_in.model_dump())
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_users_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        department_id: Optional[int] = None,
        is_active: bool = True,
) -> Sequence[Any]:
    """
    Получает список пользователей с фильтрацией и пагинацией.
    Добавлен фильтр по роли.
    """
    query = select(User).where(User.is_active == is_active)

    if department_id:
        query = query.where(User.department_id == department_id)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

async def update_user(db: AsyncSession, user_id: int, user_data: UserUpdate) -> Optional[User]:
    """ Обновляет данные пользователя """
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    update_data = user_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return user

# В конец файла, после других CRUD-функций

async def update_user_permissions(
        db: AsyncSession,
        user_id: int,
        new_permissions: Dict[str, Dict[str, bool]]
) -> Optional[User]:
    """
    Обновляет права пользователя (merge).
    Ожидает dict: {"computer": {"read": true, "write": false}, ...}
    """
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    current_perms = user.permissions if user.permissions else {}
    # Сливаем новые права со старыми (создаём новый dict для SQLAlchemy)
    user.permissions = {**current_perms, **new_permissions}
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)
    return user

async def deactivate_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """ Деактивирует пользователя (is_active = False) """
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    if not user.is_active:
        # Можно вернуть пользователя как есть или raise exception,
        # но логика проверки дубликата статуса обычно в роутере.
        # Здесь просто обновляем, если нужно.
        pass

    user.is_active = False
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)
    return user

async def activate_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """ Активирует пользователя (is_active = True) """
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    if user.is_active:
        pass

    user.is_active = True
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)
    return user

async def hard_delete_user(db: AsyncSession, user_id: int) -> bool:
    """ Жестко удаляет пользователя из БД. Возвращает True при успехе """
    user = await get_user_by_id(db, user_id)
    if not user:
        return False

    await db.delete(user)
    await db.commit()
    return True