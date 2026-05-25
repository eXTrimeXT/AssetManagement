from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from app.database.connection import get_db
from app.schemas.departments.DepartmentResponse import DepartmentResponse
from app.schemas.departments.DepartmentCreate import DepartmentCreate
from app.schemas.departments.DepartmentUpdate import DepartmentUpdate
from app.database.crud_departments import *
from app.service.auth.auth_service import require_authorized_user

router_departments = APIRouter(prefix="/departments", tags=["Departments"], dependencies=[Depends(require_authorized_user)])


@router_departments.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department_endpoint(
        department_in: DepartmentCreate,
        db: AsyncSession = Depends(get_db)
):
    return await create_department(db, department_in)


@router_departments.get("/", response_model=List[DepartmentResponse])
async def get_departments_endpoint(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        name: Optional[str] = None,
        abbreviation: Optional[str] = None,
        db: AsyncSession = Depends(get_db)
):
    return await get_departments_list(db, skip, limit, name, abbreviation)


@router_departments.get("/{department_id}", response_model=DepartmentResponse)
async def get_department_endpoint(
        department_id: int,
        db: AsyncSession = Depends(get_db)
):
    department = await get_department_by_id(db, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Департамент не найден")
    return department


@router_departments.patch("/{department_id}", response_model=DepartmentResponse)
async def update_department_endpoint(
        department_id: int,
        department_data: DepartmentUpdate,
        db: AsyncSession = Depends(get_db)
):
    updated_department = await update_department(db, department_id, department_data)
    if not updated_department:
        raise HTTPException(status_code=404, detail="Департамент не найден")
    return updated_department


@router_departments.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department_endpoint(
        department_id: int,
        db: AsyncSession = Depends(get_db)
):
    success = await delete_department(db, department_id)
    if not success:
        raise HTTPException(status_code=404, detail="Департамент не найден")
    return None