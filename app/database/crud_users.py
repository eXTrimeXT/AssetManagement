from collections import defaultdict
from datetime import datetime
from typing import List, Optional, Any, Sequence, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.User import User
from app.schemas.users.UserCreate import UserCreate
from app.schemas.users.UserUpdate import UserUpdate
from app.schemas.assets.AssetResponse import AssetShortResponse
from app.database.crud_catalog import get_catalog_entries_by_user_ids


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ПРОВЕРКИ
async def check_email_exists(db: AsyncSession, email: str, exclude_tab_id: Optional[str] = None) -> bool:
    """
    Проверяет, существует ли пользователь с таким email.
    Возвращает True, если найден.
    """
    query = select(User).where(User.email == email)
    if exclude_tab_id:
        # query = query.where(User.user_id != exclude_id)
        query = query.where(User.user_tab_id != exclude_tab_id)

    result = await db.execute(query)
    return result.scalar_one_or_none() is not None

async def check_tab_id_exists(db: AsyncSession, tab_id: str, exclude_tab_id: Optional[str] = None) -> bool:
    """
    Проверяет, существует ли пользователь с таким табельным номером.
    Возвращает True, если найден.
    """
    if not tab_id:
        return False

    query = select(User).where(User.user_tab_id == tab_id)
    if exclude_tab_id:
        # query = query.where(User.user_id != exclude_id)
        query = query.where(User.user_tab_id != exclude_tab_id)

    result = await db.execute(query)
    return result.scalar_one_or_none() is not None

# async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
#     """ Получает пользователя по ID """
#     result = await db.execute(
#         select(User).options(
#             selectinload(User.department),
#             selectinload(User.division),
#             selectinload(User.group)
#         ).where(User.user_id == user_id)
#     )
#     return result.scalar_one_or_none()

async def get_user_by_tab_id(db: AsyncSession, user_tab_id: str) -> Optional[User]:
    """ Получает пользователя по TAB_ID """
    result = await db.execute(
        select(User).options(
            selectinload(User.department),
            selectinload(User.division),
            selectinload(User.group)
        ).where(User.user_tab_id == user_tab_id)
    )
    return result.scalar_one_or_none()

# CRUD ОПЕРАЦИИ
async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """ Создает нового пользователя """
    db_user = User(**user_in.model_dump())
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


# async def get_users_list(
#         db: AsyncSession,
#         skip: int = 0,
#         limit: int = 50,
#         department_id: Optional[int] = None,
#         is_active: bool = True,
#         user_id: Optional[int] = None,
#         user_tab_id: Optional[str] = None,
# ) -> Sequence[Any]:
#     """Получает список пользователей с фильтрацией и пагинацией."""
#     query = select(User).where(User.is_active == is_active)
#
#     if department_id:
#         query = query.where(User.department_id == department_id)
#     if user_id:
#         query = query.where(User.user_id == user_id)
#     if user_tab_id:
#         query = query.where(User.user_tab_id == user_tab_id)
#
#     query = query.offset(skip).limit(limit)
#
#     result = await db.execute(query)
#     return result.scalars().all()

async def get_users_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        department_id: Optional[int] = None,
        is_active: bool = True,
        # user_id: Optional[int] = None,
        user_tab_id: Optional[str] = None,
) -> List[dict]:
    """
    Получает список пользователей с фильтрацией и пагинацией.
    Для каждого пользователя подтягивает список его активов из asset_catalog.
    Возвращает список словарей с полем 'assets'.
    """
    query = select(User).where(User.is_active == is_active)
    if department_id:
        query = query.where(User.department_id == department_id)
    # if user_id:
    #     query = query.where(User.user_id == user_id)
    if user_tab_id:
        query = query.where(User.user_tab_id == user_tab_id)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    users = result.scalars().all()

    if not users:
        return []

    # === Получаем активы пользователей из каталога одним запросом ===
    user_tab_ids = [u.user_tab_id for u in users]
    catalog_entries = await get_catalog_entries_by_user_ids(db, user_tab_ids)

    # Группируем записи каталога по owner_id
    assets_by_user = defaultdict(list)
    for entry in catalog_entries:
        if entry.asset:
            assets_by_user[entry.owner_id].append(entry.asset)

    # === Формируем ответ с активами ===
    response_users = []
    for user in users:
        user_dict = {
            # "user_id": user.user_id,
            "user_tab_id": user.user_tab_id,
            "owner": user.owner,
            "user_position": user.user_position,
            "comment": getattr(user, 'comment', None),
            "department_id": user.department_id,
            "division_id": user.division_id,
            "group_id": user.group_id,
            "email": user.email,
            "permissions": user.permissions,
            "assets": [
                AssetShortResponse.model_validate(asset).model_dump()
                for asset in assets_by_user.get(user.user_tab_id, [])
            ]
        }
        response_users.append(user_dict)

    return response_users

async def update_user(db: AsyncSession, user_tab_id: str, user_data: UserUpdate) -> Optional[User]:
    """ Обновляет данные пользователя """
    user = await get_user_by_tab_id(db, user_data.user_tab_id)
    if not user:
        return None

    update_data = user_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return user

def _deep_merge(base: dict, override: dict) -> dict:
    """Рекурсивно объединяет словари, не перезаписывая соседние вложенные ключи."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result

async def update_user_permissions(
        db: AsyncSession,
        user_tab_id: str,
        new_permissions: Dict[str, Dict[str, bool]]
) -> Optional[User]:
    """
    Обновляет права пользователя (глубокое слияние).
    Обновляет только переданные вложенные ключи, сохраняя остальные.
    """
    user = await get_user_by_tab_id(db, user_tab_id)
    if not user:
        return None

    current_perms = user.permissions or {}
    # Глубокое слияние вместо поверхностного обновления
    user.permissions = _deep_merge(current_perms, new_permissions)
    user.updated_at = datetime.now()

    await db.commit()
    await db.refresh(user)
    return user

async def deactivate_user(db: AsyncSession, user_tab_id: str) -> Optional[User]:
    """ Деактивирует пользователя (is_active = False) """
    user = await get_user_by_tab_id(db, user_tab_id)
    if not user:
        return None

    if not user.is_active:
        # Можно вернуть пользователя как есть или raise exception,
        # но логика проверки дубликата статуса обычно в роутере.
        # Здесь просто обновляем, если нужно.
        pass

    user.is_active = False
    user.updated_at = datetime.now()

    await db.commit()
    await db.refresh(user)
    return user

async def activate_user(db: AsyncSession, user_tab_id: str) -> Optional[User]:
    """ Активирует пользователя (is_active = True) """
    user = await get_user_by_tab_id(db, user_tab_id)
    if not user:
        return None

    if user.is_active:
        pass

    user.is_active = True
    user.updated_at = datetime.now()

    await db.commit()
    await db.refresh(user)
    return user

async def hard_delete_user(db: AsyncSession, user_tab_id: str) -> bool:
    """ Жестко удаляет пользователя из БД. Возвращает True при успехе """
    user = await get_user_by_tab_id(db, user_tab_id)
    if not user:
        return False

    await db.delete(user)
    await db.commit()
    return True