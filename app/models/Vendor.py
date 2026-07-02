from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.Base import Base


class Vendor(Base):
    """
    Таблица производителей, вендоров и поставщиков.
    Связывает конкретное лицо/компанию с классом (ролью) и общей информацией о компании.
    """
    __tablename__ = "vendors"

    vendor_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Название вендора/поставщика (может отличаться от company_name, если это бренд или подразделение)
    name = Column(String(255), nullable=False, index=True)

    # Ссылка на справочник классов (обязательно)
    vendor_class_id = Column(Integer, ForeignKey("vendor_classes.vendor_class_id"), nullable=False, index=True)
    vendor_class = relationship("VendorClass", back_populates="vendors", lazy="joined")

    # Ссылка на компанию (опционально, если вендор является частью компании из таблицы Company)
    company_id = Column(Integer, ForeignKey("companies.company_id"), index=True, nullable=True)
    company = relationship("Company", back_populates="vendors", lazy="joined")

    # Кто создал запись
    created_by = Column(String(50), ForeignKey("users.user_tab_id"), nullable=True)
    creator = relationship("User", foreign_keys=[created_by], lazy="joined")

    # Дата создания
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    def __repr__(self):
        return f"<Vendor(id={self.vendor_id}, name='{self.name}', class_id={self.vendor_class_id})>"