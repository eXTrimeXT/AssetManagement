from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from app.database.connection import get_db
from app.schemas.divisions.DivisionResponse import DivisionResponse, DivisionShortResponse, DivisionWithGroupsResponse
from app.schemas.divisions.DivisionCreate import DivisionCreate
from app.schemas.divisions.DivisionUpdate import DivisionUpdate
from app.database.crud_divisions import *
from app.service.auth.auth_service import require_authorized_user
from app.models.Group import Group

router_divisions = APIRouter(prefix="/divisions", tags=["Divisions"], dependencies=[Depends(require_authorized_user)])


@router_divisions.post("/", response_model=DivisionResponse, status_code=status.HTTP_201_CREATED)
async def create_division_endpoint(
        division_in: DivisionCreate,
        db: AsyncSession = Depends(get_db)
):
    try:
        return await create_division(db, division_in)
    except IntegrityError:
        raise HTTPException(
            status_code=400,
            detail=f"Отдел с аббревиатурой '{division_in.abbreviation}' уже существует"
        )


@router_divisions.get("/", response_model=List[DivisionShortResponse])
async def get_divisions_endpoint(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        name: Optional[str] = None,
        abbreviation: Optional[str] = None,
        department_id: Optional[int] = None,
        db: AsyncSession = Depends(get_db)
):
    return await get_divisions_list(db, skip, limit, name, abbreviation, department_id)


@router_divisions.get("/{division_id}", response_model=DivisionWithGroupsResponse)
async def get_division_endpoint(
        division_id: int,
        db: AsyncSession = Depends(get_db)
):
    division = await get_division_by_id(db, division_id)
    if not division:
        raise HTTPException(status_code=404, detail="Отдел не найден")

    result = await db.execute(
        select(Group).where(Group.division_id == division_id)
    )
    groups = result.scalars().all()

    return DivisionWithGroupsResponse(
        id=division.id,
        name=division.name,
        abbreviation=division.abbreviation,
        department_id=division.department_id,
        groups=[
            {"id": g.id, "name": g.name, "abbreviation": g.abbreviation}
            for g in groups
        ]
    )


@router_divisions.patch("/{division_id}", response_model=DivisionResponse)
async def update_division_endpoint(
        division_id: int,
        division_data: DivisionUpdate,
        db: AsyncSession = Depends(get_db)
):
    try:
        updated_department = await update_division(db, division_id, division_data)
        if not updated_department:
            raise HTTPException(status_code=404, detail="Отдел не найден")
        return updated_department
    except IntegrityError:
        raise HTTPException(
            status_code=400,
            detail=f"Аббревиатура '{division_data.abbreviation}' уже занята"
        )


@router_divisions.delete("/{division_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_division_endpoint(
        division_id: int,
        db: AsyncSession = Depends(get_db)
):
    success = await delete_division(db, division_id)
    if not success:
        raise HTTPException(status_code=404, detail="Отдел не найден")
    return None