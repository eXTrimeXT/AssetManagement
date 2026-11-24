from sqlalchemy import Column, String, DateTime, func
from app.models.Base import Base

class SapMaterialClass(Base):
    __tablename__ = "sap_material_classes"

    material_class = Column(String, primary_key=True, index=True, comment="Код класса материала")
    language = Column(String, primary_key=True, index=True, comment="Код языка (например, 'R')")
    material_class_short = Column(String, nullable=True, comment="Краткое название класса")
    material_class_name = Column(String, nullable=True, comment="Полное название класса")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="Время последнего обновления")