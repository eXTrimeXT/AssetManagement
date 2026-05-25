from typing import Optional, Sequence, Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.Group import Group
from app.schemas.groups.GroupCreate import GroupCreate
from app.schemas.groups.GroupUpdate import GroupUpdate


async def get_group_by_id(db: AsyncSession, group_id: int) -> Optional[Group]:
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    return result.scalar_one_or_none()


async def create_group(db: AsyncSession, group_in: GroupCreate) -> Group:
    db_group = Group(**group_in.model_dump())
    db.add(db_group)
    try:
        await db.commit()
        await db.refresh(db_group)
        return db_group
    except IntegrityError:
        await db.rollback()
        raise


async def get_groups_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        name: Optional[str] = None,
        abbreviation: Optional[str] = None,
        division_id: Optional[int] = None
) -> Sequence[Any]:
    query = select(Group)

    if name:
        query = query.where(Group.name.ilike(f"%{name}%"))
    if abbreviation:
        query = query.where(Group.abbreviation.ilike(f"%{abbreviation}%"))
    if division_id:
        query = query.where(Group.division_id == division_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_group(
        db: AsyncSession,
        group_id: int,
        group_data: GroupUpdate
) -> Optional[Group]:
    group = await get_group_by_id(db, group_id)
    if not group:
        return None

    update_data = group_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)

    try:
        await db.commit()
        await db.refresh(group)
        return group
    except IntegrityError:
        await db.rollback()
        raise


async def delete_group(db: AsyncSession, group_id: int) -> bool:
    group = await get_group_by_id(db, group_id)
    if not group:
        return False

    await db.delete(group)
    await db.commit()
    return True