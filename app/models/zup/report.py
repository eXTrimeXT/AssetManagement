from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime
from app.models.Base import Base


class Report(Base):
    """Модель отчёта по присутствию из 1С-ЗУП"""
    __tablename__ = "zup_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)

    department_name = Column(String(200), nullable=False, index=True)
    total_employees = Column(Integer, default=0)
    present_employees = Column(Integer, default=0)
    absent_employees = Column(Integer, default=0)
    attendance_value = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.now, nullable=False)

    def __repr__(self):
        return f"<Report(department={self.department_name}, total={self.total_employees})>"