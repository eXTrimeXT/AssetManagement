from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.PCData import PCData
from app.models.User import User
from app.schemas.pc_data.pc_data_schemas import PCDataCreate

async def create_or_update_pc_data(db: AsyncSession, pc_data: PCDataCreate):
    # Сравнение username клиента с user_tab_id из таблицы users
    user_result = await db.execute(select(User).where(User.user_tab_id == pc_data.user.username))
    db_user = user_result.scalars().first()
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found in users table")

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
        db_pc.user_id = db_user.user_id  # Ставим связь
    else:
        db_pc = PCData(
            username=pc_data.user.username,
            user_id=db_user.user_id,     # Ставим связь
            **payload
        )
        db.add(db_pc)

    await db.commit()
    await db.refresh(db_pc)
    return db_pc

async def get_pc_data(db: AsyncSession, username: str):
    result = await db.execute(select(PCData).where(PCData.username == username))
    return result.scalars().first()

async def get_all_pc_data(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(select(PCData).offset(skip).limit(limit))
    return result.scalars().all()

async def update_pc_data(db: AsyncSession, username: str, pc_data: PCDataCreate):
    user_result = await db.execute(select(User).where(User.user_tab_id == pc_data.user.username))
    db_user = user_result.scalars().first()
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found in users table")

    result = await db.execute(select(PCData).where(PCData.username == username))
    db_pc = result.scalars().first()
    if db_pc:
        db_pc.user = pc_data.user.model_dump()
        db_pc.network = pc_data.network.model_dump()
        db_pc.os = pc_data.os.model_dump()
        db_pc.components = pc_data.components.model_dump()
        db_pc.office_package = pc_data.office_package
        db_pc.programs = pc_data.programs
        db_pc.user_id = db_user.user_id  # Обновляем связь
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