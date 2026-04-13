from pydantic import BaseModel
from pydantic import ConfigDict

class AssetTypeBase(BaseModel):
    """
    Базовая схема для типа актива.
    Содержит общие поля, которые используются в других схемах через наследование.
    """
    # Человекочитаемое название типа (например, "Ноутбук", "Сервер")
    name: str

    # Уникальный бизнес-код типа (например, 10, 20, 30).
    # Используется как ключ для связи с таблицей assets вместо внутреннего ID базы данных.
    type_id: int


class AssetTypeCreate(AssetTypeBase):
    """
    Схема для создания нового типа актива (POST запрос).
    Наследует все обязательные поля из AssetTypeBase.
    """
    pass


class AssetTypeResponse(AssetTypeBase):
    """
    Схема для ответа клиенту (GET запросы).
    """
    # from_attributes=True позволяет Pydantic конвертировать объект SQLAlchemy (ORM-модель) в JSON-ответ.
    # Без этого возникнет ошибка сериализации.
    model_config = ConfigDict(from_attributes=True)

    # Внутренний первичный ключ базы данных (autoincrement).
    # Добавляется только в ответ, так как при создании он генерируется БД автоматически.
    asset_type_id: int

class AssetTypeUpdate(BaseModel):
    """
    Схема для частичного обновления типа актива (PATCH запрос).
    """
    # Все поля опциональны (None по умолчанию).
    # Обновятся только те поля, которые явно переданы в запросе.
    name: str | None = None
    type_id: int | None = None

    # extra='ignore' игнорирует лишние поля в JSON-запросе, которые не описаны в схеме, предотвращая ошибки валидации.
    model_config = ConfigDict(extra='ignore')