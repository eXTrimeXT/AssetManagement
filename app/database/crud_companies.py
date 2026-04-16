from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.Company import Company
from app.schemas.companies.CompanySchemas import CompanyCreate, CompanyUpdate


async def check_company_name_exists(db: AsyncSession, name: str, exclude_id: Optional[int] = None) -> bool:
    """Проверяет уникальность названия компании"""
    query = select(Company).where(Company.company_name == name)
    if exclude_id:
        query = query.where(Company.company_id != exclude_id)
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


async def create_company(db: AsyncSession, data: CompanyCreate) -> Company:
    """Создает новую компанию"""
    db_obj = Company(**data.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    # Подгружаем локацию для ответа
    await db.refresh(db_obj, attribute_names=["location_obj"])
    return db_obj


async def get_company_by_id(db: AsyncSession, company_id: int) -> Optional[Company]:
    """Получает компанию по ID с подгрузкой локации"""
    result = await db.execute(
        select(Company)
        .where(Company.company_id == company_id)
        .options(selectinload(Company.location_obj))
    )
    return result.scalar_one_or_none()


async def get_companies_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[Company]:
    """Получает список компаний"""
    query = select(Company).options(selectinload(Company.location_obj)).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def update_company(db: AsyncSession, company_id: int, data: CompanyUpdate) -> Optional[Company]:
    """Обновляет данные компании"""
    obj = await get_company_by_id(db, company_id)
    if not obj:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(obj, key, value)

    await db.commit()
    await db.refresh(obj)
    await db.refresh(obj, attribute_names=["location_obj"])
    return obj


async def delete_company(db: AsyncSession, company_id: int) -> bool:
    """Удаляет компанию"""
    obj = await get_company_by_id(db, company_id)
    if not obj:
        return False

    await db.delete(obj)
    await db.commit()
    return True