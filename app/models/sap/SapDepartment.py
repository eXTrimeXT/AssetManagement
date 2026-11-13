from sqlalchemy import Column, String, DateTime, func
from app.models.Base import Base


class SapDepartment(Base):
    __tablename__ = "sap_departments"

    department_code = Column(String, primary_key=True, index=True, comment="Код подразделения (MVZ)")
    department_name = Column(String, nullable=True, comment="Полное название подразделения")
    department_shortname = Column(String, nullable=True, comment="Краткое название подразделения")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="Время последнего обновления")
