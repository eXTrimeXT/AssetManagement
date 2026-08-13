from sqlalchemy.ext.asyncio import AsyncSession
from app.models.AuditLog import AuditLog

async def create_audit_log(
        db: AsyncSession,
        user_login: str,
        action: str,
        entity: str = None,
        entity_id: int = None,
        request_data: dict = None
):
    log = AuditLog(
        user_login=user_login,
        action=action,
        entity=entity,
        entity_id=entity_id,
        request_data=request_data
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log