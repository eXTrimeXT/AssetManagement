import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.schemas.groups.GroupResponse import GroupDivisionDepartmentIdsResponse
from app.schemas.groups.GroupCreate import GroupCreate
from app.schemas.groups.GroupUpdate import GroupUpdate
from app.database.crud_groups import (
    create_group,
    get_hierarchy_by_group_params,
    update_group,
    delete_group
)
from app.service.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)
router_groups = APIRouter(prefix="/groups", tags=["Groups"], dependencies=[Depends(require_authorized_user)])


@router_groups.post("/", response_model=GroupDivisionDepartmentIdsResponse, status_code=200)
async def create_group_endpoint(
        group_in: GroupCreate,
        db: AsyncSession = Depends(get_db)
):
    return await create_group(db, group_in)


@router_groups.get("/search", response_model=List[GroupDivisionDepartmentIdsResponse])
async def search_groups_hierarchy_endpoint(
        group_id: Optional[int] = Query(None),
        abbreviation_group: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db)
):
    """
    Поиск групп по group_id и/или abbreviation_group.
    Возвращает список с полной информацией о группе, отделе и департаменте.
    """
    return await get_hierarchy_by_group_params(db, group_id, abbreviation_group)


@router_groups.patch("/{group_id}", response_model=GroupDivisionDepartmentIdsResponse)
async def update_group_endpoint(
        group_id: int,
        group_data: GroupUpdate,
        db: AsyncSession = Depends(get_db)
):
    updated_group = await update_group(db, group_id, group_data)
    if not updated_group:
        logger.warning("Группа не найдена")
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return updated_group


@router_groups.delete("/{group_id}", status_code=200)
async def delete_group_endpoint(
        group_id: int,
        db: AsyncSession = Depends(get_db)
):
    success = await delete_group(db, group_id)
    if not success:
        logger.warning("Группа не найдена")
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return None