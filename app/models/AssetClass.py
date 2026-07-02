from sqlalchemy import String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import mapped_column, relationship
from datetime import datetime
from app.models.Base import Base

class AssetClass(Base):
    __tablename__ = "asset_classes"

    class_id = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    class_name = mapped_column(String(100), nullable=False, index=True)

    # === ЯВНАЯ СВЯЗЬ НА asset_type_id ===
    class_type_id = mapped_column(
        Integer,
        ForeignKey("asset_types.asset_type_id"),
        nullable=False,
        index=True
    )

    description = mapped_column(Text, nullable=True)

    created_at = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    created_by = mapped_column(String(50), ForeignKey("users.user_tab_id"), nullable=True)
    updated_by = mapped_column(String(50), ForeignKey("users.user_tab_id"), nullable=True)

    # === ОТНОШЕНИЯ ===
    asset_type = relationship("AssetType", foreign_keys=[class_type_id], lazy="joined")
    models = relationship("AssetModel", back_populates="asset_class", cascade="all, delete-orphan")

    creator = relationship("User", foreign_keys=[created_by], lazy="joined")
    updater = relationship("User", foreign_keys=[updated_by], lazy="joined")

    def __repr__(self) -> str:
        return f"<AssetClass(id={self.class_id}, name={self.class_name})>"