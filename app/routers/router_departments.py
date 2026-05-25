from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from app.database.connection import get_db
from app.schemas.departments.DepartmentResponse import (
    DepartmentResponse,
    DepartmentShortResponse,
    DepartmentWithDivisionsAndGroupsResponse
)
from app.schemas.departments.DepartmentCreate import DepartmentCreate
from app.schemas.departments.DepartmentUpdate import DepartmentUpdate
from app.database.crud_departments import *
from app.service.auth.auth_service import require_authorized_user
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.Division import Division
from app.models.Group import Group
from app.schemas.departments.SearchByAbbResponse import SearchByAbbreviationResponse

router_departments = APIRouter(
    prefix="/departments",
    tags=["Departments"],
    dependencies=[Depends(require_authorized_user)]
)


@router_departments.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department_endpoint(
        department_in: DepartmentCreate,
        db: AsyncSession = Depends(get_db)
):
    try:
        return await create_department(db, department_in)
    except IntegrityError:
        raise HTTPException(
            status_code=400,
            detail=f"Департамент с аббревиатурой '{department_in.abbreviation}' уже существует"
        )


@router_departments.get("/", response_model=List[DepartmentShortResponse])
async def get_departments_endpoint(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        name: Optional[str] = None,
        abbreviation: Optional[str] = None,
        db: AsyncSession = Depends(get_db)
):
    return await get_departments_list(db, skip, limit, name, abbreviation)


@router_departments.get("/id/{department_id}", response_model=DepartmentWithDivisionsAndGroupsResponse)
async def get_department_endpoint(
        department_id: int,
        db: AsyncSession = Depends(get_db)
):
    department = await get_department_by_id(db, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Департамент не найден")

    # Получаем все отделы департамента
    divisions_result = await db.execute(
        select(Division).where(Division.department_id == department_id)
    )
    divisions = divisions_result.scalars().all()

    # Для каждого отдела получаем его группы
    divisions_with_groups = []
    for div in divisions:
        groups_result = await db.execute(
            select(Group).where(Group.division_id == div.id)
        )
        groups = groups_result.scalars().all()
        divisions_with_groups.append({
            "id": div.id,
            "name": div.name,
            "abbreviation": div.abbreviation,
            "groups": [
                {"id": g.id, "name": g.name, "abbreviation": g.abbreviation}
                for g in groups
            ]
        })

    return DepartmentWithDivisionsAndGroupsResponse(
        id=department.id,
        name=department.name,
        abbreviation=department.abbreviation,
        divisions=divisions_with_groups
    )


@router_departments.patch("/{department_id}", response_model=DepartmentResponse)
async def update_department_endpoint(
        department_id: int,
        department_data: DepartmentUpdate,
        db: AsyncSession = Depends(get_db)
):
    try:
        updated_department = await update_department(db, department_id, department_data)
        if not updated_department:
            raise HTTPException(status_code=404, detail="Департамент не найден")
        return updated_department
    except IntegrityError:
        raise HTTPException(
            status_code=400,
            detail=f"Аббревиатура '{department_data.abbreviation}' уже занята"
        )


@router_departments.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department_endpoint(
        department_id: int,
        db: AsyncSession = Depends(get_db)
):
    success = await delete_department(db, department_id)
    if not success:
        raise HTTPException(status_code=404, detail="Департамент не найден")
    return None


@router_departments.get("/abb/{abbreviation}", response_model=SearchByAbbreviationResponse)
async def search_by_abbreviation_endpoint(
        abbreviation: str,
        db: AsyncSession = Depends(get_db)
):
    abbreviation = abbreviation.upper()
    # 1. Поиск в департаментах
    result = await db.execute(select(Department).where(Department.abbreviation == abbreviation))
    item = result.scalar_one_or_none()
    if item:
        return SearchByAbbreviationResponse(
            entity_type="department",
            id=item.id,
            name=item.name,
            abbreviation=item.abbreviation
        )

    # 2. Поиск в отделах
    result = await db.execute(select(Division).where(Division.abbreviation == abbreviation))
    item = result.scalar_one_or_none()
    if item:
        return SearchByAbbreviationResponse(
            entity_type="division",
            id=item.id,
            name=item.name,
            abbreviation=item.abbreviation
        )

    # 3. Поиск в группах
    result = await db.execute(select(Group).where(Group.abbreviation == abbreviation))
    item = result.scalar_one_or_none()
    if item:
        return SearchByAbbreviationResponse(
            entity_type="group",
            id=item.id,
            name=item.name,
            abbreviation=item.abbreviation
        )

    raise HTTPException(status_code=404, detail="Подразделение с указанной аббревиатурой не найдено")