from sqlalchemy.orm import relationship
from app.models.Base import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime

class User(Base):
    """
    Модель пользователя (сотрудника компании).
    Хранит информацию о сотрудниках для назначения активов.
    """
    __tablename__ = "users"

    # Идентификаторы
    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_tab_id = Column(String(50), unique=True, index=True, nullable=True)  # Табельный номер

    # Имена
    owner = Column(String(150), nullable=False, index=True)  # ФИО на русском
    user_en_name = Column(String(150), nullable=True)  # ФИО на английском

    # Должность и отдел
    user_position = Column(String(100), nullable=True)  # Должность
    department = Column(String(100), nullable=True, index=True)  # Отдел

    # Контакты
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(50), nullable=True)

    # Системные поля
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    # Связи
    assignments = relationship("UserAsset", back_populates="user", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<User(id={self.user_id}, tab_id={self.user_tab_id}, owner={self.owner})>"