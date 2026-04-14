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
    office_type = Column(String(100))                           # Тип офиса (MS Office, LibreOffice...)
    office_key = Column(String(100))                             # Ключ лицензии офиса

    # === Операционная система ===
    os_type = Column(String(100))                                # Тип ОС (Windows 10, Ubuntu...)
    os_key = Column(String(100))                            # Ключ лицензии ОС

    # === Удалённое управление ===
    remote_control = Column(String(150))                         # ПО удалённого управления

    # === Права доступа ===
    admin_permission = Column(Boolean, default=False)           # Админ права

    # === Установка ===
    who_installed = Column(String(150))                          # Кто установил (ФИО)

    # === Служебные поля ===
    installed_at = Column(DateTime, default=datetime.utcnow)     # Дата установки
    comment = Column(Text)                                       # Комментарий
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # === Связь с активом (опционально) ===
    assets = relationship("Asset", back_populates="software", lazy="select")

    def __repr__(self):
        return f"<Software(id={self.software_id}, os_type={self.os_type}, office_type={self.office_type})>"