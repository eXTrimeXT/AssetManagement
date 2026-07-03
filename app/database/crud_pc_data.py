from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.PCData import PCData
# from app.models.User import User
from app.schemas.pc_data.pc_data_schemas import PCDataCreate
from app.middleware.LoggingMiddleware import logger


async def create_or_update_pc_data(db: AsyncSession, pc_data: PCDataCreate):
    # Пытаемся найти пользователя по user_tab_id == username
    # user_result = await db.execute(select(User).where(User.user_tab_id == pc_data.user.username))
    # db_user = user_result.scalars().first()

    # Если не найден — ставим None, ошибки не поднимаем
    # user_id = db_user.user_id if db_user else None
    # user_tab_id = db_user.user_tab_id if db_user else None
    user_tab_id = "LOGIN"

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
        # db_pc.user_id = user_id  # Обновляем связь (может быть None)
        # db_pc.user_tab_id = user_tab_id  # Обновляем связь (может быть None)
    else:
        db_pc = PCData(
            username=pc_data.user.username,
            # user_id=user_id,      # Ставим связь (может быть None)
            # user_id=user_tab_id,      # Ставим связь (может быть None)
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
    # user_result = await db.execute(select(User).where(User.user_tab_id == pc_data.user.username))
    # db_user = user_result.scalars().first()
    # user_id = db_user.user_id if db_user else None  # None если пользователь не найден
    # user_tab_id = db_user.user_tab_id if db_user else None  # None если пользователь не найден

    user_tab_id = "LOGIN"
    result = await db.execute(select(PCData).where(PCData.username == username))
    db_pc = result.scalars().first()

    if db_pc:
        db_pc.user = pc_data.user.model_dump()
        db_pc.network = pc_data.network.model_dump()
        db_pc.os = pc_data.os.model_dump()
        db_pc.components = pc_data.components.model_dump()
        db_pc.office_package = pc_data.office_package
        db_pc.programs = pc_data.programs
        # db_pc.user_id = user_id  # Обновляем связь
        # db_pc.user_tab_id = user_tab_id  # Обновляем связь
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