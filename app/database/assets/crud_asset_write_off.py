from typing import List, Optional
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assets.AssetWriteOff import AssetWriteOff
from app.models.assets.Asset import Asset
from app.models.assets.AssetStatus import AssetStatus
from app.models.assets.AssetAssignment import AssetAssignment
from app.database.assets.crud_asset_history import create_history_record
from app.schemas.assets.AssetWriteOffSchemas import AssetWriteOffCreate


async def create_write_off(
        db: AsyncSession,
        data: AssetWriteOffCreate,
        employee_id: str
) -> Optional[AssetWriteOff]:
    """
    Создать акт списания:
    1. Создать запись в asset_write_offs
    2. Поменять статус актива на "Списан"
    3. Закрыть все активные привязки пользователей
    4. Записать в историю изменений
    """
    # 1. Проверяем существование актива
    asset = await db.get(Asset, data.asset_id)
    if not asset:
        return None

    # 2. Создаём запись списания
    write_off = AssetWriteOff(
        asset_id=data.asset_id,
        reason=data.reason,
        reason_description=data.reason_description,
        act_number=data.act_number,
        act_date=data.act_date,
        disposal_method=data.disposal_method,
        initiated_by=employee_id,
        notes=data.notes
    )
    db.add(write_off)

    # 3. Находим статус "Списан" и меняем у актива
    result = await db.execute(
        select(AssetStatus).where(AssetStatus.status == "Списан")
    )
    written_off_status = result.scalars().first()

    old_status_id = asset.asset_status_id
    if written_off_status:
        asset.asset_status_id = written_off_status.id
        asset.updated_by = employee_id

        # 4. Записываем изменение статуса в историю
        await create_history_record(
            db=db,
            asset_id=asset.asset_id,
            field_name="asset_status_id",
            old_value=str(old_status_id) if old_status_id else None,
            new_value=str(written_off_status.id),
            changed_by=employee_id
        )

    # 5. Закрываем все активные привязки пользователей
    result_assignments = await db.execute(
        select(AssetAssignment).where(
            AssetAssignment.asset_id == asset.asset_id,
            AssetAssignment.end_date.is_(None)
        )
    )
    active_assignments = result_assignments.scalars().all()
    for assignment in active_assignments:
        assignment.end_date = date.today()

    await db.commit()
    await db.refresh(write_off)
    return write_off


async def get_write_offs_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        asset_id: Optional[int] = None
) -> List[AssetWriteOff]:
    """Получить список актов списания"""
    query = select(AssetWriteOff).order_by(AssetWriteOff.created_at.desc())

    if asset_id is not None:
        query = query.where(AssetWriteOff.asset_id == asset_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_write_off_by_id(db: AsyncSession, write_off_id: int) -> Optional[AssetWriteOff]:
    """Получить акт списания по ID"""
    return await db.get(AssetWriteOff, write_off_id)


async def delete_write_off(db: AsyncSession, write_off_id: int) -> bool:
    """Удалить акт списания (только если он был создан по ошибке)"""
    write_off = await db.get(AssetWriteOff, write_off_id)
    if not write_off:
        return False
    await db.delete(write_off)
    await db.commit()
    return True