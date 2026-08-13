from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.connection import get_db
from app.models.AuditLog import AuditLog
from typing import List

router_audit = APIRouter(prefix="/audit", tags=["Audit"])

@router_audit.get("/", response_model=List[dict])
async def get_audit_logs(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuditLog).offset(skip).limit(limit).order_by(AuditLog.id.desc()))
    return result.scalars().all()