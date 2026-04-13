from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.models.Base import Base

class Software(Base):
    """
    Модель программного обеспечения.
    Хранит информацию о лицензиях и установленном ПО.
    """
    __tablename__ = "software"

    # === Идентификаторы ===
    software_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # === Офисное ПО ===
    office_type = Column(String(100), nullable=True)                            # Тип офиса (MS Office, LibreOffice...)
    office_key = Column(String(100), nullable=True)                             # Ключ лицензии офиса

    # === Операционная система ===
    os_type = Column(String(100), nullable=True)                                # Тип ОС (Windows 10, Ubuntu...)
    os_key = Column(String(100), nullable=True)                                 # Ключ лицензии ОС

    # === Удалённое управление ===
    remote_control = Column(String(150), nullable=True)                         # ПО удалённого управления

    # === Права доступа ===
    admin_permission = Column(Boolean, default=False, nullable=False)           # Админ права

    # === Установка ===
    who_installed = Column(String(150), nullable=True)                          # Кто установил (ФИО)

    # === Служебные поля ===
    installed_at = Column(DateTime, default=datetime.utcnow, nullable=True)     # Дата установки
    comment = Column(Text, nullable=True)                                       # Комментарий
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    # === Связь с активом (опционально) ===
    assets = relationship("Asset", back_populates="software", lazy="select")

    def __repr__(self):
        return f"<Software(id={self.software_id}, os_type={self.os_type}, office_type={self.office_type})>"