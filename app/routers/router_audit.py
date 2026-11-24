from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.connection import get_db
from app.models.AuditLog import AuditLog
from typing import List

from app.schemas.audit.AuditLogSchemas import AuditLogResponse
from app.services.auth.auth_service import require_authorized_user

router_audit = APIRouter(prefix="/audit", tags=["Audit"])

@router_audit.get(
    "/",
    response_model=List[AuditLogResponse],
    summary="Получение журнала аудита / Get Audit Logs",
    description=(
            "RU: Возвращает список записей журнала аудита с поддержкой пагинации (параметры `skip` и `limit`). "
            "Записи отсортированы по убыванию идентификатора (новые записи отображаются первыми). Требуется авторизация пользователя.\n\n"
            "EN: Returns a list of audit log entries with pagination support (`skip` and `limit` parameters). "
            "Entries are sorted by ID in descending order (newest entries are displayed first). User authorization is required."
    )
)
async def get_audit_logs(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    result = await db.execute(select(AuditLog).offset(skip).limit(limit).order_by(AuditLog.id.desc()))
    return result.scalars().all()