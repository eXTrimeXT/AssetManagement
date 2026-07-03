from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.Company import Company
from app.schemas.companies.CompanySchemas import CompanyCreate, CompanyUpdate


async def get_company_by_id(db: AsyncSession, company_id: int) -> Optional[Company]:
    result = await db.execute(
        select(Company)
        .options(
            selectinload(Company.location_obj),
            selectinload(Company.creator)
        )
        .where(Company.company_id == company_id)
    )
    return result.scalar_one_or_none()


async def create_company(db: AsyncSession, company_in: CompanyCreate, employee_id: str) -> Company:
    db_company = Company(**company_in.model_dump(), created_by=employee_id)
    db.add(db_company)
    await db.commit()
    # Перезагружаем с связями
    return await get_company_by_id(db, db_company.company_id)


async def update_company(db: AsyncSession, company_id: int, company_data: CompanyUpdate) -> Optional[Company]:
    company = await get_company_by_id(db, company_id)
    if not company:
        return None
    update_data = company_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)
    await db.commit()
    return await get_company_by_id(db, company_id)


async def get_companies_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        name: Optional[str] = None
) -> Sequence[Company]:
    """Получить список компаний с фильтрами"""
    query = select(Company).options(
        selectinload(Company.location_obj),
        selectinload(Company.creator)
    )
    if name:
        query = query.where(Company.company_name.ilike(f"%{name}%"))
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def delete_company(db: AsyncSession, company_id: int) -> bool:
    """Удалить компанию"""
    company = await get_company_by_id(db, company_id)
    if not company:
        return False
    await db.delete(company)
    await db.commit()
    return True