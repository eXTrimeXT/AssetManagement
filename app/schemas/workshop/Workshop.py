from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


# === БАЗОВАЯ СХЕМА (для создания) ===
class WorkshopCreate(BaseModel):
    """
    Схема для создания нового цеха.
    """
    name: str = Field(..., min_length=1, max_length=255, description="Название цеха")
    code: str = Field(..., min_length=1, max_length=50, description="Код цеха (уникальный)")
    description: Optional[str] = Field(None, max_length=1000, description="Описание цеха")

    # Карта цеха
    background_image_url: Optional[str] = Field(None, max_length=500, description="URL фона карты")

    # === ГЕОМЕТРИЯ ЦЕХА ===
    geometry: Optional[dict] = Field(
        None,
        description="Геометрия цеха (полигон) для сложных форм. Пример: {'coordinates': [[0,0], [1920,0], ...]}"
    )

    # === РАЗМЕРЫ ПРЯМОУГОЛЬНИКА (если geometry нет) ===
    workshop_width: Optional[int] = Field(None, ge=100, le=10000, description="Ширина прямоугольника цеха")
    workshop_height: Optional[int] = Field(None, ge=100, le=10000, description="Высота прямоугольника цеха")

    # === ПОЗИЦИЯ НА ОБЩЕЙ КАРТЕ ===
    offset_x: Optional[int] = Field(0, ge=0, description="Смещение по X на общей карте")
    offset_y: Optional[int] = Field(0, ge=0, description="Смещение по Y на общей карте")

    @field_validator('geometry')
    @classmethod
    def validate_geometry(cls, v):
        """Валидация структуры геометрии."""
        if v is None:
            return v

        if not isinstance(v, dict):
            raise ValueError("Геометрия должна быть dict")

        if 'type' not in v or 'coordinates' not in v:
            raise ValueError("Геометрия должна содержать 'type' и 'coordinates'")

        if v['type'] != 'polygon':
            raise ValueError("Тип геометрии должен быть 'polygon'")

        coords = v['coordinates']
        if not isinstance(coords, list) or len(coords) < 3:
            raise ValueError("Координаты должны быть в виде списка, содержащего не менее 3 точек")

        for point in coords:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("Каждая координата должна быть списком из 2 чисел [x, y]")
            if not all(isinstance(n, (int, float)) for n in point):
                raise ValueError("Координаты должны быть числами")

        return v

# === СХЕМА ДЛЯ ОБНОВЛЕНИЯ ===
class WorkshopUpdate(BaseModel):
    """
    Схема для обновления цеха.
    Все поля необязательны.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=1000)

    background_image_url: Optional[str] = Field(None, max_length=500)

    is_active: Optional[bool] = None

    # === ГЕОМЕТРИЯ ЦЕХА ===
    geometry: Optional[dict] = Field(None, description="Геометрия цеха (полигон)")

    # === РАЗМЕРЫ ПРЯМОУГОЛЬНИКА ===
    workshop_width: Optional[int] = Field(None, ge=100, le=10000)
    workshop_height: Optional[int] = Field(None, ge=100, le=10000)

    # === ПОЗИЦИЯ НА ОБЩЕЙ КАРТЕ ===
    offset_x: Optional[int] = Field(0, ge=0, description="Смещение по X на общей карте")
    offset_y: Optional[int] = Field(0, ge=0, description="Смещение по Y на общей карте")

    @field_validator('geometry')
    @classmethod
    def validate_geometry(cls, v):
        """Валидация структуры геометрии."""
        if v is None:
            return v

        if not isinstance(v, dict):
            raise ValueError("Геометрия должна быть dict")

        if 'type' not in v or 'coordinates' not in v:
            raise ValueError("Геометрия должна содержать 'type' и 'coordinates'")

        if v['type'] != 'polygon':
            raise ValueError("Тип геометрии должен быть 'polygon'")

        coords = v['coordinates']
        if not isinstance(coords, list) or len(coords) < 3:
            raise ValueError("Координаты должны быть в виде списка, содержащего не менее 3 точек")

        for point in coords:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("Каждая координата должна быть списком из 2 чисел [x, y]")
            if not all(isinstance(n, (int, float)) for n in point):
                raise ValueError("Координаты должны быть числами")

        return v


# === СХЕМА ОТВЕТА (для чтения) ===
class WorkshopResponse(BaseModel):
    """
    Схема ответа с информацией о цехе.
    """
    model_config = ConfigDict(from_attributes=True)

    workshop_id: int
    name: str
    code: str
    description: Optional[str] = None

    background_image_url: Optional[str] = None

    is_active: bool

    # === ГЕОМЕТРИЯ ЦЕХА ===
    geometry: Optional[dict] = None

    # === РАЗМЕРЫ ПРЯМОУГОЛЬНИКА ===
    workshop_width: Optional[int] = None
    workshop_height: Optional[int] = None

    # === ПОЗИЦИЯ НА ОБЩЕЙ КАРТЕ ===
    offset_x: Optional[int] = Field(0, ge=0, description="Смещение по X на общей карте")
    offset_y: Optional[int] = Field(0, ge=0, description="Смещение по Y на общей карте")

    created_at: datetime
    updated_at: datetime


# === СХЕМА ДЛЯ СПИСКА ЦЕХОВ ===
class WorkshopListResponse(BaseModel):
    """
    Схема для списка цехов.
    """
    model_config = ConfigDict(from_attributes=True)

    workshop_id: int
    name: str
    code: str
    is_active: bool

    # === ГЕОМЕТРИЯ ЦЕХА ===
    geometry: Optional[dict] = None

    # === РАЗМЕРЫ ПРЯМОУГОЛЬНИКА ===
    workshop_width: Optional[int] = None
    workshop_height: Optional[int] = None

    # === ПОЗИЦИЯ НА ОБЩЕЙ КАРТЕ ===
    offset_x: Optional[int] = Field(0, ge=0, description="Смещение по X на общей карте")
    offset_y: Optional[int] = Field(0, ge=0, description="Смещение по Y на общей карте")


# === СХЕМА С АКТИВАМИ (для карты) ===
class WorkshopWithAssetsResponse(WorkshopResponse):
    """
    Расширенная схема цеха с количеством активов.
    """
    assets_count: int = 0
    active_positions_count: int = 0