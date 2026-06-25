from typing import Optional, Sequence, Any
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.Department import Department
from app.models.Division import Division
from app.models.Group import Group
from app.schemas.groups.GroupCreate import GroupCreate
from app.schemas.groups.GroupUpdate import GroupUpdate


def _group_to_hierarchy_dict(group: Group) -> dict:
    """
    Преобразует объект Group в словарь формата GroupDivisionDepartmentIdsResponse.
    """
    return {
        "group_id": group.id,
        "group_name": group.name,
        "group_abbreviation": group.abbreviation,
        "division_id": group.division_id,
        "division_name": group.division.name if group.division else None,
        "division_abbreviation": group.division.abbreviation if group.division else None,
        "department_id": group.division.department_id if group.division else None,
        "department_name": group.division.department.name if group.division and group.division.department else None,
        "department_abbreviation": group.division.department.abbreviation if group.division and group.division.department else None,
    }


async def get_group_by_id(db: AsyncSession, group_id: int) -> Optional[Group]:
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    return result.scalar_one_or_none()


async def create_group(db: AsyncSession, group_in: GroupCreate) -> dict:
    """
    Создает новую группу и возвращает полную информацию в формате GroupDivisionDepartmentIdsResponse.
    """
    db_group = Group(**group_in.model_dump())
    db.add(db_group)
    try:
        await db.commit()
        await db.refresh(db_group)

        # Загружаем связанные division и department
        result = await db.execute(
            select(Group).options(
                selectinload(Group.division).selectinload(Division.department)
            ).where(Group.id == db_group.id)
        )
        group_with_relations = result.scalar_one_or_none()

        return _group_to_hierarchy_dict(group_with_relations)
    except IntegrityError:
        await db.rollback()
        raise


async def get_hierarchy_by_group_params(
        db: AsyncSession,
        group_id: Optional[int] = None,
        abbreviation: Optional[str] = None
) -> Sequence[dict]:
    """
    Поиск групп по group_id (точное совпадение) и/или abbreviation (частичное совпадение).
    Возвращает список словарей с полной информацией о группе, отделе и департаменте.
    """
    query = select(Group).options(
        selectinload(Group.division).selectinload(Division.department)
    )

    if group_id is not None:
        query = query.where(Group.id == group_id)
    if abbreviation:
        query = query.where(Group.abbreviation.ilike(f"%{abbreviation}%"))

    result = await db.execute(query)
    groups = result.scalars().all()

    return [_group_to_hierarchy_dict(g) for g in groups]


async def update_group(
        db: AsyncSession,
        group_id: int,
        group_data: GroupUpdate
) -> Optional[dict]:
    """
    Обновляет группу и возвращает полную информацию в формате GroupDivisionDepartmentIdsResponse.
    """
    group = await get_group_by_id(db, group_id)
    if not group:
        return None

    update_data = group_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)

    try:
        await db.commit()
        await db.refresh(group)

        # Загружаем связанные division и department
        result = await db.execute(
            select(Group).options(
                selectinload(Group.division).selectinload(Division.department)
            ).where(Group.id == group.id)
        )
        group_with_relations = result.scalar_one_or_none()

        return _group_to_hierarchy_dict(group_with_relations)
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