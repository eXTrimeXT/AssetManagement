from operator import index
from typing import Optional
from app.models.Base import Base
from sqlalchemy import Column, Integer, String, Date, Enum, ForeignKey, Text, DateTime, Boolean
from datetime import datetime
from sqlalchemy.orm import relationship, backref, Mapped

class Asset(Base):
    """
    Модель IT-актива (оборудования).
    Хранит информацию обо всех активах компании.
    """
    __tablename__ = "assets"

    # === Идентификаторы ===
    asset_id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # === Основные поля (из ТЗ) ===
    asset_status = Column(String(100), index=True, default="Приемка")               # Статус актива
    type_domain = Column(String(100))                                               # Тип домена
    model_id = Column(Integer, ForeignKey("asset_models.model_id"), index=True, nullable=True)  # Модель актива (ссылка на справочник)
    inventory_id = Column(String(100), unique=True, index=True)                     # Инвентарный номер
    affixed_inventory_id = Column(Boolean, default=False)                           # Инвентарный номер наклеен?
    info_storage_location = Column(String(200))                                     # Место хранения информации об активе

    # === СКЛАД (вместо локации) ===
    warehouse_id = Column(Integer, ForeignKey("warehouses.warehouse_id"), index=True)
    warehouse_obj: Mapped[Optional["Warehouse"]] = relationship(
        "Warehouse",
        back_populates="assets",
        lazy="joined"  # Подгружаем склад сразу при запросе актива
    )

    serial_number = Column(String(100), unique=True, index=True, nullable=True)  # Серийный номер
    name = Column(String(150), nullable=False, index=True)                       # Имя актива
    date_issue = Column(Date)                                                    # Дата выдачи
    date_purchasing = Column(Date)                                               # Дата покупки
    comment = Column(Text)                                                       # Комментарий
    price = Column(Integer, index=True)                                          # Цена

    # === Комплектация (иерархия через parent_id) ===
    parent_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), index=True)

    # === Производитель и поставщик ===
    manufacturer_id = Column(Integer, ForeignKey("vendors.vendor_id"), index=True)
    manufacturer = relationship("Vendor", foreign_keys=[manufacturer_id], lazy="joined")

    vendor_id = Column(Integer, ForeignKey("vendors.vendor_id"), index=True)
    vendor = relationship("Vendor", foreign_keys=[vendor_id], lazy="joined")

    # === Служебные поля ===
    prepared_by = Column(Integer, ForeignKey("users.user_id"))                   # Подготовил
    checked_by = Column(Integer, ForeignKey("users.user_id"))                    # Проверил

    deleted_at = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # === Связи ===
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

    preparer = relationship("User", foreign_keys=[prepared_by])
    checker = relationship("User", foreign_keys=[checked_by])

    software_id = Column(Integer, ForeignKey("software.software_id", ondelete="SET NULL"), index=True)
    software = relationship("Software", back_populates="assets", lazy="joined")

    # Модель актива (вместо AssetType)
    model = relationship("AssetModel", back_populates="assets", lazy="joined")

    @property
    def type_asset(self) -> Optional[str]:
        """Извлекает en_name типа актива через цепочку: model -> class -> type"""
        if self.model and self.model.asset_class and self.model.asset_class.asset_type:
            return self.model.asset_class.asset_type.en_name
        return None

    def __repr__(self):
        return f"<Asset(id={self.asset_id}, name={self.name}, inventory_id={self.inventory_id})>"