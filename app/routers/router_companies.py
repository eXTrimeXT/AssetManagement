import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.database.connection import get_db
from app.database.crud_companies import (
    get_company_by_id, get_companies_list, create_company, update_company, delete_company
)
from app.schemas.companies.CompanySchemas import (
    CompanyCreate, CompanyUpdate, CompanyResponse, CompanyShortResponse
)
from app.services.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)
router_companies = APIRouter(prefix="/companies", tags=["Companies"])


@router_companies.get("/", response_model=List[CompanyResponse])
async def get_companies(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        name: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await get_companies_list(db, skip, limit, name)


@router_companies.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
        company_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    company = await get_company_by_id(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return company


@router_companies.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company_endpoint(
        company_in: CompanyCreate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    return await create_company(db, company_in, current_user.employee_id)


@router_companies.patch("/{company_id}", response_model=CompanyResponse)
async def update_company_endpoint(
        company_id: int,
        company_data: CompanyUpdate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    updated = await update_company(db, company_id, company_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return updated


@router_companies.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_endpoint(
        company_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    success = await delete_company(db, company_id)
    if not success:
        raise HTTPException(status_code=404, detail="Компания не найдена")