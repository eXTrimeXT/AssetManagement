from sqlalchemy import Column, Integer, String
from app.models.Base import Base

class AssetStatus(Base):
    __tablename__ = "asset_status"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    status = Column(String(100), nullable=False, unique=True)