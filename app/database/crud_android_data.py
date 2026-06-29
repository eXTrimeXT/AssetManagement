from unittest import result

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.AndroidData import AndroidData
from app.schemas.android_data.android_data_schemas import AndroidDataCreate

async def create_or_update_android_data(db: AsyncSession, data: AndroidDataCreate):
    result = await db.execute(select(AndroidData).where(AndroidData.serial_number == data.serial_number))
    db_record = result.scalars().first()

    payload = {
        "device": data.device.model_dump(),
        "system": data.system.model_dump(),
        "hardware": data.hardware.model_dump(),
        "network": data.network.model_dump(),
        "battery": data.battery.model_dump()
    }

    if db_record:
        db_record.request_time = data.request_time
        for k, v in payload.items():
            setattr(db_record, k, v)
    else:
        db_record = AndroidData(
            serial_number=data.serial_number,
            request_time=data.request_time,
            **payload
        )
        db.add(db_record)

    await db.commit()
    await db.refresh(db_record)
    return db_record

async def get_all_android_data(db: AsyncSession, serial_number: str = None, skip: int = 0, limit: int = 100):
    if serial_number:
        result = await db.execute(select(AndroidData).offset(skip).limit(limit).where(AndroidData.serial_number == serial_number))
    else:
        result = await db.execute(select(AndroidData).offset(skip).limit(limit))
    return result.scalars().all()

async def update_android_data(db: AsyncSession, serial_number: str, data: AndroidDataCreate):
    result = await db.execute(select(AndroidData).where(AndroidData.serial_number == serial_number))
    db_record = result.scalars().first()

    if db_record:
        db_record.request_time = data.request_time
        db_record.device = data.device.model_dump()
        db_record.system = data.system.model_dump()
        db_record.hardware = data.hardware.model_dump()
        db_record.network = data.network.model_dump()
        db_record.battery = data.battery.model_dump()
        await db.commit()
        await db.refresh(db_record)
    return db_record

async def delete_android_data(db: AsyncSession, serial_number: str):
    result = await db.execute(select(AndroidData).where(AndroidData.serial_number == serial_number))
    db_record = result.scalars().first()

    if db_record:
        await db.delete(db_record)
        await db.commit()
    return db_record