from app.models.Base import Base
from sqlalchemy import Column, Integer, String, Date, Enum, ForeignKey, Text, DateTime, Boolean
from datetime import datetime
from sqlalchemy.orm import relationship, backref

class Asset(Base):
    """
    Модель IT-актива (оборудования).
    Хранит информацию обо всех активах компании.
    """
    __tablename__ = "assets"

    # === Идентификаторы ===
    asset_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # === Основные поля (из ТЗ) ===
    asset_status = Column(String(100), nullable=False, index=True, default="Приемка")
    type_domain = Column(String(100), nullable=True)  # Тип домена
    type_id = Column(Integer, ForeignKey("asset_types.type_id"), nullable=False, index=True)  # Тип актива (ссылка на справочник)
    inventory_id = Column(String(50), unique=True, index=True, nullable=False)  # Инвентарный номер
    affixed_inventory_id = Column(Boolean, default=False, nullable=True)  # Инвентарный номер наклеен?
    info_storage_location = Column(String(200), nullable=True)  # Место хранения информации об активе
    location = Column(String(150), nullable=True)  # Местоположение актива
    serial_number = Column(String(100), unique=True, index=True, nullable=False)  # Серийный номер
    name = Column(String(150), nullable=False, index=True)  # Имя актива
    passwork = Column(String(200), nullable=True)  # Строковое значение (пароль/ключ)
    date_issue = Column(Date, nullable=True)  # Дата выдачи
    date_purchasing = Column(Date, nullable=True)  # Дата покупки
    comment = Column(Text, nullable=True)  # Комментарий

    # === Комплектация (иерархия через parent_id) ===
    # equipment = parent_id (может быть NULL или ссылаться на другой актив)
    parent_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=True, index=True)

    # === Служебные поля ===
    source = Column(String(100), nullable=True)  # Источник
    prepared_by = Column(String(100), nullable=True)  # Подготовил
    checked_by = Column(String(100), nullable=True)  # Проверил
    deleted_at = Column(DateTime, nullable=True, index=True)  # Soft delete
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    # Самореференция: комплектация (дочерние активы)
    parent = relationship(
        "Asset",
        remote_side=[asset_id],
        backref=backref(
            "children",
            lazy="selectin",
            cascade="all, delete-orphan"
        ),
        lazy="selectin"
    )

    # Тип актива
    asset_type = relationship("AssetType", back_populates="assets", lazy="joined")

    # Связь с software
    # software_list = relationship("Software", back_populates="asset", lazy="select", cascade="all, delete-orphan")
    software_id = Column(
        Integer,
        ForeignKey("software.software_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    software = relationship("Software", back_populates="assets", lazy="joined")

    # Связь с UserAsset
    user_assignments = relationship("UserAsset", back_populates="asset", lazy="select", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Asset(id={self.asset_id}, name={self.name}, inventory_id={self.inventory_id})>"