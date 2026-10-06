from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.models.Base import Base

class ImportTask(Base):
    __tablename__ = "import_tasks"

    task_id = Column(String(36), primary_key=True, index=True)
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    allowed_cost_centers = Column(JSON, nullable=True)
    items_data = Column(JSON, nullable=True)  # Храним результаты обработки строк
    employee_id = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())