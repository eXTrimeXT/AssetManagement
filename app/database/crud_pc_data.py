from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.PCData import PCData
from app.schemas.pc_data.PcDataSchemas import PCDataCreate


async def create_or_update_pc_data(db: AsyncSession, pc_data: PCDataCreate):
    result = await db.execute(select(PCData).where(PCData.username == pc_data.user.username))
    db_pc = result.scalars().first()

    payload = {
        "user": pc_data.user.model_dump(),
        "network": pc_data.network.model_dump(),
        "os": pc_data.os.model_dump(),
        "components": pc_data.components.model_dump(),
        "office_package": pc_data.office_package,
        "programs": pc_data.programs
    }

    if db_pc:
        for k, v in payload.items():
            setattr(db_pc, k, v)
        db_pc.updated_at = datetime.now()
    else:
        db_pc = PCData(
            username=pc_data.user.username,
            **payload
        )
        db.add(db_pc)

    await db.commit()
    await db.refresh(db_pc)
    return db_pc

async def get_all_pc_data(db: AsyncSession, username: str = None, skip: int = 0, limit: int = 100):
    if username:
        result = await db.execute(select(PCData).offset(skip).limit(limit).where(PCData.username.ilike(f"%{username}%")))
    else:
        result = await db.execute(select(PCData).offset(skip).limit(limit))
    return result.scalars().all()

async def update_pc_data(db: AsyncSession, username: str, pc_data: PCDataCreate):
    result = await db.execute(select(PCData).where(PCData.username == username))
    db_pc = result.scalars().first()

    if db_pc:
        db_pc.user = pc_data.user.model_dump()
        db_pc.network = pc_data.network.model_dump()
        db_pc.os = pc_data.os.model_dump()
        db_pc.components = pc_data.components.model_dump()
        db_pc.office_package = pc_data.office_package
        db_pc.programs = pc_data.programs
        await db.commit()
        await db.refresh(db_pc)
    return db_pc

async def delete_pc_data(db: AsyncSession, username: str):
    result = await db.execute(select(PCData).where(PCData.username == username))
    db_pc = result.scalars().first()
    if db_pc:
        await db.delete(db_pc)
        await db.commit()
    return db_pc