from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.User import User
from app.models.Asset import Asset
from app.models.UserAsset import UserAsset


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ПРОВЕРКИ
async def get_user_by_id(db: AsyncSession, user_id: int) -> type[User] | None:
    """
    Получает пользователя по ID.
    """
    return await db.get(User, user_id)

async def get_asset_by_id(db: AsyncSession, asset_id: int) -> type[Asset] | None:
    """
    Получает актив по ID.
    """
    return await db.get(Asset, asset_id)

async def check_active_assignment_exists(
        db: AsyncSession,
        user_id: int,
        asset_id: int
) -> bool:
    """
    Проверяет, существует ли уже активная (не возвращенная) связь между пользователем и активом.
    Возвращает True, если связь есть.
    """
    result = await db.execute(
        select(UserAsset).where(
            UserAsset.user_id == user_id,
            UserAsset.asset_id == asset_id,
            UserAsset.returned_at.is_(None)
        )
    )
    return result.scalar_one_or_none() is not None


async def get_active_assignment_link(
        db: AsyncSession,
        user_id: int,
        asset_id: int
) -> Optional[UserAsset]:
    """
    Получает объект связи UserAsset, если он активен (не возвращен).
    """
    result = await db.execute(
        select(UserAsset).where(
            UserAsset.user_id == user_id,
            UserAsset.asset_id == asset_id,
            UserAsset.returned_at.is_(None)
        )
    )
    return result.scalar_one_or_none()


# CRUD ОПЕРАЦИИ
async def create_assignment(db: AsyncSession, user_id: int, asset_id: int) -> UserAsset:
    """
    Создает новую связь между пользователем и активом.
    """
    link = UserAsset(user_id=user_id, asset_id=asset_id)
    db.add(link)
    await db.commit()
    await db.refresh(link)

    # Подгружаем связанный актив для ответа (если нужно сразу вернуть с данными актива)
    # В роутере это делается через refresh attribute_names, но можно и здесь через selectinload при получении
    # Однако, так как мы только что сделали commit, проще сделать отдельный запрос или refresh
    await db.refresh(link, attribute_names=["asset"])

    return link

async def unassign_asset(db: AsyncSession, user_id: int, asset_id: int) -> Optional[UserAsset]:
    """
    Отвязывает пользователя от актива (устанавливает returned_at).
    Возвращает обновленный объект связи или None, если связь не найдена.
    """
    link = await get_active_assignment_link(db, user_id, asset_id)
    if not link:
        return None

    link.returned_at = datetime.utcnow()
    await db.commit()
    await db.refresh(link, attribute_names=["asset"])

    return link

async def get_user_full_info(db: AsyncSession, user_id: int) -> Optional[User]:
    """
    Получает полную информацию о пользователе со всеми вложенными данными:
    - Назначения (assignments)
    - Активы (asset)
    - Дочерние элементы активов (children)
    - Типы активов (asset_type)
    - ПО (software)

    Использует эффективную загрузку связей (selectinload/joinedload).
    """
    query = (
        select(User)
        .where(User.user_id == user_id)
        .options(
            selectinload(User.assignments)
            .selectinload(UserAsset.asset)
            .options(
                selectinload(Asset.children),
                joinedload(Asset.asset_type),
                selectinload(Asset.software)
            )
        )
    )

    result = await db.execute(query)
    return result.scalar_one_or_none()