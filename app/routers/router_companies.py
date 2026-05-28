import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database.connection import get_db
from app.schemas.companies.CompanySchemas import (
    CompanyCreate,
    CompanyUpdate,
    CompanyResponse,
    CompanyShortResponse
)
from app.database.crud_companies import (
    create_company,
    get_company_by_id,
    get_companies_list,
    update_company,
    delete_company,
    check_company_name_exists
)
from app.service.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)

router_companies = APIRouter(prefix="/companies", tags=["Companies"], dependencies=[Depends(require_authorized_user)])


@router_companies.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company_endpoint(
        data: CompanyCreate,
        db: AsyncSession = Depends(get_db)
):
    """Создать новую компанию"""
    if await check_company_name_exists(db, data.company_name):
        logger.warning("Компания с таким названием уже существует")
        raise HTTPException(status_code=400, detail="Компания с таким названием уже существует")

    return await create_company(db, data)


@router_companies.get("/", response_model=List[CompanyShortResponse])
async def get_companies_endpoint(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_db)
):
    """Получить список всех компаний"""
    return await get_companies_list(db, skip, limit)


@router_companies.get("/{company_id}", response_model=CompanyResponse)
async def get_company_endpoint(
        company_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Получить компанию по ID"""
    obj = await get_company_by_id(db, company_id)
    if not obj:
        logger.warning("Компания не найдена")
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return obj


@router_companies.patch("/{company_id}", response_model=CompanyResponse)
async def update_company_endpoint(
        company_id: int,
        data: CompanyUpdate,
        db: AsyncSession = Depends(get_db)
):
    """Обновить данные компании"""
    if data.company_name:
        current = await get_company_by_id(db, company_id)
        if current and data.company_name != current.company_name:
            if await check_company_name_exists(db, data.company_name, exclude_id=company_id):
                logger.warning("Компания с таким названием уже существует")
                raise HTTPException(status_code=400, detail="Компания с таким названием уже существует")

    updated_obj = await update_company(db, company_id, data)
    if not updated_obj:
        logger.warning("Компания не найдена")
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return updated_obj


@router_companies.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_endpoint(
        company_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Удалить компанию"""
    success = await delete_company(db, company_id)
    if not success:
        logger.warning("Компания не найдена")
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return None