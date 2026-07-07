from typing import TypeVar, Generic, List
from pydantic import BaseModel, Field

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Универсальная схема пагинированного ответа"""
    items: List[T]
    total: int = Field(..., description="Общее количество записей")
    page: int = Field(..., description="Текущая страница (начинается с 1)")
    page_size: int = Field(..., description="Размер страницы")
    total_pages: int = Field(..., description="Общее количество страниц")
    has_next: bool = Field(..., description="Есть ли следующая страница")
    has_previous: bool = Field(..., description="Есть ли предыдущая страница")