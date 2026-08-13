from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from app.models.Base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_login = Column(String, nullable=True)
    action = Column(String, nullable=False)  # Например: "POST /api/assets"
    entity = Column(String, nullable=True)   # Сущность (опционально)
    entity_id = Column(Integer, nullable=True) # ID записи (опционально)
    request_data = Column(JSON, nullable=True) # Тело запроса/параметры
    created_at = Column(DateTime(), server_default=func.now())