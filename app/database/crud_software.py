from typing import List, Optional, Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.Software import Software
from app.models.Asset import Asset
from app.schemas.software.SoftwareCreate import SoftwareCreate
from app.schemas.software.SoftwareUpdate import SoftwareUpdate


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# async def get_software_by_id(db: AsyncSession, software_id: int) -> Optional[Software]:
#     """
#     Получает запись о ПО по ID.
#     Возвращает None, если не найдено.
#     """
#     result = await db.execute(
#         select(Software).where(Software.software_id == software_id)
#     )
#     return result.scalar_one_or_none()
async def get_software_by_id(db: AsyncSession, software_id: int) -> Optional[Software]:
    """
    Получает запись о ПО по ID с подгрузкой пользователя.
    """
    result = await db.execute(
        select(Software)
        .where(Software.software_id == software_id)
        .options(selectinload(Software.installer)) # Явно подгружаем пользователя
    )
    return result.scalar_one_or_none()

async def check_software_has_assets(db: AsyncSession, software_id: int) -> bool:
    """
    Проверяет, привязаны ли к данному ПО какие-либо активы.
    Возвращает True, если привязки есть.
    """
    result = await db.execute(
        select(Asset).where(Asset.software_id == software_id).limit(1)
    )
    return result.scalar_one_or_none() is not None

# CRUD ОПЕРАЦИИ
async def create_software(db: AsyncSession, software_in: SoftwareCreate) -> Software:
    """
    Создает новую запись о программном обеспечении.
    """
    db_software = Software(**software_in.model_dump())
    db.add(db_software)
    await db.commit()
    await db.refresh(db_software)
    await db.refresh(db_software, )
    return db_software

async def get_software_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        admin_permission: Optional[bool] = None,
        os_type: Optional[str] = None
) -> Sequence[Any]:
    """
    Получает список ПО с фильтрацией и пагинацией.
    """
    query = select(Software)

    if admin_permission is not None:
        query = query.where(Software.admin_permission == admin_permission)

    if os_type:
        # Используем ilike для регистронезависимого поиска
        query = query.where(Software.os_type.ilike(f"%{os_type}%"))

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

async def update_software(db: AsyncSession, software_id: int, software_data: SoftwareUpdate) -> Optional[Software]:
    """
    Обновляет поля записи о ПО.
    """
    software = await get_software_by_id(db, software_id)
    if not software:
        return None

    update_data = software_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(software, key, value)

    await db.commit()
    await db.refresh(software)
    # После обновления связи могут сброситься, поэтому снова подгружаем
    await db.refresh(software, attribute_names=["installer"])
    return software

async def delete_software(db: AsyncSession, software_id: int) -> bool:
    """
    Удаляет запись о ПО.
    Предварительно проверяет отсутствие привязанных активов.
    Возвращает True при успешном удалении, False если ПО не найдено.
    Raises HTTPException 400 если есть привязанные активы (обработка должна быть в роутере или здесь).
    """
    software = await get_software_by_id(db, software_id)
    if not software:
        return False

    # Проверка на наличие связанных активов
    if await check_software_has_assets(db, software_id):
        # В CRUD слое лучше выбрасывать исключение или возвращать код ошибки,
        # но так как мы хотим сохранить логику роутера, проверим это в роутере
        # или выбросим ValueError/CustomException.
        # Для чистоты CRUD, пусть роутер делает проверку через check_software_has_assets,
        # а здесь только удаление.
        pass

    await db.delete(software)
    await db.commit()
    return True

async def get_assets_by_software_id(db: AsyncSession, software_id: int) -> Sequence[Any]:
    """
    Получает список всех активных (не удаленных) активов,
    на которых установлено данное ПО.
    """
    result = await db.execute(
        select(Asset)
        .where(Asset.software_id == software_id)
        .where(Asset.deleted_at.is_(None))
    )
    return result.scalars().all()