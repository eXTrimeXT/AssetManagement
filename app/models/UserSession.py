from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime
from datetime import datetime

from app.models.Base import Base

class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String, unique=True, index=True)
    token: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    user_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)