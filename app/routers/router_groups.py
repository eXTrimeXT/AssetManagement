import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from app.database.connection import get_db
from app.schemas.groups.GroupResponse import GroupResponse, GroupShortResponse
from app.schemas.groups.GroupCreate import GroupCreate
from app.schemas.groups.GroupUpdate import GroupUpdate
from app.database.crud_groups import *
from app.service.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)

router_groups = APIRouter(prefix="/groups", tags=["Groups"], dependencies=[Depends(require_authorized_user)])


@router_groups.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group_endpoint(
        group_in: GroupCreate,
        db: AsyncSession = Depends(get_db)
):
    return await create_group(db, group_in)


@router_groups.get("/", response_model=List[GroupShortResponse])
async def get_groups_endpoint(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        name: Optional[str] = None,
        abbreviation: Optional[str] = None,
        division_id: Optional[int] = None,
        db: AsyncSession = Depends(get_db)
):
    return await get_groups_list(db, skip, limit, name, abbreviation, division_id)


@router_groups.get("/{group_id}", response_model=GroupResponse)
async def get_group_endpoint(
        group_id: int,
        db: AsyncSession = Depends(get_db)
):
    group = await get_group_by_id(db, group_id)
    if not group:
        logger.warning("Группа не найдена")
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return group


@router_groups.patch("/{group_id}", response_model=GroupResponse)
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


@router_groups.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group_endpoint(
        group_id: int,
        db: AsyncSession = Depends(get_db)
):
    success = await delete_group(db, group_id)
    if not success:
        logger.warning("Группа не найдена")
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return None